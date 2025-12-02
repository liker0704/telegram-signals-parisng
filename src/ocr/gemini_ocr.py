"""Gemini Vision OCR for extracting text from trading chart images."""

import os
from typing import Optional

import google.generativeai as genai

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configure Gemini
genai.configure(api_key=config.GEMINI_API_KEY)

_model = None


def get_model() -> genai.GenerativeModel:
    """Get or create Gemini Vision model instance."""
    global _model
    if _model is None:
        _model = genai.GenerativeModel(config.GEMINI_MODEL)
    return _model


def extract_image_text(image_path: str) -> Optional[str]:
    """
    Extract and translate text from a trading chart image using Gemini Vision.

    This is a SYNCHRONOUS function.

    Args:
        image_path: Path to the image file

    Returns:
        str: Extracted and translated text, or None if no text found

    Raises:
        FileNotFoundError: If image file doesn't exist
        Exception: If OCR fails
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    logger.debug("Starting OCR", image_path=image_path)

    # Upload file to Gemini
    uploaded_file = genai.upload_file(image_path)

    prompt = '''Extract ALL visible text from this trading chart/screenshot image.
If text is visible, translate any Russian text to English.
Preserve numbers, currency symbols ($, €), and ticker symbols (e.g., BTC/USDT, %) exactly.

If NO readable text is found on the image, return exactly: NO_TEXT_FOUND

Return in this format:
EXTRACTED: [original text from image]
TRANSLATED: [english translation if needed, or same as extracted if already English]

If no text found:
EXTRACTED: (none)
TRANSLATED: (none)'''

    model = get_model()
    response = model.generate_content([prompt, uploaded_file])

    text = response.text.strip()

    # Parse response
    if "NO_TEXT_FOUND" in text or "EXTRACTED: (none)" in text:
        logger.info("No text found in image")
        return None

    # Extract translated portion
    lines = text.split('\n')
    translated = None

    for line in lines:
        if line.startswith('TRANSLATED:'):
            translated = line.replace('TRANSLATED:', '').strip()
            break

    if translated and translated != '(none)':
        logger.info("OCR complete", text_length=len(translated))
        return f"[Chart text]: {translated}"

    logger.info("No translatable text found in image")
    return None


async def translate_image_ocr(image_path: str) -> Optional[str]:
    """
    Async wrapper for image OCR extraction.

    Args:
        image_path: Path to the image file

    Returns:
        str: Extracted text formatted for message, or None
    """
    import asyncio

    try:
        result = await asyncio.to_thread(extract_image_text, image_path)
        return result
    except FileNotFoundError:
        logger.warning("Image file not found for OCR", path=image_path)
        return None
    except Exception as e:
        logger.error("OCR failed", error=str(e), path=image_path)
        return None
