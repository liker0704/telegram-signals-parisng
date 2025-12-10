"""Translation fallback orchestrator with timeout handling."""

import asyncio
import hashlib
from typing import Optional

from src.config import config
from src.utils.logger import get_logger
from src.translators.gemini import gemini_translate
from src.translators.google import google_translate

logger = get_logger(__name__)

# Rate limiting for Gemini API calls
_translation_semaphore: asyncio.Semaphore = None
MAX_CONCURRENT_TRANSLATIONS = 5


def _get_semaphore() -> asyncio.Semaphore:
    """Get or create the global semaphore for rate limiting."""
    global _translation_semaphore
    if _translation_semaphore is None:
        _translation_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSLATIONS)
    return _translation_semaphore


def _hash_text(text: str) -> str:
    """Generate SHA256 hash of text for cache lookup."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


async def translate_text_with_fallback(
    text: str,
    timeout: Optional[int] = None,
    use_cache: bool = True
) -> str:
    """
    Translate text using Gemini with fallback to Google Translate.

    Strategy:
    1. Check cache for existing translation (optional)
    2. Try Gemini with timeout (rate limited)
    3. On timeout/error -> fallback to Google Translate
    4. If both fail -> return original text
    5. Cache successful translation (optional)

    Args:
        text: Russian text to translate
        timeout: Timeout in seconds (default: config.TIMEOUT_GEMINI_SEC)
        use_cache: Whether to use translation cache

    Returns:
        str: Translated English text, or original text if all methods fail
    """
    if not text or not text.strip():
        return text

    timeout = timeout or config.TIMEOUT_GEMINI_SEC
    text_hash = _hash_text(text)

    # Step 1: Check cache (optional, skip if DB not available)
    if use_cache:
        try:
            from src.db.queries import db_get_cached_translation
            cached = await db_get_cached_translation(text_hash)
            if cached:
                logger.info("Translation cache hit", text_hash=text_hash[:16])
                return cached
        except Exception as e:
            logger.debug("Cache lookup skipped", error=str(e))

    # Use semaphore for rate limiting
    semaphore = _get_semaphore()
    async with semaphore:
        translated = None
        model_used = None

        # Step 2: Try Gemini with timeout (run sync in thread)
        try:
            logger.debug("Attempting Gemini translation", timeout=timeout)
            translated = await asyncio.wait_for(
                asyncio.to_thread(gemini_translate, text),
                timeout=timeout
            )
            model_used = "gemini"
            logger.info("Gemini translation successful")

        except asyncio.TimeoutError:
            logger.warning("Gemini timeout, falling back to Google Translate",
                           timeout=timeout)
        except Exception as e:
            logger.warning("Gemini error, falling back to Google Translate",
                           error=str(e))

        # Step 3: Fallback to Google Translate
        if translated is None:
            try:
                translated = await asyncio.wait_for(
                    asyncio.to_thread(google_translate, text),
                    timeout=15
                )
                model_used = "google_translate"
                logger.info("Google Translate fallback successful")

            except Exception as e:
                logger.error("All translation methods failed", error=str(e))
                return text  # Return original as last resort

        # Step 4: Cache the translation (optional)
        if use_cache and translated and model_used:
            try:
                from src.db.queries import db_cache_translation
                await db_cache_translation(text_hash, text, translated, model_used)
                logger.debug("Translation cached", model=model_used)
            except Exception as e:
                logger.debug("Cache write skipped", error=str(e))

        return translated
