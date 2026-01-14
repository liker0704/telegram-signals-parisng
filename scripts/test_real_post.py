#!/usr/bin/env python3
"""
Test real posting - finds last #идея chain and posts it to target group.
Uses actual handlers from the codebase.
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
from src.db.connection import init_db, close_db
from src.handlers.signal_handler import handle_new_signal
from src.handlers.update_handler import handle_signal_update
from src.telethon_setup import init_clients, get_reader_client, get_publisher_client


async def main():
    print("Initializing...")

    # Init DB
    await init_db()

    # Init Telegram clients
    await init_clients()
    reader = get_reader_client()

    source_group_id = config.SOURCE_GROUP_ID
    allowed_users = set(config.allowed_users_list)

    print(f"Source group: {source_group_id}")
    print(f"Allowed users: {allowed_users}")

    # Find second-to-last #идея message
    print("\nSearching for second-to-last #идея signal...")
    signal_message = None
    found_count = 0

    async for message in reader.iter_messages(source_group_id, limit=200):
        if message.sender_id in allowed_users and message.text:
            if "#идея" in message.text.lower() or "#idea" in message.text.lower():
                found_count += 1
                if found_count == 2:  # Second signal
                    signal_message = message
                    break

    if not signal_message:
        print("No #идея signal found in last 100 messages")
        await close_db()
        return

    print(f"\n{'='*60}")
    print("FOUND SIGNAL:")
    print(f"{'='*60}")
    print(f"ID: {signal_message.id}")
    print(f"From: {signal_message.sender_id}")
    print(f"Date: {signal_message.date}")
    print(f"Text preview: {signal_message.text[:200]}...")

    # Find replies to this signal (updates)
    print(f"\nSearching for replies to message {signal_message.id}...")
    replies = []

    async for message in reader.iter_messages(
        source_group_id,
        reply_to=signal_message.id,
        limit=20
    ):
        if message.sender_id in allowed_users:
            replies.append(message)

    replies.reverse()  # Oldest first
    print(f"Found {len(replies)} replies")

    # Summary
    print(f"\n{'='*60}")
    print("POSTING:")
    print(f"{'='*60}")
    print(f"1 signal + {len(replies)} updates")

    # Process signal
    print("\n>>> Processing signal...")

    # Create a fake event-like object that the handler expects
    class FakeEvent:
        def __init__(self, msg, client):
            self.message = msg
            self.chat_id = msg.chat_id
            self.sender_id = msg.sender_id
            self.client = client

    try:
        await handle_new_signal(FakeEvent(signal_message, reader))
        print("Signal posted!")
    except Exception as e:
        print(f"Signal posting failed: {e}")
        import traceback
        traceback.print_exc()

    # Process replies
    for i, reply in enumerate(replies, 1):
        print(f"\n>>> Processing update {i}/{len(replies)}...")
        try:
            await handle_signal_update(FakeEvent(reply, reader))
            print(f"Update {i} posted!")
        except Exception as e:
            print(f"Update {i} failed: {e}")

    print("\n" + "="*60)
    print("DONE!")
    print("="*60)

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
