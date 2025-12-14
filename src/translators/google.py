"""Google Translate fallback service."""

from typing import Optional

from deep_translator import GoogleTranslator

from src.utils.logger import get_logger

logger = get_logger(__name__)


def google_translate(text: str) -> Optional[str]:
    """Translate using Google Translate with error handling."""
    if not text or not text.strip():
        return text

    try:
        translator = GoogleTranslator(source='ru', target='en')
        result = translator.translate(text)

        if result is None:
            logger.warning("Google Translate returned None")
            return None

        return result

    except Exception as e:
        logger.error("Google Translate failed", error=str(e))
        return None
