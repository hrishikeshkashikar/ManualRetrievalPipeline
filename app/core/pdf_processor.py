"""
PDF Processing module.

Handles:
- Text extraction per page
- Smart text chunking with overlap
- Page rendering to high-resolution images
- Embedded image/diagram extraction
- Section header detection
"""

import hashlib
import io
import logging
import re
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

from app.config import settings
from app.models.schemas import DocumentChunk
from app.utils.image_utils import save_image

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Processes PDF manuals into text chunks and images."""

    def __init__(self) -> None:
        self.chunk_size = settings.chunk_size
        self.chunk_overlap = settings.chunk_overlap
        self.render_dpi = settings.page_render_dpi
        self.image_store_dir = settings.image_store_dir

    def generate_manual_id(self, filepath: Path) -> str:
        """Generate a deterministic manual ID from the file content hash."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                hasher.update(block)
        return hasher.hexdigest()[:16]

    def process_pdf(
        self, filepath: Path, manual_id: str
    ) -> tuple[list[DocumentChunk], list[dict]]:
        """
        Process a PDF file into document chunks and extracted images.

        Args:
            filepath: Path to the PDF file.
            manual_id: Unique identifier for this manual.

        Returns:
            Tuple of:
              - List of DocumentChunk objects (text chunks)
              - List of image info dicts with keys: path, page_number, image_index, type
        """
        logger.info(f"Processing PDF: {filepath.name} (manual_id={manual_id})")
        doc = fitz.open(str(filepath))

        all_chunks: list[DocumentChunk] = []
        all_images: list[dict] = []
        manual_image_dir = self.image_store_dir / manual_id
        manual_image_dir.mkdir(parents=True, exist_ok=True)

        total_pages = len(doc)
        logger.info(f"PDF has {total_pages} pages")

        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_num = page_idx + 1  # 1-indexed
            logger.debug(f"Processing page {page_num}/{total_pages}")

            # ── 1. Extract text and create chunks ──────────────────────
            page_text = page.get_text("text")
            if page_text.strip():
                section_header = self._detect_section_header(page_text)
                chunks = self._chunk_text(page_text, section_header)

                for chunk_idx, chunk_text in enumerate(chunks):
                    chunk_id = f"{manual_id}_p{page_num}_c{chunk_idx}"
                    page_image_path = str(manual_image_dir / f"page_{page_num}.png")
                    all_chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            content=chunk_text,
                            content_type="text",
                            source_file=filepath.name,
                            manual_id=manual_id,
                            page_number=page_num,
                            chunk_index=chunk_idx,
                            section_header=section_header,
                            image_path=None,
                            page_image_path=page_image_path,
                        )
                    )

            # ── 2. Render page as image ────────────────────────────────
            page_image_path = self._render_page(page, manual_image_dir, page_num)
            all_images.append(
                {
                    "path": str(page_image_path),
                    "page_number": page_num,
                    "image_index": 0,
                    "type": "page_render",
                }
            )

            # ── 3. Extract embedded images/diagrams ────────────────────
            extracted = self._extract_images(doc, page, manual_image_dir, page_num)
            all_images.extend(extracted)

        doc.close()

        logger.info(
            f"Processed {filepath.name}: "
            f"{len(all_chunks)} text chunks, {len(all_images)} images"
        )
        return all_chunks, all_images

    def _detect_section_header(self, page_text: str) -> str | None:
        """
        Attempt to detect a section header from the page text.

        Looks for common patterns like numbered sections, all-caps lines,
        or lines that appear to be titles.
        """
        lines = page_text.strip().split("\n")
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if not line:
                continue

            # Numbered section pattern: "1.2 Maintenance" or "Chapter 3: ..."
            if re.match(
                r"^(\d+\.?\d*\.?\d*)\s+[A-Z]",
                line,
            ):
                return line[:100]

            # "Chapter X" or "Section X" pattern
            if re.match(r"^(Chapter|Section|Part)\s+\d", line, re.IGNORECASE):
                return line[:100]

            # All caps line that's short enough to be a header
            if line.isupper() and 3 < len(line) < 80:
                return line

        return None

    def _chunk_text(self, text: str, section_header: str | None = None) -> list[str]:
        """
        Split text into overlapping chunks.

        If a section header is detected, it's prepended to each chunk
        for better retrieval context.
        """
        text = text.strip()
        if not text:
            return []

        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.chunk_size

            # Try to break at a sentence boundary
            if end < text_length:
                # Look for sentence-ending punctuation near the chunk boundary
                search_start = max(start + self.chunk_size - 100, start)
                search_region = text[search_start:end]

                # Find the last sentence boundary
                for sep in [". ", ".\n", "\n\n", "\n", "; ", ", "]:
                    last_sep = search_region.rfind(sep)
                    if last_sep != -1:
                        end = search_start + last_sep + len(sep)
                        break

            chunk_text = text[start:end].strip()

            # Prepend section header for context
            if section_header and chunk_text:
                chunk_text = f"[{section_header}]\n{chunk_text}"

            if chunk_text:
                chunks.append(chunk_text)

            # Move forward by chunk_size - overlap
            start = start + self.chunk_size - self.chunk_overlap

        return chunks

    def _render_page(self, page: fitz.Page, output_dir: Path, page_num: int) -> Path:
        """Render a PDF page to a PNG image at configured DPI."""
        zoom = self.render_dpi / 72  # 72 is the default DPI
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix)

        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        output_path = output_dir / f"page_{page_num}.png"
        save_image(image, output_path)

        logger.debug(f"Rendered page {page_num} to {output_path}")
        return output_path

    def _extract_images(
        self,
        doc: fitz.Document,
        page: fitz.Page,
        output_dir: Path,
        page_num: int,
    ) -> list[dict]:
        """
        Extract embedded images from a PDF page.

        Returns a list of image info dicts.
        """
        extracted = []
        image_list = page.get_images(full=True)

        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if base_image is None:
                    continue

                image_bytes = base_image["image"]
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

                # Skip tiny images (likely icons or decorations)
                width, height = image.size
                if width < 50 or height < 50:
                    logger.debug(
                        f"Skipping tiny image on page {page_num}: " f"{width}x{height}"
                    )
                    continue

                output_path = output_dir / f"page_{page_num}_img_{img_idx}.png"
                save_image(image, output_path)

                extracted.append(
                    {
                        "path": str(output_path),
                        "page_number": page_num,
                        "image_index": img_idx + 1,
                        "type": "extracted_image",
                    }
                )
                logger.debug(
                    f"Extracted image {img_idx} from page {page_num}: "
                    f"{width}x{height}"
                )

            except Exception as e:
                logger.warning(
                    f"Failed to extract image {img_idx} from page {page_num}: {e}"
                )
                continue

        return extracted

    def get_page_count(self, filepath: Path) -> int:
        """Get the number of pages in a PDF without full processing."""
        doc = fitz.open(str(filepath))
        count = len(doc)
        doc.close()
        return count
