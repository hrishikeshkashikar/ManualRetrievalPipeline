"""
Vision Captioner module.

Uses Ollama's vision-capable LLM to generate rich text descriptions
of diagrams, schematics, and page images from machine manuals.
This makes visual content searchable via text embeddings.
"""

import logging
from pathlib import Path

import ollama

from app.config import settings
from app.models.schemas import DocumentChunk
from app.utils.image_utils import load_image, resize_image, image_to_bytes
from app.utils.path_utils import to_relative_image_path

logger = logging.getLogger(__name__)

# Prompts tailored for machine manual content
PAGE_CAPTION_PROMPT = (
    "You are analyzing a page from a machine/equipment manual. "
    "Describe ALL content visible on this page in detail. Include:\n"
    "- All text content, headings, and labels\n"
    "- Tables and their data\n"
    "- Diagrams, schematics, and their components\n"
    "- Part numbers, model numbers, and specifications\n"
    "- Procedural steps and instructions\n"
    "- Warning or safety symbols and their meanings\n"
    "- Any error codes or troubleshooting information\n"
    "Be thorough — this description will be used to help technicians "
    "find relevant information when troubleshooting problems."
)

DIAGRAM_CAPTION_PROMPT = (
    "You are analyzing a diagram/image from a machine/equipment manual. "
    "Describe this diagram in detail. Include:\n"
    "- What type of diagram this is (wiring diagram, assembly drawing, "
    "flowchart, schematic, photo, etc.)\n"
    "- All component names and labels visible\n"
    "- Connections, relationships, and flow between components\n"
    "- Any measurements, dimensions, or specifications\n"
    "- Part numbers or reference numbers\n"
    "- Color coding or symbol meanings\n"
    "- Any text or annotations in the image\n"
    "Be thorough — this description will be used to help technicians "
    "understand and reference this diagram."
)


class VisionCaptioner:
    """Generates text captions for images using Ollama's vision model."""

    def __init__(self) -> None:
        self.model = settings.ollama_vision_model
        self.base_url = settings.ollama_base_url
        self.max_resolution = settings.max_image_resolution
        self.timeout = settings.ollama_request_timeout
        self.num_ctx = settings.ollama_num_ctx
        self._client: ollama.Client | None = None

    @property
    def client(self) -> ollama.Client:
        """Lazy-initialize the Ollama client."""
        if self._client is None:
            self._client = ollama.Client(
                host=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    def caption_image(self, image_path: str | Path, prompt: str | None = None) -> str:
        """
        Generate a text caption for a single image.

        Args:
            image_path: Path to the image file.
            prompt: Custom prompt. Defaults to DIAGRAM_CAPTION_PROMPT.

        Returns:
            Generated caption text.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Load and resize for VLM input
        image = load_image(image_path)
        image = resize_image(image, self.max_resolution)
        image_bytes = image_to_bytes(image, format="PNG")

        caption_prompt = prompt or DIAGRAM_CAPTION_PROMPT

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": caption_prompt,
                        "images": [image_bytes],
                    }
                ],
                options={"num_ctx": self.num_ctx},
            )
            caption = response.message.content
            logger.debug(
                f"Generated caption for {image_path.name} " f"({len(caption)} chars)"
            )
            return caption

        except Exception as e:
            logger.error(f"Failed to caption {image_path.name}: {e}")
            raise

    def caption_page(self, image_path: str | Path) -> str:
        """
        Generate a detailed caption for a full page render.

        Args:
            image_path: Path to the rendered page image.

        Returns:
            Generated caption text.
        """
        return self.caption_image(image_path, prompt=PAGE_CAPTION_PROMPT)

    def caption_diagram(self, image_path: str | Path) -> str:
        """
        Generate a detailed caption for an extracted diagram/image.

        Args:
            image_path: Path to the extracted diagram image.

        Returns:
            Generated caption text.
        """
        return self.caption_image(image_path, prompt=DIAGRAM_CAPTION_PROMPT)

    def process_images_for_manual(
        self,
        images: list[dict],
        manual_id: str,
        source_file: str,
    ) -> list[DocumentChunk]:
        """
        Generate captions for all images from a manual and return
        them as DocumentChunks ready for embedding.

        Args:
            images: List of image info dicts from PDFProcessor.
            manual_id: Manual identifier.
            source_file: Original PDF filename.

        Returns:
            List of DocumentChunk objects with caption content.
        """
        caption_chunks: list[DocumentChunk] = []
        total = len(images)
        successful = 0

        logger.info(f"Generating captions for {total} images from {source_file}")

        for idx, img_info in enumerate(images):
            image_path = img_info["path"]
            page_num = img_info["page_number"]
            img_type = img_info["type"]

            logger.info(
                f"Captioning image {idx + 1}/{total} "
                f"(page {page_num}, type: {img_type})"
            )

            try:
                if img_type == "page_render":
                    caption = self.caption_page(image_path)
                else:
                    caption = self.caption_diagram(image_path)

                if not caption or len(caption.strip()) < 10:
                    logger.warning(f"Skipping empty/trivial caption for {image_path}")
                    continue

                chunk_id = f"{manual_id}_p{page_num}_cap_{img_info['image_index']}"
                page_image_path = to_relative_image_path(
                    Path(settings.image_store_dir) / manual_id / f"page_{page_num}.png",
                    manual_id=manual_id,
                )
                rel_image_path = to_relative_image_path(image_path, manual_id=manual_id)

                caption_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        content=caption,
                        content_type="image_caption",
                        source_file=source_file,
                        manual_id=manual_id,
                        page_number=page_num,
                        chunk_index=img_info["image_index"],
                        section_header=None,
                        image_path=rel_image_path,
                        page_image_path=page_image_path,
                    )
                )
                successful += 1

            except Exception as e:
                logger.error(
                    f"Failed to caption image {idx + 1}/{total} "
                    f"(page {page_num}): {e}"
                )
                continue

        logger.info(f"Generated {successful}/{total} captions for {source_file}")
        return caption_chunks

    def is_available(self) -> bool:
        """Check if the Ollama service and vision model are available."""
        try:
            models = self.client.list()
            available = [m.model for m in models.models]
            return self.model in available
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
