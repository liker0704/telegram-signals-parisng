"""
Script to get Telegram user ID by username.

Usage:
    python scripts/get_user_id.py @username
    python scripts/get_user_id.py username

Examples:
    python scripts/get_user_id.py @durov
    python scripts/get_user_id.py durov
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

import os

API_ID = os.getenv("READER_API_ID")
API_HASH = os.getenv("READER_API_HASH")
SESSION_STRING = os.getenv("READER_SESSION_STRING")
PHONE = os.getenv("READER_PHONE")


async def get_user_id(username: str):
    if not all([API_ID, API_HASH]):
        print("Missing READER_API_ID or READER_API_HASH in .env")
        return

    # Use StringSession if available, otherwise file-based
    if SESSION_STRING:
        session = StringSession(SESSION_STRING)
    else:
        session = "temp_get_user"

    client = TelegramClient(session, int(API_ID), API_HASH)

    try:
        if SESSION_STRING:
            await client.connect()
        else:
            await client.start(phone=PHONE)

        # Normalize username
        if not username.startswith("@"):
            username = f"@{username}"

        print(f"\nLooking up {username}...\n")

        user = await client.get_entity(username)

        print(f"  Username:   @{user.username or 'N/A'}")
        print(f"  User ID:    {user.id}")
        print(f"  First name: {user.first_name or 'N/A'}")
        print(f"  Last name:  {user.last_name or 'N/A'}")
        print(f"  Phone:      {user.phone or 'hidden'}")
        print(f"  Bot:        {user.bot}")
        print()

    except ValueError as e:
        print(f"Error: User '{username}' not found")
        print(f"Details: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()

        # Cleanup temp session if created
        if not SESSION_STRING:
            temp_session = Path("temp_get_user.session")
            if temp_session.exists():
                temp_session.unlink()


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/get_user_id.py @username")
        print("Example: python scripts/get_user_id.py @durov")
        sys.exit(1)

    username = sys.argv[1]
    asyncio.run(get_user_id(username))


if __name__ == "__main__":
    main()
