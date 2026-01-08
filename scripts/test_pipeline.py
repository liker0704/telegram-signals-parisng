#!/usr/bin/env python3
"""
Test pipeline script - processes the last message from source group WITHOUT posting.
Shows what would be sent to target group.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient
from telethon.sessions import StringSession

from src.config import config
from src.translators.fallback import translate_text_with_fallback
from src.image_editing import ImageEditorFactory


async def main():
    # Connect with Reader to get messages (READ ONLY!)
    print("Connecting to Telegram (READ ONLY)...")
    reader = TelegramClient(
        StringSession(config.READER_SESSION_STRING),
        config.READER_API_ID,
        config.READER_API_HASH
    )
    await reader.connect()

    source_group_id = config.SOURCE_GROUP_ID
    allowed_users = set(config.allowed_users_list)

    print(f"Source group: {source_group_id}")
    print(f"Allowed users: {allowed_users}")

    # Find last message from allowed user
    print("\nSearching for last message from allowed user...")
    target_message = None

    async for message in reader.iter_messages(source_group_id, limit=50):
        if message.sender_id in allowed_users:
            target_message = message
            break

    if not target_message:
        print("No messages from allowed users found in last 50 messages")
        await reader.disconnect()
        return

    print(f"\n{'='*60}")
    print("FOUND MESSAGE:")
    print(f"{'='*60}")
    print(f"From: {target_message.sender_id}")
    print(f"Date: {target_message.date}")
    print(f"Has photo: {target_message.photo is not None}")
    print(f"Text: {target_message.text[:200] if target_message.text else '(no text)'}...")

    # Process text translation
    print(f"\n{'='*60}")
    print("TRANSLATING TEXT...")
    print(f"{'='*60}")

    if target_message.text:
        translated = await translate_text_with_fallback(target_message.text)
        print(f"\nOriginal:\n{target_message.text[:500]}")
        print(f"\nTranslated:\n{translated[:500] if translated else '(failed)'}")
    else:
        translated = None
        print("(no text to translate)")

    # Process image if present
    if target_message.photo:
        print(f"\n{'='*60}")
        print("PROCESSING IMAGE...")
        print(f"{'='*60}")

        # Download image
        download_path = "/tmp/signals/test_pipeline_image.jpg"
        os.makedirs(os.path.dirname(download_path), exist_ok=True)

        await reader.download_media(target_message.photo, file=download_path)
        print(f"Downloaded to: {download_path}")

        # Get image size
        from PIL import Image
        with Image.open(download_path) as img:
            print(f"Original size: {img.size}")

        # Edit image
        editor = ImageEditorFactory.get_editor()
        print(f"Using editor: {editor.__class__.__name__}")

        try:
            # Pass translations dict (used for OCR-based editing)
            translations = {"original": target_message.text or "", "translated": translated or ""}
            result = editor.edit_image(download_path, translations)

            if result.success and result.edited_image:
                edited_path = "/tmp/signals/test_pipeline_edited.png"
                result.edited_image.save(edited_path)
                print(f"Edited image saved to: {edited_path}")
                print(f"Edited size: {result.edited_image.size}")
            else:
                print(f"Editing failed: {result.error}")
                edited_path = None
        except Exception as e:
            print(f"Image editing failed: {e}")
            edited_path = None
    else:
        edited_path = None
        print("\n(no image to process)")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY - WOULD POST TO TARGET GROUP:")
    print(f"{'='*60}")
    print(f"Text: {translated[:300] if translated else '(none)'}...")
    print(f"Image: {edited_path if edited_path else '(none)'}")
    print(f"\n*** NOT ACTUALLY POSTING - TEST ONLY ***")

    await reader.disconnect()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
