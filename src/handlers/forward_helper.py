"""Helper functions for parallel forwarding of original messages to forward group."""

import asyncio
from typing import Optional, Tuple

from src.config import config
from src.telethon_setup import get_publisher_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


def is_forwarding_enabled() -> bool:
    """Check if forwarding is enabled in configuration."""
    return config.FORWARD_GROUP_ID is not None


async def forward_original_message(
    original_text: str,
    media_path: Optional[str],
    reply_to_forward_id: Optional[int] = None
) -> Tuple[Optional[int], Optional[str]]:
    """
    Forward original message (without translation) to the forward group.

    Uses send_message (not forward_messages) to avoid "Forwarded from" label.

    Args:
        original_text: Original untranslated text
        media_path: Path to original media file, or None
        reply_to_forward_id: Message ID in forward group to reply to (for threading)

    Returns:
        Tuple of (forward_message_id, error_message)
        - (int, None) on success
        - (None, None) if forwarding disabled
        - (None, str) on failure
    """
    if not config.FORWARD_GROUP_ID:
        return None, None

    try:
        publisher = get_publisher_client()

        posted_msg = await asyncio.wait_for(
            publisher.send_message(
                entity=config.FORWARD_GROUP_ID,
                message=original_text,
                file=media_path,
                reply_to=reply_to_forward_id
            ),
            timeout=config.TIMEOUT_TELEGRAM_SEC
        )

        logger.info("Forwarded original to forward group",
                    forward_msg_id=posted_msg.id,
                    reply_to=reply_to_forward_id)

        return posted_msg.id, None

    except asyncio.TimeoutError:
        error_msg = "Timeout forwarding to forward group"
        logger.warning(error_msg)
        return None, error_msg

    except Exception as e:
        error_msg = f"Failed to forward: {str(e)}"
        logger.warning(error_msg, exc_info=True)
        return None, error_msg
