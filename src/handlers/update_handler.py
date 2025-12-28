"""Handler for signal updates (replies to existing signals)."""

import asyncio
from datetime import datetime

from telethon.events import NewMessage

from src.config import config
from src.utils.logger import get_logger
from src.utils.text_cleaner import strip_promo_content
from src.formatters.message import build_final_message
from src.translators.fallback import translate_text_with_fallback
from src.ocr import process_image
from src.media.downloader import download_and_process_media, cleanup_media
from src.db.queries import (
    db_find_signal_by_source_msg,
    db_insert_signal_update,
    db_update_signal_update,
    db_find_update_by_source_msg
)
from src.telethon_setup import get_publisher_client
from src.handlers.forward_helper import forward_original_message, is_forwarding_enabled

logger = get_logger(__name__)


async def handle_signal_update(event: NewMessage.Event) -> None:
    """
    Process a reply to an existing #Идея signal.

    This maintains message threading between source and target groups.

    Pipeline:
    1. Find parent signal in DB
    2. If not found, ignore (orphan reply)
    3. Create update record
    4. Download media (if present)
    5. Translate text + OCR
    6. Build message
    7. Post as reply to target signal
    8. Update DB
    9. Cleanup

    Args:
        event: Telethon NewMessage event (must be a reply)
    """
    message = event.message
    # Idempotency check - skip if already processed
    existing_update = await db_find_update_by_source_msg(
        source_chat_id=message.chat_id,
        source_message_id=message.id
    )
    if existing_update:
        logger.info("Signal update already processed, skipping",
                   source_msg_id=message.id)
        return

    update_id = None
    media_info = None
    edited_image_path = None

    try:
        # Step 1: Find parent signal
        parent_msg_id = message.reply_to_msg_id
        if not parent_msg_id:
            logger.debug("Message is not a reply, ignoring")
            return

        parent_signal = await db_find_signal_by_source_msg(
            source_chat_id=message.chat_id,
            source_message_id=parent_msg_id
        )

        # Step 2: Check if parent exists
        if not parent_signal:
            logger.debug("Reply to unknown signal, ignoring",
                        parent_msg_id=parent_msg_id)
            return

        # Check if parent was successfully posted
        if not parent_signal.get('target_message_id'):
            logger.warning("Parent signal was not posted to target",
                          signal_id=parent_signal['id'])
            return

        # Get parent's forward message ID for threading
        parent_forward_msg_id = parent_signal.get('forward_message_id')

        logger.info("Processing signal update",
                    source_msg_id=message.id,
                    parent_signal_id=parent_signal['id'])

        # Step 3: Create update record
        update_data = {
            'signal_id': parent_signal['id'],
            'source_chat_id': message.chat_id,
            'source_message_id': message.id,
            'source_user_id': message.sender_id,
            'original_text': message.text or '',
            'status': 'PROCESSING',
            'created_at': message.date or datetime.utcnow()
        }
        update_id = await db_insert_signal_update(update_data)
        logger.info("Created update record", update_id=update_id)

        # Step 4: Download media
        reader_client = event.client
        media_info = await download_and_process_media(
            client=reader_client,
            message=message,
            entity_id=update_id,
            is_update=True
        )

        if media_info:
            await db_update_signal_update(update_id, {
                'image_local_path': media_info['local_path']
            })

        # Step 5: Clean text and prepare parallel tasks
        clean_text = strip_promo_content(message.text or '')
        translation_task = translate_text_with_fallback(clean_text)
        image_edit_task = (
            process_image(media_info['local_path'])
            if media_info else asyncio.sleep(0)
        )

        # Forward original reply (threaded to parent forward if exists)
        forward_task = (
            forward_original_message(
                original_text=message.text or '',
                media_path=media_info['local_path'] if media_info else None,
                reply_to_forward_id=parent_forward_msg_id  # Thread to parent
            )
            if is_forwarding_enabled() else asyncio.sleep(0)
        )

        results = await asyncio.gather(
            translation_task,
            image_edit_task,
            forward_task,
            return_exceptions=True
        )

        translated_text = results[0] if not isinstance(results[0], Exception) else clean_text
        edited_image_path = results[1] if not isinstance(results[1], Exception) else None

        # Handle forward result
        forward_msg_id = None
        if is_forwarding_enabled() and len(results) > 2:
            forward_result = results[2]
            if not isinstance(forward_result, Exception) and forward_result:
                forward_msg_id, forward_error = forward_result
                if forward_error:
                    logger.warning("Forward failed", error=forward_error)

        if isinstance(results[0], Exception):
            logger.error("Translation failed for update", error=str(results[0]))

        # Step 6: Build message
        final_message = build_final_message(
            translated_text=translated_text
        )

        # Step 7: Post as reply to target signal
        publisher = get_publisher_client()

        image_to_send = edited_image_path or (media_info['local_path'] if media_info else None)

        posted_msg = await asyncio.wait_for(
            publisher.send_message(
                entity=config.TARGET_GROUP_ID,
                message=final_message,
                file=image_to_send,
                reply_to=parent_signal['target_message_id']  # KEY: maintain threading
            ),
            timeout=config.TIMEOUT_TELEGRAM_SEC
        )

        target_msg_id = posted_msg.id
        logger.info("Posted update to target",
                    update_id=update_id,
                    target_msg_id=target_msg_id,
                    reply_to=parent_signal['target_message_id'])

        # Step 8: Update DB
        await db_update_signal_update(update_id, {
            'target_chat_id': config.TARGET_GROUP_ID,
            'target_message_id': target_msg_id,
            'translated_text': translated_text,
            'image_ocr_text': None,  # No longer using OCR
            'status': 'POSTED',
            'processed_at': datetime.utcnow(),
            'forward_chat_id': config.FORWARD_GROUP_ID if forward_msg_id else None,
            'forward_message_id': forward_msg_id,
        })

    except Exception as e:
        logger.error("Error processing signal update",
                     update_id=update_id,
                     error=str(e),
                     exc_info=True)

        if update_id:
            await db_update_signal_update(update_id, {
                'status': 'ERROR_POSTING_FAILED',
                'error_message': str(e)
            })

    finally:
        # Step 9: Cleanup with error handling
        if media_info and media_info.get('local_path'):
            try:
                cleanup_media(media_info['local_path'])
            except Exception as cleanup_err:
                logger.warning("Failed to cleanup media", error=str(cleanup_err))

        if edited_image_path:
            try:
                cleanup_media(edited_image_path)
            except Exception as cleanup_err:
                logger.warning("Failed to cleanup edited image", error=str(cleanup_err))
