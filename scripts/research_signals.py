#!/usr/bin/env python3
"""Research signal patterns from specific users in source group."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv(PROJECT_ROOT / ".env")

# Config
API_ID = int(os.getenv("READER_API_ID", "0"))
API_HASH = os.getenv("READER_API_HASH", "")
SESSION = os.getenv("READER_SESSION_STRING", "")
SOURCE_GROUP_ID = int(os.getenv("SOURCE_GROUP_ID", "0"))

# Users to research (excluding Mark 1018248833 and Даниил 1155161257)
RESEARCH_USERS = [
    468446980,   # Bendi
    5575681795,  # Unknown user
]


async def main():
    print(f"Connecting to Telegram...")
    print(f"API_ID: {API_ID}")
    print(f"Source group: {SOURCE_GROUP_ID}")

    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.start()

    me = await client.get_me()
    print(f"Connected as: {me.first_name} (@{me.username})")

    # Get group entity
    try:
        group = await client.get_entity(SOURCE_GROUP_ID)
        print(f"Group: {group.title}")
    except Exception as e:
        print(f"Error getting group: {e}")
        await client.disconnect()
        return

    # Cache participants to resolve user entities
    print("\nCaching group participants...")
    participants = {}
    async for user in client.iter_participants(group):
        participants[user.id] = user
    print(f"Cached {len(participants)} participants")

    print("\n" + "="*80)
    print("RESEARCHING SIGNAL PATTERNS")
    print("="*80)

    for user_id in RESEARCH_USERS:
        print(f"\n{'='*80}")
        print(f"USER ID: {user_id}")
        print("="*80)

        # Get user info from cache
        user = participants.get(user_id)
        if user:
            print(f"Name: {user.first_name} {user.last_name or ''}")
            print(f"Username: @{user.username or 'N/A'}")
        else:
            print(f"User not found in group participants")

        # Get messages from this user by iterating all messages and filtering
        print(f"\nLast 20 messages from user {user_id}:")
        print("-"*60)

        count = 0
        async for message in client.iter_messages(group, limit=500):
            if message.sender_id == user_id:
                count += 1
                text = message.text or "[media without text]"
                # Truncate long messages
                if len(text) > 500:
                    text = text[:500] + "..."

                print(f"\n[{count}] Message ID: {message.id}")
                print(f"    Date: {message.date}")
                print(f"    Reply to: {message.reply_to_msg_id or 'N/A'}")
                print(f"    Text:\n{text}")
                print("-"*60)

                if count >= 20:
                    break

        if count == 0:
            print("No messages found from this user in this group")

    await client.disconnect()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
