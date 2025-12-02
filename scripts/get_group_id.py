"""
Script to find Telegram group IDs.
Run this to list all your groups/chats and their IDs.

Usage:
    python scripts/get_group_id.py

You need to set these environment variables first:
    READER_API_ID=your_api_id
    READER_API_HASH=your_api_hash
    READER_PHONE=+your_phone
"""

import asyncio
import os
from telethon import TelegramClient

API_ID = os.getenv("READER_API_ID")
API_HASH = os.getenv("READER_API_HASH")
PHONE = os.getenv("READER_PHONE")


async def main():
    if not all([API_ID, API_HASH, PHONE]):
        print("Please set environment variables:")
        print("  export READER_API_ID=your_api_id")
        print("  export READER_API_HASH=your_api_hash")
        print("  export READER_PHONE=+your_phone")
        return

    client = TelegramClient("session_finder", int(API_ID), API_HASH)
    await client.start(phone=PHONE)

    print("\n=== Your Groups and Channels ===\n")

    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            entity = dialog.entity
            group_type = "Channel" if dialog.is_channel else "Group"
            print(f"{group_type}: {dialog.name}")
            print(f"  ID: {dialog.id}")
            print()

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
