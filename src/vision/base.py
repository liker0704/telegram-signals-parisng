"""
Base abstractions for vision providers in the telegram-signals-parsing project.

This module provides the foundation for implementing various vision/OCR providers
that can extract and translate text from images. All providers must implement
the VisionProvider abstract base class.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from PIL import Image

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class TextExtraction:
    """
    Represents a single text extraction from an image.

    Attributes:
        original: The original text extracted from the image
        translated: The translated version of the text (or same as original if no translation)
        confidence: Confidence score of the extraction (0.0 to 1.0), defaults to 1.0
    """

    original: str
    translated: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        """Validate confidence score is within valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class VisionResult:
    """
    Result from a vision provider's text extraction operation.

    Attributes:
        extractions: List of text extractions from the image
        provider_name: Name of the vision provider that generated this result
        raw_response: Optional raw response from the provider API (for debugging)
        latency_ms: Time taken for the extraction in milliseconds
    """

    extractions: List[TextExtraction]
    provider_name: str
    raw_response: Optional[str] = None
    latency_ms: float = 0.0

    def __post_init__(self) -> None:
        """Validate that extractions list is not empty."""
        if not self.extractions:
            logger.warning(
                "VisionResult created with empty extractions list",
                provider=self.provider_name
            )

    @property
    def has_text(self) -> bool:
        """Check if any text was extracted."""
        return len(self.extractions) > 0 and any(
            ext.original.strip() or ext.translated.strip()
            for ext in self.extractions
        )

    @property
    def combined_original(self) -> str:
        """Get all original texts combined with newlines."""
        return "\n".join(ext.original for ext in self.extractions if ext.original.strip())

    @property
    def combined_translated(self) -> str:
        """Get all translated texts combined with newlines."""
        return "\n".join(ext.translated for ext in self.extractions if ext.translated.strip())

    @property
    def average_confidence(self) -> float:
        """Calculate average confidence across all extractions."""
        if not self.extractions:
            return 0.0
        return sum(ext.confidence for ext in self.extractions) / len(self.extractions)


# ============================================================================
# Exceptions
# ============================================================================


class VisionProviderError(Exception):
    """
    Base exception for all vision provider errors.

    This exception is raised when a vision provider encounters an error during
    text extraction, translation, or any other operation.
    """

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        """
        Initialize the exception.

        Args:
            message: Error message describing what went wrong
            provider: Optional name of the provider that raised the error
        """
        self.provider = provider
        super().__init__(message)

    def __str__(self) -> str:
        """Format error message with provider name if available."""
        if self.provider:
            return f"[{self.provider}] {super().__str__()}"
        return super().__str__()


# ============================================================================
# Abstract Base Class
# ============================================================================


class VisionProvider(ABC):
    """
    Abstract base class for vision/OCR providers.

    All vision providers must implement this interface to ensure consistent
    behavior across different implementations (Gemini, Tesseract, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the name of this vision provider.

        Returns:
            str: Provider name (e.g., "gemini", "tesseract", "paddleocr")
        """
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available and configured.

        Returns:
            bool: True if provider is available, False otherwise
        """
        pass

    @abstractmethod
    async def extract_text(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """
        Extract and optionally translate text from an image (async).

        Args:
            image: PIL Image object to extract text from
            prompt: Optional custom prompt for the vision model

        Returns:
            VisionResult: Result containing extracted/translated text and metadata

        Raises:
            VisionProviderError: If extraction fails
        """
        pass

    def extract_text_sync(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """
        Synchronous wrapper for extract_text.

        This method runs the async extract_text in a new event loop.
        Useful for synchronous contexts or compatibility with sync code.

        Args:
            image: PIL Image object to extract text from
            prompt: Optional custom prompt for the vision model

        Returns:
            VisionResult: Result containing extracted/translated text and metadata

        Raises:
            VisionProviderError: If extraction fails
        """
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_running_loop()
                # If we're already in an async context, use run_until_complete
                if loop.is_running():
                    logger.warning(
                        "extract_text_sync called from async context, using asyncio.to_thread",
                        provider=self.name
                    )
                    # This shouldn't happen in normal usage but handle it gracefully
                    return asyncio.run(self.extract_text(image, prompt))
            except RuntimeError:
                # No running loop, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run the async method
            return loop.run_until_complete(self.extract_text(image, prompt))

        except Exception as e:
            logger.error(
                "Synchronous extraction failed",
                provider=self.name,
                error=str(e)
            )
            raise VisionProviderError(
                f"Synchronous extraction failed: {str(e)}",
                provider=self.name
            ) from e

    def _measure_latency(self, func):
        """
        Decorator to measure execution latency of a function.

        This is a helper method for providers to track latency metrics.

        Args:
            func: Async function to measure

        Returns:
            Wrapped function that measures latency
        """
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(
                    "Operation completed",
                    provider=self.name,
                    latency_ms=round(latency_ms, 2)
                )
                return result
            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    "Operation failed",
                    provider=self.name,
                    latency_ms=round(latency_ms, 2),
                    error=str(e)
                )
                raise

        return wrapper
