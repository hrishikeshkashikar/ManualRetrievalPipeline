"""
Generator module.

Uses Ollama's vision-capable LLM to generate structured diagnostic
responses based on retrieved context (text + images).
"""

import json
import logging

import ollama

from app.config import settings
from app.models.schemas import RetrievedChunk
from app.utils.image_utils import load_image, resize_image, image_to_bytes
from app.utils.path_utils import resolve_stored_image_path

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a machine maintenance expert assistant. You help technicians \
diagnose problems and find solutions using information from machine manuals.

You MUST respond in the following JSON format:
{
    "answer": "A comprehensive answer explaining the diagnosis and solution",
    "possible_issues": ["Issue 1 description", "Issue 2 description"],
    "recommended_solutions": ["Step-by-step solution 1", "Step-by-step solution 2"],
    "safety_warnings": ["Warning 1", "Warning 2"]
}

Rules:
- Base your response ONLY on the provided manual context and images
- If the context doesn't contain enough information, say so honestly
- Always include safety warnings when relevant
- Reference specific page numbers and sections when possible
- Be specific and actionable in your solutions
- If diagrams are provided, reference them in your explanation\
"""

STREAM_SYSTEM_PROMPT = """\
You are a machine maintenance expert assistant. You help technicians \
diagnose problems and find solutions using information from machine manuals.

Respond in clear, well-structured markdown. Use the following sections when relevant:

## Diagnosis
Provide a comprehensive explanation of the diagnosis and solution.

## Possible Issues
- List each possible issue as a bullet point

## Recommended Solutions
1. List step-by-step solutions as numbered items

## ⚠️ Safety Warnings
- List any safety precautions as bullet points

Rules:
- Base your response ONLY on the provided manual context and images
- If the context doesn't contain enough information, say so honestly
- Always include safety warnings when relevant
- Reference specific page numbers and sections when possible
- Be specific and actionable in your solutions
- If diagrams are provided, reference them in your explanation

Markdown Spacing Constraints (CRITICAL):
- Every heading (e.g. `## Diagnosis`) MUST be on its own line. Do NOT write any description or text on the same line as a heading.
- Always put a blank line BEFORE and AFTER every heading.
- Separate paragraphs and lists with a blank line to ensure readable spacing.
- Use standard sentence casing (do NOT write in ALL CAPS).
"""

USER_PROMPT_TEMPLATE = """\
CONTEXT FROM MANUAL:
{context}

---

USER'S PROBLEM:
{query}

Analyze the manual context (including any attached diagrams/images) and \
provide a structured diagnosis. Identify possible issues, recommend \
solutions, and note any safety warnings. Always reference the specific \
manual pages and sections.\
"""


class Generator:
    """Generates diagnostic responses using Ollama's vision model."""

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

    def _build_context(self, chunks: list[RetrievedChunk]) -> str:
        """
        Build a text context string from retrieved chunks.

        Includes source attribution for each chunk.
        """
        context_parts = []
        for i, rc in enumerate(chunks, 1):
            chunk = rc.chunk
            source_info = f"[Source: {chunk.source_file}, " f"Page {chunk.page_number}"
            if chunk.section_header:
                source_info += f", Section: {chunk.section_header}"
            source_info += f", Type: {chunk.content_type}]"

            context_parts.append(f"--- Excerpt {i} {source_info} ---\n{chunk.content}")

        return "\n\n".join(context_parts)

    def _collect_images(
        self, chunks: list[RetrievedChunk], max_images: int | None = None
    ) -> list[bytes]:
        """
        Collect unique page images from the retrieved chunks.

        Limits to max_images to avoid overloading the VLM context.
        Pass 0 (via settings.max_generation_images) for text-only generation.
        """
        limit = settings.max_generation_images if max_images is None else max_images
        if limit <= 0:
            logger.debug("max_generation_images=%s — skipping image collection", limit)
            return []

        seen_paths: set[str] = set()
        images: list[bytes] = []

        for rc in chunks:
            if len(images) >= limit:
                break

            # Prefer page image path, fall back to image path
            stored = rc.chunk.page_image_path or rc.chunk.image_path
            if not stored or stored in seen_paths:
                continue

            path = resolve_stored_image_path(stored)
            if path is None:
                logger.warning("Image not found: %s", stored)
                continue

            try:
                image = load_image(path)
                image = resize_image(image, self.max_resolution)
                img_bytes = image_to_bytes(image, format="PNG")
                images.append(img_bytes)
                seen_paths.add(stored)
            except Exception as e:
                logger.warning("Failed to load image %s: %s", stored, e)
                continue

        logger.debug("Collected %s images for generation", len(images))
        return images

    def _parse_response(self, raw_response: str) -> dict:
        """
        Parse the LLM's response, extracting structured fields.

        Attempts to parse as JSON first; falls back to using the
        raw text as the answer if JSON parsing fails.
        """
        # Try to extract JSON from the response
        try:
            # The model might wrap JSON in markdown code blocks
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                # Remove markdown code fences
                lines = cleaned.split("\n")
                # Remove first and last lines if they're code fences
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines)

            parsed = json.loads(cleaned)
            return {
                "answer": parsed.get("answer", raw_response),
                "possible_issues": parsed.get("possible_issues", []),
                "recommended_solutions": parsed.get("recommended_solutions", []),
                "safety_warnings": parsed.get("safety_warnings", []),
            }
        except (json.JSONDecodeError, AttributeError):
            logger.debug("Could not parse response as JSON, using raw text")
            return {
                "answer": raw_response,
                "possible_issues": [],
                "recommended_solutions": [],
                "safety_warnings": [],
            }

    async def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
    ) -> dict:
        """
        Generate a diagnostic response using the VLM.

        Sends the retrieved text context and associated page images
        to the vision model for a comprehensive answer.

        Args:
            query: The user's problem description.
            chunks: Reranked retrieved chunks with context.

        Returns:
            Dict with keys: answer, possible_issues,
            recommended_solutions, safety_warnings.
        """
        # Build text context
        context = self._build_context(chunks)

        # Collect relevant images
        images = self._collect_images(chunks)

        # Build the user message
        user_content = USER_PROMPT_TEMPLATE.format(context=context, query=query)

        # Construct messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": user_content,
                "images": images if images else None,
            },
        ]

        # Remove None images key if no images
        if not images:
            del messages[1]["images"]

        logger.info(
            f"Generating response for query: {query[:80]}... "
            f"({len(chunks)} chunks, {len(images)} images)"
        )

        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={"num_ctx": self.num_ctx},
            )
            raw_answer = response.message.content
            parsed = self._parse_response(raw_answer)

            logger.info(
                f"Generated response: {len(parsed['answer'])} chars, "
                f"{len(parsed['possible_issues'])} issues, "
                f"{len(parsed['recommended_solutions'])} solutions"
            )

            return parsed

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise

    async def generate_stream(
        self,
        query: str,
        chunks: list[RetrievedChunk],
    ):
        """
        Generate a streaming response using the VLM.

        Uses a natural-language markdown prompt (STREAM_SYSTEM_PROMPT)
        instead of JSON for faster, unconstrained generation.

        Yields text tokens as they are generated.

        Args:
            query: The user's problem description.
            chunks: Retrieved chunks with context.

        Yields:
            String tokens as they are generated.
        """
        context = self._build_context(chunks)
        images = self._collect_images(chunks)

        user_content = USER_PROMPT_TEMPLATE.format(context=context, query=query)

        messages = [
            {"role": "system", "content": STREAM_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": user_content,
                "images": images if images else None,
            },
        ]

        if not images:
            del messages[1]["images"]

        try:
            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options={"num_ctx": self.num_ctx},
            )

            for chunk in stream:
                if chunk.message.content:
                    yield chunk.message.content

        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            raise
