"""Image text editor using Gemini 3 Pro Image API."""

import asyncio
import os
from io import BytesIO
from typing import Optional

from PIL import Image
from google import genai
from google.genai import types

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Lazy-loaded client
_client = None


def get_client() -> genai.Client:
    """Get or create Gemini client instance."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def edit_image_text_sync(image_path: str, output_path: str) -> Optional[str]:
    """
    Edit image: translate Russian text to English.

    Synchronous version - use edit_image_text() for async.

    Args:
        image_path: Path to original image
        output_path: Path to save edited image

    Returns:
        Path to edited image, or None if editing failed
    """
    if not os.path.exists(image_path):
        logger.error("Image file not found", path=image_path)
        return None

    logger.info("Starting image text editing", image_path=image_path)

    try:
        # Load image
        image = Image.open(image_path)

        client = get_client()

        prompt = '''Analyze this trading chart/signal image.

TASK: Find any Russian text on the image and replace it with English translation.

RULES:
1. Keep ALL numbers, prices, percentages EXACTLY as they are
2. Keep ALL chart elements, lines, candles, colors unchanged
3. Keep ticker symbols (BTC/USDT, ETH/USDT etc) unchanged
4. ONLY translate Russian words to English
5. Maintain the same text positions and styling

Common translations:
- "Вход" → "Entry"
- "Стоп" / "СЛ" → "SL" (Stop Loss)
- "Тейк" / "ТП" → "TP" (Take Profit)
- "Лонг" → "Long"
- "Шорт" → "Short"
- "Цель" → "Target"
- "Позиция активна" → "Position Active"
- "Сигнал открыт" → "Signal Open"
- "Прибыль зафиксирована" → "Profit Taken"

If there is NO Russian text on the image, return the image unchanged.

Generate the edited image.'''

        response = client.models.generate_content(
            model=config.GEMINI_IMAGE_MODEL,
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE']
            )
        )

        # Log response structure for debugging
        logger.info("Gemini response received",
                    num_parts=len(response.candidates[0].content.parts) if response.candidates else 0)

        # Extract generated image using SDK's as_image() method
        for i, part in enumerate(response.candidates[0].content.parts):
            if part.text is not None:
                logger.info("Response contains text", part_index=i, text_preview=part.text[:100])
            if part.inline_data is not None:
                mime_type = getattr(part.inline_data, 'mime_type', 'unknown')
                data_size = len(part.inline_data.data) if part.inline_data.data else 0
                logger.info("Response contains inline_data",
                           part_index=i, mime_type=mime_type, data_size=data_size)

                # Check if it's an image
                if mime_type and mime_type.startswith('image/'):
                    # Use SDK's as_image() method which handles base64 decoding
                    try:
                        edited_image = part.as_image()
                        edited_image.save(output_path)
                        logger.info("Image edited successfully", output_path=output_path)
                        return output_path
                    except AttributeError:
                        # Fallback: try manual base64 decoding
                        import base64
                        decoded_data = base64.b64decode(part.inline_data.data)
                        edited_image = Image.open(BytesIO(decoded_data))
                        edited_image.save(output_path)
                        logger.info("Image edited successfully (fallback)", output_path=output_path)
                        return output_path
                else:
                    logger.warning("inline_data is not an image", mime_type=mime_type)

        logger.warning("No image in response, returning None")
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
        Path to edited image, or None if editing failed (use original as fallback)
    """
    try:
        result = await asyncio.to_thread(edit_image_text_sync, image_path, output_path)
        return result
    except Exception as e:
        logger.error("Async image editing failed", error=str(e), path=image_path)
        return None
