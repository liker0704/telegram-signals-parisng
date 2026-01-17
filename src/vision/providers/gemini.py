"""
Gemini vision provider implementation using LangChain.

This module provides Gemini-based OCR text extraction for trading chart images
using LangChain's unified interface. The provider uses gemini-2.5-flash for
vision capabilities with structured text extraction and translation.
"""

import base64
import threading
import time
from io import BytesIO
from typing import List, Optional

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from PIL import Image

from src.config import config
from src.utils.logger import get_logger
from src.vision.base import TextExtraction, VisionProvider, VisionProviderError, VisionResult
from src.vision.prompts import OCR_EXTRACTION_PROMPT

logger = get_logger(__name__)


class GeminiVisionProvider(VisionProvider):
    """
    Gemini vision provider using LangChain ChatGoogleGenerativeAI.

    This provider uses Gemini's multimodal capabilities to extract and translate
    text from trading chart images. It implements thread-safe lazy initialization
    and structured response parsing.

    Attributes:
        _model: Lazy-initialized ChatGoogleGenerativeAI instance
        _model_lock: Thread lock for safe model initialization
    """

    def __init__(self) -> None:
        """Initialize the Gemini vision provider with lazy model loading."""
        self._model: Optional[ChatGoogleGenerativeAI] = None
        self._model_lock = threading.Lock()

    @property
    def name(self) -> str:
        """Get the provider name."""
        return "gemini"

    @property
    def is_available(self) -> bool:
        """
        Check if Gemini API is available and configured.

        Returns:
            bool: True if GEMINI_API_KEY is set, False otherwise
        """
        is_available = bool(config.GEMINI_API_KEY)
        if not is_available:
            logger.warning(
                "Gemini provider not available: GEMINI_API_KEY not configured",
                provider=self.name
            )
        return is_available

    def _get_model(self) -> ChatGoogleGenerativeAI:
        """
        Get or create ChatGoogleGenerativeAI model instance (thread-safe).

        This method implements lazy initialization with thread safety using
        double-checked locking pattern.

        Returns:
            ChatGoogleGenerativeAI: Initialized model instance

        Raises:
            VisionProviderError: If model initialization fails
        """
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    try:
                        logger.debug(
                            "Initializing Gemini model",
                            provider=self.name,
                            model=config.GEMINI_MODEL
                        )
                        self._model = ChatGoogleGenerativeAI(
                            model=config.GEMINI_MODEL,
                            google_api_key=config.GEMINI_API_KEY,
                            temperature=0,
                        )
                        logger.info(
                            "Gemini model initialized successfully",
                            provider=self.name,
                            model=config.GEMINI_MODEL
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to initialize Gemini model",
                            provider=self.name,
                            error=str(e)
                        )
                        raise VisionProviderError(
                            f"Failed to initialize Gemini model: {str(e)}",
                            provider=self.name
                        ) from e
        return self._model

    def _image_to_base64(self, image: Image.Image) -> str:
        """
        Convert PIL Image to base64-encoded JPEG string.

        Args:
            image: PIL Image object to convert

        Returns:
            str: Base64-encoded JPEG image string

        Raises:
            VisionProviderError: If image conversion fails
        """
        try:
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=95)
            base64_str = base64.b64encode(buffer.getvalue()).decode()
            logger.debug(
                "Image converted to base64",
                provider=self.name,
                size_bytes=len(buffer.getvalue()),
                base64_length=len(base64_str)
            )
            return base64_str
        except Exception as e:
            logger.error(
                "Failed to convert image to base64",
                provider=self.name,
                error=str(e)
            )
            raise VisionProviderError(
                f"Failed to convert image to base64: {str(e)}",
                provider=self.name
            ) from e

    def _parse_response(self, raw_text: str) -> List[TextExtraction]:
        """
        Parse LLM response into structured TextExtraction objects.

        Expected format from LLM:
            ORIGINAL: <original text> -> ENGLISH: <translated text>

        Args:
            raw_text: Raw text response from Gemini

        Returns:
            List[TextExtraction]: Parsed text extractions with translations
        """
        extractions = []

        logger.debug(
            "Parsing vision response",
            provider=self.name,
            raw_length=len(raw_text)
        )

        # Handle NO_TEXT_FOUND case
        if "NO_TEXT_FOUND" in raw_text:
            logger.info(
                "No text found in image",
                provider=self.name
            )
            return extractions

        for line_num, line in enumerate(raw_text.split('\n'), 1):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Normalize Unicode arrows to ASCII for consistent parsing
            normalized_line = line.replace("→", "->").replace("➔", "->").replace("⟶", "->")

            # Skip lines without the arrow separator
            if '->' not in normalized_line:
                continue

            # Format: "ORIGINAL: text -> ENGLISH: translation"
            if 'ORIGINAL:' in normalized_line and 'ENGLISH:' in normalized_line:
                try:
                    parts = normalized_line.split('->', 1)  # Split only on first arrow
                    if len(parts) != 2:
                        continue

                    original = parts[0].replace('ORIGINAL:', '').strip()
                    english = parts[1].replace('ENGLISH:', '').strip()

                    # Only add if we have both original and english text
                    if original and english:
                        extractions.append(
                            TextExtraction(
                                original=original,
                                translated=english,
                                confidence=1.0
                            )
                        )
                        logger.debug(
                            "Parsed text extraction",
                            provider=self.name,
                            line_num=line_num,
                            original=original[:50],  # Log first 50 chars
                            translated=english[:50]
                        )
                    else:
                        logger.warning(
                            "Skipping extraction with empty text",
                            provider=self.name,
                            line_num=line_num,
                            line=line[:100]
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to parse extraction line",
                        provider=self.name,
                        line_num=line_num,
                        line=line[:100],
                        error=str(e)
                    )
                    continue

        logger.info(
            "Response parsing complete",
            provider=self.name,
            extractions_found=len(extractions)
        )

        return extractions

    async def extract_text(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """
        Extract and translate text from an image using Gemini vision API.

        This method:
        1. Converts PIL Image to base64 JPEG
        2. Creates HumanMessage with text prompt and image
        3. Invokes Gemini model asynchronously
        4. Parses response into structured TextExtraction objects
        5. Returns VisionResult with latency metrics

        Args:
            image: PIL Image object to extract text from
            prompt: Optional custom prompt (defaults to OCR_EXTRACTION_PROMPT)

        Returns:
            VisionResult: Result containing extracted/translated text and metadata

        Raises:
            VisionProviderError: If extraction fails or API error occurs
        """
        start_time = time.perf_counter()

        if not self.is_available:
            raise VisionProviderError(
                "Gemini provider is not available (missing API key)",
                provider=self.name
            )

        try:
            logger.info(
                "Starting text extraction",
                provider=self.name,
                image_size=image.size,
                has_custom_prompt=bool(prompt)
            )

            # Get model instance
            model = self._get_model()

            # Convert image to base64
            base64_image = self._image_to_base64(image)

            # Create HumanMessage with text and image content
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt or OCR_EXTRACTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            )

            logger.debug(
                "Invoking Gemini model",
                provider=self.name,
                message_content_blocks=len(message.content)
            )

            # Invoke model asynchronously
            response = await model.ainvoke([message])
            raw_text = response.content

            if not raw_text:
                logger.warning(
                    "Gemini returned empty response",
                    provider=self.name
                )
                raise VisionProviderError(
                    "Gemini returned empty response",
                    provider=self.name
                )

            logger.debug(
                "Received response from Gemini",
                provider=self.name,
                response_length=len(raw_text)
            )

            # Parse response into TextExtraction objects
            extractions = self._parse_response(raw_text)

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "Text extraction completed",
                provider=self.name,
                extractions_count=len(extractions),
                latency_ms=round(latency_ms, 2)
            )

            return VisionResult(
                extractions=extractions,
                provider_name=self.name,
                raw_response=raw_text,
                latency_ms=latency_ms
            )

        except VisionProviderError:
            # Re-raise VisionProviderError as-is
            raise
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Text extraction failed",
                provider=self.name,
                error=str(e),
                error_type=type(e).__name__,
                latency_ms=round(latency_ms, 2)
            )
            raise VisionProviderError(
                f"Gemini text extraction failed: {str(e)}",
                provider=self.name
            ) from e
