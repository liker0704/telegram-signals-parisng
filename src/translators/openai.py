"""OpenAI API translation service."""

import threading
from typing import Optional
from openai import OpenAI

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

_client = None
_client_lock = threading.Lock()


def get_client() -> Optional[OpenAI]:
    """Get or create OpenAI client instance (thread-safe)."""
    global _client

    # Check if API key is configured
    if not config.OPENAI_API_KEY:
        logger.warning("OpenAI API key not configured")
        return None

    if _client is None:
        with _client_lock:
            if _client is None:
                _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def openai_translate(text: str) -> Optional[str]:
    """Translate text using OpenAI API with error handling."""
    if not text or not text.strip():
        return text

    try:
        client = get_client()
        if client is None:
            return None

        prompt = f'''Translate the following trading signal text from Russian to English.
Keep all trading terms, numbers, ticker symbols, and formatting intact.
Only translate the Russian text to English.

Text to translate:
{text}

Return ONLY the translated text, nothing else.'''

        response = client.chat.completions.create(
            model=config.OPENAI_TRANSLATE_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=config.OPENAI_TRANSLATE_MAX_TOKENS
        )

        if response is None:
            logger.warning("OpenAI returned None response")
            return None

        if not response.choices or len(response.choices) == 0:
            logger.warning("OpenAI response has no choices")
            return None

        translated = response.choices[0].message.content
        if not translated or not translated.strip():
            logger.warning("OpenAI returned empty translation")
            return None

        return translated.strip()

    except Exception as e:
        logger.error("OpenAI translation failed", error=str(e), text_len=len(text))
        return None
