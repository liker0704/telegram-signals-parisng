"""Handler for new trading signals (#Идея)."""

from datetime import datetime
from typing import Optional

from telethon.events import NewMessage

from src.config import config
from src.utils.logger import get_logger
from src.parsers.signal_parser import parse_trading_signal, is_signal
from src.formatters.message import build_final_message
from src.translators.fallback import translate_text_with_fallback
from src.ocr.gemini_ocr import translate_image_ocr
from src.media.downloader import download_and_process_media, cleanup_media
from src.db.queries import db_insert_signal, db_update_signal
from src.telethon_setup import get_publisher_client

logger = get_logger(__name__)


async def handle_new_signal(event: NewMessage.Event) -> None:
    """
    Process a new #Идея signal from source group.

    Pipeline:
    1. Create DB record (PENDING)
    2. Update to PROCESSING
    3. Parse structured fields (regex)
    4. Download media (if present)
    5. Translate text + OCR (parallel)
    6. Build final message
    7. Post to target group
    8. Update DB with result
    9. Cleanup media

    Args:
        event: Telethon NewMessage event
    """
    message = event.message
    signal_id = None
    media_info = None

    try:
        # Check if sender is allowed (if configured)
        if config.allowed_users_list:
            sender_id = message.sender_id
            if sender_id not in config.allowed_users_list:
                logger.debug("Signal from unauthorized user, ignoring",
                            sender_id=sender_id)
                return

        logger.info("Processing new signal",
                    source_msg_id=message.id,
                    sender_id=message.sender_id)

        # Step 1: Create initial DB record
        signal_data = {
            'source_chat_id': message.chat_id,
            'source_message_id': message.id,
            'source_user_id': message.sender_id or 0,
            'original_text': message.text or '',
            'status': 'PENDING',
            'created_at': message.date or datetime.utcnow()
        }
        signal_id = await db_insert_signal(signal_data)
        logger.info("Created signal record", signal_id=signal_id)

        # Step 2: Update to PROCESSING
        await db_update_signal(signal_id, {'status': 'PROCESSING'})

        # Step 3: Parse structured fields
        parsed_fields = parse_trading_signal(message.text or '')
        await db_update_signal(signal_id, {
            'pair': parsed_fields.get('pair'),
            'direction': parsed_fields.get('direction'),
            'timeframe': parsed_fields.get('timeframe'),
            'entry_range': parsed_fields.get('entry_range'),
            'tp1': parsed_fields.get('tp1'),
            'tp2': parsed_fields.get('tp2'),
            'tp3': parsed_fields.get('tp3'),
            'sl': parsed_fields.get('sl'),
            'risk_percent': parsed_fields.get('risk_percent'),
        })

        # Step 4: Download media if present
        reader_client = event.client
        media_info = await download_and_process_media(
            client=reader_client,
            message=message,
            entity_id=signal_id
        )

        if media_info:
            await db_update_signal(signal_id, {
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
            logger.error("Translation failed", error=str(results[0]))
            await db_update_signal(signal_id, {
                'status': 'ERROR_TRANSLATION_FAILED',
                'error_message': str(results[0])
            })
            # Continue with original text

        # Step 6: Build final message
        final_message = build_final_message(
            translated_text=translated_text,
            image_ocr=image_ocr,
            parsed_fields=parsed_fields
        )

        # Step 7: Post to target group
        publisher = get_publisher_client()

        posted_msg = await publisher.send_message(
            entity=config.TARGET_GROUP_ID,
            message=final_message,
            file=media_info['local_path'] if media_info else None
        )

        target_msg_id = posted_msg.id
        logger.info("Posted signal to target",
                    signal_id=signal_id,
                    target_msg_id=target_msg_id)

        # Step 8: Update DB with success
        await db_update_signal(signal_id, {
            'target_chat_id': config.TARGET_GROUP_ID,
            'target_message_id': target_msg_id,
            'translated_text': translated_text,
            'image_ocr_text': image_ocr,
            'status': 'POSTED',
            'processed_at': datetime.utcnow()
        })

    except Exception as e:
        logger.error("Error processing signal",
                     signal_id=signal_id,
                     error=str(e),
                     exc_info=True)

        if signal_id:
            await db_update_signal(signal_id, {
                'status': 'ERROR_POSTING_FAILED',
                'error_message': str(e)
            })

    finally:
        # Step 9: Cleanup media
        if media_info:
            cleanup_media(media_info['local_path'])
