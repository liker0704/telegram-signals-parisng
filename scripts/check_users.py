#!/usr/bin/env python3
"""Check who is who by user IDs from source group messages."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.config import config
from src.telethon_setup import init_clients, get_reader_client


async def main():
    await init_clients()
    client = get_reader_client()

    print(f"Source group: {config.SOURCE_GROUP_ID}")
    print(f"Allowed users in env: {config.SOURCE_ALLOWED_USERS}\n")

    # Get recent messages from source group
    users_info = {}

    async for msg in client.iter_messages(config.SOURCE_GROUP_ID, limit=200):
        if msg.sender_id and msg.sender_id not in users_info:
            try:
                sender = await msg.get_sender()
                if sender:
                    name = getattr(sender, 'first_name', '') or ''
                    last = getattr(sender, 'last_name', '') or ''
                    username = getattr(sender, 'username', None)
                    users_info[msg.sender_id] = {
                        'name': f"{name} {last}".strip(),
                        'username': username,
                        'count': 0
                    }
            except:
                pass

        if msg.sender_id in users_info:
            users_info[msg.sender_id]['count'] += 1

    print("Users found in source group (last 200 messages):\n")
    print("-" * 60)

    for uid, info in sorted(users_info.items(), key=lambda x: -x[1]['count']):
        username_str = f"@{info['username']}" if info['username'] else "no username"
        in_allowed = "✓ ALLOWED" if uid in config.allowed_users_list else ""
        print(f"{uid}: {info['name']} ({username_str}) - {info['count']} msgs {in_allowed}")

    print("-" * 60)
    print(f"\nCurrent SOURCE_ALLOWED_USERS: {config.SOURCE_ALLOWED_USERS}")


if __name__ == "__main__":
    asyncio.run(main())
