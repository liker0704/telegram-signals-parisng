"""
Vision providers module for text extraction from images.

This module provides a unified interface for different vision/OCR providers
to extract and translate text from images. All providers implement the
VisionProvider abstract base class.

Public API:
    - VisionProvider: Abstract base class for all providers
    - TextExtraction: Data class for extracted text
    - VisionResult: Data class for extraction results
    - VisionProviderError: Exception for provider errors
    - FallbackChain: Orchestrates fallback between multiple providers
"""

from src.vision.base import (
    TextExtraction,
    VisionProvider,
    VisionProviderError,
    VisionResult,
)
from src.vision.fallback import FallbackChain
from src.vision.factory import VisionProviderFactory

__all__ = [
    "VisionProvider",
    "VisionProviderFactory",
    "TextExtraction",
    "VisionResult",
    "VisionProviderError",
    "FallbackChain",
]
