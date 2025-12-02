"""Gemini API translation service."""

import google.generativeai as genai

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configure Gemini
genai.configure(api_key=config.GEMINI_API_KEY)

_model = None


def get_model() -> genai.GenerativeModel:
    """Get or create Gemini model instance."""
    global _model
    if _model is None:
        _model = genai.GenerativeModel(config.GEMINI_MODEL)
    return _model


def gemini_translate(text: str) -> str:
    """
    Translate text from Russian to English using Gemini API.

    This is a SYNCHRONOUS function.

    Args:
        text: Russian text to translate

    Returns:
        str: Translated English text
    """
    logger.debug("Starting Gemini translation", text_length=len(text))

    prompt = f'''Translate the following trading signal text from Russian to English.

IMPORTANT RULES:
- Keep these terms EXACTLY as is: TP1, TP2, TP3, SL, LONG, SHORT
- Keep all ticker symbols exactly as is (e.g., BTC/USDT, ETH/USDT)
- Preserve all numbers and price levels exactly
- Preserve all emojis
- Preserve line breaks and formatting structure
- Only translate descriptive Russian text to English
- Keep #Идея as #Idea

Text to translate:
{text}

Return ONLY the translated text, nothing else.'''

    model = get_model()
    response = model.generate_content(prompt)

    translated = response.text.strip()
    logger.info("Gemini translation complete",
                original_length=len(text),
                translated_length=len(translated))

    return translated
