"""Google Translate fallback service."""

import threading
from typing import Optional
from googletrans import Translator

from src.utils.logger import get_logger
from src.formatters.message import restore_trading_terms

logger = get_logger(__name__)

# Singleton translator instance
_translator = None
_translator_lock = threading.Lock()


def get_translator() -> Translator:
    """Get or create Translator instance (thread-safe)."""
    global _translator
    if _translator is None:
        with _translator_lock:
            if _translator is None:
                _translator = Translator()
    return _translator


def google_translate(text: str) -> Optional[str]:
    """Translate using Google Translate with error handling."""
    if not text or not text.strip():
        return text

    try:
        translator = get_translator()
        result = translator.translate(text, src='ru', dest='en')

        if result is None:
            logger.warning("Google Translate returned None")
            return None

        if not hasattr(result, 'text') or result.text is None:
            logger.warning("Google Translate result has no text")
            return None

        return result.text

    except Exception as e:
        logger.error("Google Translate failed", error=str(e))
        return None
