"""
Vector Store module.

Wraps ChromaDB for persistent vector storage with metadata filtering.
Provides operations for adding, searching, and managing document collections.
"""

import logging

import chromadb

from app.config import settings
from app.models.schemas import DocumentChunk, RetrievedChunk

logger = logging.getLogger(__name__)

# ChromaDB collection name prefix
COLLECTION_PREFIX = "manual_"


class VectorStore:
    """
    ChromaDB-backed vector store for document chunks.

    Each manual gets its own collection for independent management.
    A unified collection is also maintained for cross-manual search.
    """

    def __init__(self) -> None:
        self._client: chromadb.PersistentClient | None = None

    def initialize(self, path: str | None = None) -> None:
        """Initialize (or re-initialize) the ChromaDB persistent client."""
        persist_path = path or str(settings.chroma_persist_dir)
        logger.info("Initializing ChromaDB at %s", persist_path)

        # Drop previous client so remounts don't keep a locked/stale handle
        self._client = None

        from pathlib import Path

        Path(persist_path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_path)
        self._get_or_create_unified_collection()
        logger.info("ChromaDB initialized successfully")

    @property
    def client(self) -> chromadb.PersistentClient:
        """Get the ChromaDB client, raising if not initialized."""
        if self._client is None:
            raise RuntimeError("VectorStore not initialized. Call initialize() first.")
        return self._client

    @property
    def is_ready(self) -> bool:
        """Check if the vector store is operational."""
        try:
            if self._client is None:
                return False
            self._client.heartbeat()
            return True
        except Exception:
            return False

    def _get_or_create_unified_collection(self) -> chromadb.Collection:
        """Get or create the unified collection for cross-manual search."""
        return self.client.get_or_create_collection(
            name="all_manuals",
            metadata={"hnsw:space": "cosine"},
        )

    def _get_or_create_manual_collection(self, manual_id: str) -> chromadb.Collection:
        """Get or create a collection for a specific manual."""
        return self.client.get_or_create_collection(
            name=f"{COLLECTION_PREFIX}{manual_id}",
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int:
        """
        Add document chunks and their embeddings to the vector store.

        Chunks are added to both the manual-specific collection and
        the unified collection.

        Args:
            chunks: List of DocumentChunk objects.
            embeddings: Corresponding embedding vectors.

        Returns:
            Number of chunks successfully added.
        """
        if not chunks or not embeddings:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatched lengths: {len(chunks)} chunks vs "
                f"{len(embeddings)} embeddings"
            )

        manual_id = chunks[0].manual_id
        manual_collection = self._get_or_create_manual_collection(manual_id)
        unified_collection = self._get_or_create_unified_collection()

        # Prepare data for ChromaDB
        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [
            {
                "source_file": chunk.source_file,
                "manual_id": chunk.manual_id,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "content_type": chunk.content_type,
                "section_header": chunk.section_header or "",
                "image_path": chunk.image_path or "",
                "page_image_path": chunk.page_image_path or "",
            }
            for chunk in chunks
        ]

        # Add to manual-specific collection
        try:
            manual_collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            logger.debug(
                f"Added {len(chunks)} chunks to manual collection " f"{manual_id}"
            )
        except Exception as e:
            logger.error(f"Failed to add to manual collection {manual_id}: {e}")
            raise

        # Add to unified collection
        try:
            unified_collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            logger.debug(f"Added {len(chunks)} chunks to unified collection")
        except Exception as e:
            logger.error(f"Failed to add to unified collection: {e}")
            raise

        return len(chunks)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 15,
        manual_filter: str | None = None,
    ) -> list[RetrievedChunk]:
        """
        Search for the most similar chunks to a query embedding.

        Args:
            query_embedding: The query's embedding vector.
            top_k: Number of results to return.
            manual_filter: Optional manual_id to restrict search.

        Returns:
            List of RetrievedChunk objects sorted by similarity.
        """
        if manual_filter:
            collection_name = f"{COLLECTION_PREFIX}{manual_filter}"
            try:
                collection = self.client.get_collection(collection_name)
            except Exception:
                logger.warning(
                    f"Manual collection {manual_filter} not found, "
                    f"falling back to unified"
                )
                collection = self._get_or_create_unified_collection()
        else:
            collection = self._get_or_create_unified_collection()

        # Ensure we don't request more results than available
        collection_count = collection.count()
        effective_top_k = min(top_k, collection_count) if collection_count > 0 else 0

        if effective_top_k == 0:
            logger.warning("No documents in the collection to search")
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=effective_top_k,
            include=["documents", "metadatas", "distances"],
        )

        retrieved: list[RetrievedChunk] = []

        if not results["ids"] or not results["ids"][0]:
            return retrieved

        for i, chunk_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i]
            document = results["documents"][0][i]
            distance = results["distances"][0][i]

            chunk = DocumentChunk(
                chunk_id=chunk_id,
                content=document,
                content_type=metadata.get("content_type", "text"),
                source_file=metadata.get("source_file", ""),
                manual_id=metadata.get("manual_id", ""),
                page_number=metadata.get("page_number", 0),
                chunk_index=metadata.get("chunk_index", 0),
                section_header=metadata.get("section_header") or None,
                image_path=metadata.get("image_path") or None,
                page_image_path=metadata.get("page_image_path") or None,
            )

            retrieved.append(RetrievedChunk(chunk=chunk, distance=distance))

        return retrieved

    def delete_manual(self, manual_id: str) -> bool:
        """
        Delete all data for a specific manual.

        Removes both the manual-specific collection and its entries
        from the unified collection.

        Args:
            manual_id: The manual identifier to delete.

        Returns:
            True if deletion was successful.
        """
        # Delete manual-specific collection
        collection_name = f"{COLLECTION_PREFIX}{manual_id}"
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted manual collection: {collection_name}")
        except Exception as e:
            logger.warning(f"Could not delete manual collection {collection_name}: {e}")

        # Remove from unified collection
        try:
            unified = self._get_or_create_unified_collection()
            # Get all IDs for this manual
            results = unified.get(
                where={"manual_id": manual_id},
                include=[],
            )
            if results["ids"]:
                unified.delete(ids=results["ids"])
                logger.info(
                    f"Removed {len(results['ids'])} chunks from "
                    f"unified collection for manual {manual_id}"
                )
        except Exception as e:
            logger.error(f"Failed to clean unified collection for {manual_id}: {e}")
            return False

        return True

    def list_manuals(self) -> list[dict]:
        """
        List all indexed manuals with their stats.

        Returns:
            List of dicts with manual_id, filename, chunk_count.
        """
        collections = self.client.list_collections()
        manuals = []

        for col in collections:
            if col.name.startswith(COLLECTION_PREFIX):
                manual_id = col.name[len(COLLECTION_PREFIX) :]
                collection = self.client.get_collection(col.name)
                count = collection.count()

                # Get the source filename from the first chunk's metadata
                filename = ""
                if count > 0:
                    sample = collection.peek(limit=1)
                    if sample["metadatas"]:
                        filename = sample["metadatas"][0].get("source_file", "")

                manuals.append(
                    {
                        "manual_id": manual_id,
                        "filename": filename,
                        "total_chunks": count,
                    }
                )

        return manuals

    def get_total_chunks(self) -> int:
        """Get the total number of chunks across all manuals."""
        try:
            unified = self._get_or_create_unified_collection()
            return unified.count()
        except Exception:
            return 0
