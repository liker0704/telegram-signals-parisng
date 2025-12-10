"""Security utilities for file validation."""
import imghdr
from pathlib import Path
from typing import Optional

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
ALLOWED_IMAGE_MAGIC = {'jpeg', 'png', 'gif', 'webp', 'bmp'}


def validate_file_path(file_path: str, base_dir: Optional[str] = None) -> bool:
    """Validate that file path is within allowed directory."""
    try:
        if not file_path:
            return False

        path = Path(file_path).resolve()
        allowed_base = Path(base_dir or config.MEDIA_DOWNLOAD_DIR).resolve()

        try:
            path.relative_to(allowed_base)
            return True
        except ValueError:
            logger.warning("Path traversal attempt blocked", path=file_path)
            return False
    except Exception as e:
        logger.error("Path validation error", error=str(e))
        return False


def validate_image_file(file_path: str) -> bool:
    """Validate file exists, is within allowed dir, and is a valid image."""
    if not validate_file_path(file_path):
        return False

    path = Path(file_path)

    if not path.exists():
        return False

    if path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        logger.warning("Invalid image extension", path=file_path, ext=path.suffix)
        return False

    try:
        magic = imghdr.what(file_path)
        if magic not in ALLOWED_IMAGE_MAGIC:
            logger.warning("Invalid image magic bytes", path=file_path, magic=magic)
            return False
    except Exception:
        return False

    return True
