"""Google Translate fallback service."""

from googletrans import Translator

from src.utils.logger import get_logger
from src.formatters.message import restore_trading_terms

logger = get_logger(__name__)

# Singleton translator instance
_translator = None


def get_translator() -> Translator:
    """Get or create Translator instance."""
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


def google_translate(text: str) -> str:
    """
    Translate text from Russian to English using Google Translate.

    This is a SYNCHRONOUS function (googletrans is sync).

    Args:
        text: Russian text to translate

    Returns:
        str: Translated English text with trading terms restored
    """
    logger.debug("Starting Google Translate", text_length=len(text))

    translator = get_translator()
    result = translator.translate(text, src='ru', dest='en')
    translated = result.text

    # Post-process to restore trading terms
    translated = restore_trading_terms(translated)

    logger.info("Google Translate complete",
                original_length=len(text),
                translated_length=len(translated))

    return translated
