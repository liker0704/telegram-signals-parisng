"""OCR services package."""

from src.ocr.gemini_ocr import translate_image_ocr, extract_image_text

__all__ = ['translate_image_ocr', 'extract_image_text']
