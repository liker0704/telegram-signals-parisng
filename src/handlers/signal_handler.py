"""Handler for new trading signals (#Идея)."""

import asyncio
from datetime import datetime

from telethon.events import NewMessage

from src.config import config
from src.utils.logger import get_logger
from src.utils.text_cleaner import strip_promo_content
from src.parsers.signal_parser import parse_trading_signal
from src.formatters.message import build_final_message
from src.translators.fallback import translate_text_with_fallback
from src.ocr.gemini_ocr import process_image
from src.media.downloader import download_and_process_media, cleanup_media
from src.db.queries import db_insert_signal, db_update_signal, db_find_signal_by_source_msg
from src.telethon_setup import get_publisher_client
from src.handlers.forward_helper import forward_original_message, is_forwarding_enabled
from src.state import start_flow

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
    # Idempotency check - skip if already processed
    existing_signal = await db_find_signal_by_source_msg(
        source_chat_id=message.chat_id,
        source_message_id=message.id
    )
    if existing_signal:
        logger.info("Signal already processed, skipping",
                   source_msg_id=message.id,
                   existing_signal_id=existing_signal.get('id'))
        return

    signal_id = None
    media_info = None
    edited_image_path = None

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

        # Start flow tracking (only for identified users)
        if message.sender_id and message.sender_id > 0:
            start_flow(signal_id, message.sender_id)
            logger.debug("Started flow tracking", signal_id=signal_id, user_id=message.sender_id)

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

        # Step 5: Clean text and prepare parallel tasks
        clean_text = strip_promo_content(message.text or '')
        translation_task = translate_text_with_fallback(clean_text)
        image_edit_task = (
            process_image(media_info['local_path'])
            if media_info else asyncio.sleep(0)
        )

        # Forward original message task (parallel with translation)
        forward_task = (
            forward_original_message(
                original_text=message.text or '',
                media_path=media_info['local_path'] if media_info else None,
                reply_to_forward_id=None  # New signal, no parent
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
            logger.error("Translation failed", error=str(results[0]))
            await db_update_signal(signal_id, {
                'status': 'ERROR_TRANSLATION_FAILED',
                'error_message': str(results[0])
            })
            # Continue with original text

        # Step 6: Build final message
        final_message = build_final_message(
            translated_text=translated_text,
            parsed_fields=parsed_fields
        )

        # Step 7: Post to target group
        publisher = get_publisher_client()

        # Use edited image if available, otherwise original
        image_to_send = edited_image_path or (media_info['local_path'] if media_info else None)

        posted_msg = await asyncio.wait_for(
            publisher.send_message(
                entity=config.TARGET_GROUP_ID,
                message=final_message,
                file=image_to_send
            ),
            timeout=config.TIMEOUT_TELEGRAM_SEC
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
            'image_ocr_text': None,  # OCR no longer performed
            'status': 'POSTED',
            'processed_at': datetime.utcnow(),
            'forward_chat_id': config.FORWARD_GROUP_ID if forward_msg_id else None,
            'forward_message_id': forward_msg_id,
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
        # Step 9: Cleanup media (both original and edited images) with error handling
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
