"""
Image text editor using multi-provider vision and image editing.

Simple two-stage pipeline:
- Stage 1: Vision provider extracts and translates text
- Stage 2: Image editor generates new image with translations
"""

import asyncio
import concurrent.futures
import os
from typing import Dict, List, Optional

from PIL import Image

from src.config import config
from src.image_editing.factory import ImageEditorFactory
from src.utils.logger import get_logger
from src.utils.security import validate_image_file
from src.vision import FallbackChain
from src.vision.factory import VisionProviderFactory

logger = get_logger(__name__)

# Lazy-loaded vision chain
_vision_chain = None
_vision_chain_lock = asyncio.Lock()


async def get_vision_chain() -> Optional[FallbackChain]:
    """Get or create vision provider chain (thread-safe)."""
    global _vision_chain

    if _vision_chain is None:
        async with _vision_chain_lock:
            if _vision_chain is None:
                try:
                    providers = []

                    # Primary provider
                    try:
                        primary_provider = VisionProviderFactory.get_provider(config.VISION_PROVIDER)
                        if primary_provider.is_available:
                            providers.append(primary_provider)
                            logger.info("Primary vision provider loaded", provider=config.VISION_PROVIDER)
                        else:
                            logger.warning("Primary vision provider not available", provider=config.VISION_PROVIDER)
                    except Exception as e:
                        logger.warning("Failed to get primary vision provider",
                                     provider=config.VISION_PROVIDER, error=str(e))

                    # Fallback providers
                    for name in config.vision_fallback_list:
                        try:
                            fallback_provider = VisionProviderFactory.get_provider(name)
                            if fallback_provider.is_available and fallback_provider not in providers:
                                providers.append(fallback_provider)
                                logger.info("Fallback vision provider loaded", provider=name)
                        except Exception as e:
                            logger.debug("Fallback provider not available", provider=name, error=str(e))

                    if providers:
                        _vision_chain = FallbackChain(
                            providers,
                            timeout_sec=config.VISION_TIMEOUT_SEC,
                            max_retries=config.VISION_MAX_RETRIES
                        )
                        logger.info("Vision chain created",
                                  num_providers=len(providers),
                                  providers=[p.name for p in providers])
                    else:
                        logger.warning("No vision providers available, vision chain not created")

                except Exception as e:
                    logger.error("Failed to create vision chain", error=str(e))

    return _vision_chain


async def extract_text_from_image(image: Image.Image) -> List[Dict[str, str]]:
    """
    Extract and translate text from image using vision chain.

    Args:
        image: PIL Image object

    Returns:
        List of dicts with 'russian' and 'english' keys
    """
    chain = await get_vision_chain()

    if not chain:
        logger.error("Vision chain not available for text extraction")
        return []

    try:
        logger.info("Extracting text with vision chain")
        result = await chain.extract_text(image)

        if result and result.extractions:
            # Convert VisionResult extractions to expected format
            translations = [
                {"russian": extraction.original, "english": extraction.translated}
                for extraction in result.extractions
                if extraction.original and extraction.translated
            ]

            if translations:
                logger.info("Vision chain extraction successful",
                          count=len(translations),
                          provider=result.provider_name,
                          translations=[f"{t['russian']} -> {t['english']}" for t in translations[:5]])
                return translations
            else:
                logger.warning("Vision chain returned empty extractions")
        else:
            logger.warning("Vision chain returned no result or extractions")

    except Exception as e:
        logger.error("Vision chain extraction failed", error=str(e), error_type=type(e).__name__)

    return []


def _run_async(coro):
    """
    Run async coroutine from sync context safely.

    Handles two scenarios:
    1. If already in async context (event loop running) - creates new loop in thread
    2. If in sync context - uses asyncio.run()

    Args:
        coro: Coroutine to execute

    Returns:
        Result of coroutine execution
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in async context - create new loop in thread to avoid conflict
        logger.debug("Running coroutine in thread pool (async context detected)")
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        # Sync context - safe to use asyncio.run()
        logger.debug("Running coroutine with asyncio.run (sync context)")
        return asyncio.run(coro)


def edit_image_text_sync(image_path: str, output_path: str) -> Optional[str]:
    """
    Edit image: translate Russian text to English using vision + image editing.

    Stage 1: Vision provider extracts and translates text
    Stage 2: Image editor generates new image with translations

    Args:
        image_path: Path to original image
        output_path: Path to save edited image

    Returns:
        Path to edited image, or None if editing failed
    """
    # Validate image
    if not validate_image_file(image_path):
        logger.error("Invalid or unsafe image path", path=image_path)
        return None

    if not os.path.exists(image_path):
        logger.error("Image file not found", path=image_path)
        return None

    logger.info("Starting image text editing", image_path=image_path)

    try:
        # Load image
        with Image.open(image_path) as img:
            image = img.convert('RGB')

            # Upscale small images for better OCR accuracy
            min_dimension = 1024
            width, height = image.size

            if width < min_dimension or height < min_dimension:
                scale = max(min_dimension / width, min_dimension / height)
                new_size = (int(width * scale), int(height * scale))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                logger.info("Upscaled image for OCR", original=(width, height), new=new_size)

            # Stage 1: Extract translations using vision chain
            logger.info("Stage 1: Extracting translations with vision chain")
            translations_list = _run_async(extract_text_from_image(image))

            if not translations_list:
                logger.warning("No translations extracted from image")
                return None

            # Convert to dict format: {russian_text: english_text}
            translations_dict = {
                t['russian']: t['english']
                for t in translations_list
            }

            logger.info("Stage 1 complete",
                       num_translations=len(translations_dict),
                       translations=list(translations_dict.items())[:5])

        # Stage 2: Generate edited image using image editor
        logger.info("Stage 2: Generating edited image with image editor")

        # Get image editor with fallback
        try:
            editor = ImageEditorFactory.get_editor_with_fallback()
            logger.info("Image editor ready", editor=editor.name)
        except Exception as e:
            logger.error("Failed to get image editor", error=str(e))
            return None

        # Edit image
        result = editor.edit_image(
            image_path=image_path,
            translations=translations_dict,
            output_path=output_path
        )

        if result.success and result.edited_image:
            # Save edited image if not already saved
            if not os.path.exists(output_path):
                result.edited_image.save(output_path)
                logger.info("Edited image saved", output_path=output_path)

            logger.info("Image editing successful",
                       output_path=output_path,
                       method=result.method)
            return output_path
        else:
            logger.warning("Image editing failed",
                         error=result.error,
                         method=result.method)
            return None

    except Exception as e:
        logger.error("Image editing failed", error=str(e), path=image_path)
        return None


async def edit_image_text(image_path: str, output_path: str) -> Optional[str]:
    """
    Async wrapper for image text editing.

    Args:
        image_path: Path to original image
        output_path: Path to save edited image

    Returns:
        Path to edited image, or None if editing failed
    """
    try:
        result = await asyncio.to_thread(edit_image_text_sync, image_path, output_path)
        return result
    except Exception as e:
        logger.error("Async image editing failed", error=str(e), path=image_path)
        return None
