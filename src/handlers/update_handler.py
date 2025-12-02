"""Handler for signal updates (replies to existing signals)."""

from datetime import datetime
from typing import Optional

from telethon.events import NewMessage

from src.config import config
from src.utils.logger import get_logger
from src.formatters.message import build_final_message
from src.translators.fallback import translate_text_with_fallback
from src.ocr.gemini_ocr import translate_image_ocr
from src.media.downloader import download_and_process_media, cleanup_media
from src.db.queries import (
    db_find_signal_by_source_msg,
    db_insert_signal_update,
    db_update_signal_update
)
from src.telethon_setup import get_publisher_client

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
    update_id = None
    media_info = None

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

        # Step 5: Translate text + OCR
        import asyncio

        translation_task = translate_text_with_fallback(message.text or '')
        ocr_task = (
            translate_image_ocr(media_info['local_path'])
            if media_info else asyncio.sleep(0)
        )

        results = await asyncio.gather(
            translation_task,
            ocr_task,
            return_exceptions=True
        )

        translated_text = results[0] if not isinstance(results[0], Exception) else message.text
        image_ocr = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else None

        if isinstance(results[0], Exception):
            logger.error("Translation failed for update", error=str(results[0]))

        # Step 6: Build message
        final_message = build_final_message(
            translated_text=translated_text,
            image_ocr=image_ocr
        )

        # Step 7: Post as reply to target signal
        publisher = get_publisher_client()

        posted_msg = await publisher.send_message(
            entity=config.TARGET_GROUP_ID,
            message=final_message,
            file=media_info['local_path'] if media_info else None,
            reply_to=parent_signal['target_message_id']  # KEY: maintain threading
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
            'image_ocr_text': image_ocr,
            'status': 'POSTED',
            'processed_at': datetime.utcnow()
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
        # Step 9: Cleanup
        if media_info:
            cleanup_media(media_info['local_path'])
