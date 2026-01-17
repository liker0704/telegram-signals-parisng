"""Gemini API translation service."""

import threading
from typing import Optional

import google.generativeai as genai

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configure Gemini
genai.configure(api_key=config.GEMINI_API_KEY)

_model = None
_model_lock = threading.Lock()


def get_model() -> genai.GenerativeModel:
    """Get or create Gemini model instance (thread-safe)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = genai.GenerativeModel(config.GEMINI_MODEL)
    return _model


def gemini_translate(text: str) -> Optional[str]:
    """Translate text using Gemini API with error handling."""
    if not text or not text.strip():
        return text

    try:
        model = get_model()
        prompt = f'''Translate the following trading signal text from Russian to English.
Keep all trading terms, numbers, ticker symbols, and formatting intact.
Only translate the Russian text to English.

Text to translate:
{text}

Return ONLY the translated text, nothing else.'''

        response = model.generate_content(prompt)

        if response is None:
            logger.warning("Gemini returned None response")
            return None

        if not hasattr(response, 'text') or response.text is None:
            logger.warning("Gemini response has no text")
            return None

        translated = response.text.strip()
        if not translated:
            logger.warning("Gemini returned empty translation")
            return None

        return translated

    except Exception as e:
        logger.error("Gemini translation failed", error=str(e), text_len=len(text))
        return None
