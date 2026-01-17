"""Media downloader for Telegram messages."""

import os
from datetime import datetime
from typing import Any, Dict, Optional

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def download_and_process_media(
    client,
    message,
    entity_id: int,
    is_update: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Download media from a Telegram message.

    Args:
        client: Telethon client instance
        message: Telegram message object
        entity_id: Signal ID or Update ID for logging
        is_update: Whether this is for a signal update (reply)

    Returns:
        dict with keys:
            - local_path: Path to downloaded file
            - file_name: Original filename
            - file_size: Size in bytes
            - downloaded_at: Timestamp
        Or None if no media or download failed
    """
    # Check if message has downloadable media
    if not message.photo and not message.document:
        logger.debug("No media in message", entity_id=entity_id)
        return None

    # Ensure download directory exists
    os.makedirs(config.MEDIA_DOWNLOAD_DIR, exist_ok=True)

    try:
        # Download media
        logger.debug("Downloading media",
                     entity_id=entity_id,
                     has_photo=bool(message.photo),
                     has_document=bool(message.document))

        file_path = await message.download_media(
            file=config.MEDIA_DOWNLOAD_DIR
        )

        if not file_path:
            logger.warning("Download returned no path", entity_id=entity_id)
            return None

        # Check file size
        file_size = os.path.getsize(file_path)
        max_size = config.MAX_IMAGE_SIZE_MB * 1024 * 1024

        if file_size > max_size:
            logger.warning("Media too large, skipping",
                          entity_id=entity_id,
                          file_size_mb=file_size / (1024 * 1024),
                          max_size_mb=config.MAX_IMAGE_SIZE_MB)
            os.remove(file_path)
            return None

        result = {
            'local_path': file_path,
            'file_name': os.path.basename(file_path),
            'file_size': file_size,
            'downloaded_at': datetime.utcnow()
        }

        logger.info("Media downloaded",
                    entity_id=entity_id,
                    file_name=result['file_name'],
                    file_size_kb=file_size // 1024)

        return result

    except Exception as e:
        logger.error("Media download failed",
                     entity_id=entity_id,
                     error=str(e))
        return None


def cleanup_media(file_path: str) -> None:
    """
    Remove downloaded media file after processing.

    Args:
        file_path: Path to the file to delete
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.debug("Cleaned up media file", path=file_path)
    except Exception as e:
        logger.warning("Failed to cleanup media", path=file_path, error=str(e))
