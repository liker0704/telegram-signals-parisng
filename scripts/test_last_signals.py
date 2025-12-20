#!/usr/bin/env python3
"""Test script to find and optionally reprocess last signals."""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient
from telethon.sessions import StringSession
from src.db.connection import init_db, fetch, execute, close_db
from src.handlers.signal_handler import handle_new_signal
from src.telethon_setup import init_publisher_client


class FakeEvent:
    """Fake event to simulate Telegram message event."""
    def __init__(self, message, client, chat_id):
        self.message = message
        self.chat_id = chat_id
        self.client = client


async def main():
    # Initialize DB
    await init_db()

    # Connect reader
    reader = TelegramClient(
        StringSession(os.getenv('READER_SESSION_STRING')),
        int(os.getenv('READER_API_ID')),
        os.getenv('READER_API_HASH')
    )
    await reader.start()

    source_group = int(os.getenv('SOURCE_GROUP_ID'))
    allowed_users = [int(x) for x in os.getenv('SOURCE_ALLOWED_USERS', '').split(',') if x]

    print(f"Connected! Looking for last 10 #Идея messages...")

    # Fetch last 100 messages and filter for #Идея
    idea_messages = []
    async for msg in reader.iter_messages(source_group, limit=100):
        if msg.text and '#Идея' in msg.text:
            if msg.sender_id in allowed_users:
                idea_messages.append(msg)
                if len(idea_messages) >= 10:
                    break

    print(f"\nFound {len(idea_messages)} #Идея messages from allowed users:\n")

    # Check which ones are already processed
    for i, msg in enumerate(idea_messages):
        existing = await fetch(
            "SELECT id, status, target_message_id FROM signals WHERE source_message_id = $1",
            msg.id
        )
        status = existing[0]['status'] if existing else "NOT_IN_DB"
        target_id = existing[0]['target_message_id'] if existing else None
        has_media = "📷" if msg.media else "📝"
        text_preview = (msg.text[:40] + "...") if len(msg.text) > 40 else msg.text
        text_preview = text_preview.replace('\n', ' ')
        print(f"  [{i}] {has_media} msg_id={msg.id} | {status:<20} | target={target_id}")

    # Ask if user wants to reprocess
    if '--reprocess' in sys.argv:
        # Find which index to reprocess
        idx = int(sys.argv[sys.argv.index('--reprocess') + 1]) if len(sys.argv) > sys.argv.index('--reprocess') + 1 else 0

        if idx < len(idea_messages):
            msg = idea_messages[idx]
            print(f"\n🔄 Reprocessing message {msg.id}...")

            # Initialize Publisher client for posting
            print("📤 Initializing Publisher client...")
            await init_publisher_client()

            # Delete from DB if exists
            await execute("DELETE FROM signals WHERE source_message_id = $1", msg.id)

            # Create fake event and process
            event = FakeEvent(msg, reader, source_group)
            await handle_new_signal(event)

            print("✅ Done!")

    await reader.disconnect()
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
