"""
Anthropic Claude Vision Provider via LangChain.

This provider uses Anthropic's Claude vision capabilities to extract and translate
text from trading chart images.
"""

import asyncio
import base64
import io
import threading
import time
from typing import List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from PIL import Image

from src.config import config
from src.utils.logger import get_logger
from src.vision.base import (
    TextExtraction,
    VisionProvider,
    VisionProviderError,
    VisionResult,
)
from src.vision.prompts import OCR_EXTRACTION_PROMPT

logger = get_logger(__name__)

# Thread-safe singleton
_client = None
_client_lock = threading.Lock()


def _get_client() -> Optional[ChatAnthropic]:
    """Get or create Anthropic client instance (thread-safe lazy initialization)."""
    global _client

    if not config.ANTHROPIC_API_KEY:
        return None

    if _client is None:
        with _client_lock:
            if _client is None:
                try:
                    _client = ChatAnthropic(
                        model=config.ANTHROPIC_VISION_MODEL,
                        api_key=config.ANTHROPIC_API_KEY,
                        temperature=0,
                    )
                    logger.info(
                        "Anthropic client initialized",
                        model=config.ANTHROPIC_VISION_MODEL
                    )
                except Exception as e:
                    logger.error("Failed to initialize Anthropic client", error=str(e))
                    return None

    return _client


class AnthropicVisionProvider(VisionProvider):
    """
    Vision provider implementation using Anthropic Claude Vision API via LangChain.

    This provider uses Claude's vision capabilities to:
    1. Extract all visible text from trading chart images
    2. Translate Russian/Cyrillic text to English
    3. Preserve formatting of numbers, symbols, and technical terms
    """

    @property
    def name(self) -> str:
        """Get provider name."""
        return "anthropic"

    @property
    def is_available(self) -> bool:
        """Check if Anthropic API key is configured."""
        return bool(config.ANTHROPIC_API_KEY)

    def _image_to_base64(self, image: Image.Image) -> str:
        """
        Convert PIL Image to base64 string for API submission.

        Args:
            image: PIL Image object

        Returns:
            Base64 encoded image string
        """
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        return base64.b64encode(img_bytes).decode("utf-8")

    def _parse_response(self, response_text: str) -> List[TextExtraction]:
        """
        Parse the OCR response into TextExtraction objects.

        Expected format:
        ORIGINAL: <text> -> ENGLISH: <translation>

        Args:
            response_text: Raw text response from the vision API

        Returns:
            List of TextExtraction objects
        """
        extractions = []

        # Check for "no text found" indicator
        if "NO_TEXT_FOUND" in response_text:
            logger.info("No text found in image (Anthropic)")
            return []

        # Parse line by line
        for line in response_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue

            # Expected format: ORIGINAL: text -> ENGLISH: translation
            if "ORIGINAL:" in line and "ENGLISH:" in line:
                try:
                    # Split by arrow
                    parts = line.split("->")
                    if len(parts) == 2:
                        original_part = parts[0].strip()
                        english_part = parts[1].strip()

                        # Extract text after colons
                        original = original_part.replace("ORIGINAL:", "").strip()
                        translated = english_part.replace("ENGLISH:", "").strip()

                        if original and translated:
                            extractions.append(
                                TextExtraction(
                                    original=original,
                                    translated=translated,
                                    confidence=1.0
                                )
                            )
                except Exception as e:
                    logger.warning(
                        "Failed to parse extraction line",
                        line=line,
                        error=str(e)
                    )
                    continue

        if not extractions:
            logger.warning(
                "No valid extractions parsed from response",
                response_preview=response_text[:200]
            )

        return extractions

    async def extract_text(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """
        Extract and translate text from image using Anthropic Claude Vision API.

        Args:
            image: PIL Image object to extract text from
            prompt: Optional custom prompt (defaults to OCR_EXTRACTION_PROMPT)

        Returns:
            VisionResult with extracted text and metadata

        Raises:
            VisionProviderError: If extraction fails
        """
        start_time = time.perf_counter()

        try:
            client = _get_client()
            if not client:
                raise VisionProviderError(
                    "Anthropic client not available (check API key)",
                    provider=self.name
                )

            # Use custom prompt or default
            extraction_prompt = prompt or OCR_EXTRACTION_PROMPT

            # Convert image to base64
            logger.debug("Converting image to base64", provider=self.name)
            image_b64 = self._image_to_base64(image)

            # Create message with image
            message = HumanMessage(
                content=[
                    {"type": "text", "text": extraction_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ]
            )

            # Call Anthropic API (run in thread to avoid blocking)
            logger.info("Calling Anthropic Vision API", model=config.ANTHROPIC_VISION_MODEL)
            response = await asyncio.to_thread(client.invoke, [message])

            # Extract response text
            response_text = response.content
            logger.debug(
                "Anthropic API response received",
                length=len(response_text),
                preview=response_text[:200]
            )

            # Parse response into extractions
            extractions = self._parse_response(response_text)

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            result = VisionResult(
                extractions=extractions,
                provider_name=self.name,
                raw_response=response_text,
                latency_ms=latency_ms
            )

            logger.info(
                "Text extraction complete",
                provider=self.name,
                extraction_count=len(extractions),
                latency_ms=round(latency_ms, 2)
            )

            return result

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Text extraction failed",
                provider=self.name,
                error=str(e),
                latency_ms=round(latency_ms, 2)
            )
            raise VisionProviderError(
                f"Anthropic vision extraction failed: {str(e)}",
                provider=self.name
            ) from e
