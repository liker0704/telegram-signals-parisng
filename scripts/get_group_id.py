"""
Script to find Telegram group IDs.
Run this to list all your groups/chats and their IDs.

Usage:
    1. Create .env file with API credentials
    2. Run: python scripts/get_group_id.py [reader|publisher]

    Examples:
        python scripts/get_group_id.py reader     # List groups for Reader account
        python scripts/get_group_id.py publisher  # List groups for Publisher account
        python scripts/get_group_id.py            # Default: reader
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telethon import TelegramClient

# Load .env file
load_dotenv()

import os


def get_credentials(account_type: str) -> tuple:
    """Get API credentials based on account type."""
    if account_type == "publisher":
        return (
            os.getenv("PUBLISHER_API_ID"),
            os.getenv("PUBLISHER_API_HASH"),
            os.getenv("PUBLISHER_PHONE"),
            "PUBLISHER"
        )
    else:
        return (
            os.getenv("READER_API_ID"),
            os.getenv("READER_API_HASH"),
            os.getenv("READER_PHONE"),
            "READER"
        )


async def main():
    # Parse command line argument
    account_type = "reader"
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("publisher", "pub", "p"):
            account_type = "publisher"
        elif arg in ("reader", "read", "r"):
            account_type = "reader"
        else:
            print(f"Unknown account type: {arg}")
            print("Use: reader or publisher")
            return

    api_id, api_hash, phone, prefix = get_credentials(account_type)

    if not all([api_id, api_hash, phone]):
        print(f"Missing configuration for {account_type.upper()} in .env file!")
        print("Required variables:")
        print(f"  {prefix}_API_ID=your_api_id")
        print(f"  {prefix}_API_HASH=your_api_hash")
        print(f"  {prefix}_PHONE=+your_phone")
        print()
        print("Make sure .env file exists in the project root.")
        return

    session_name = f"session_finder_{account_type}"
    client = TelegramClient(session_name, int(api_id), api_hash)
    await client.start(phone=phone)

    print(f"\n=== Groups and Channels for {account_type.upper()} account ===\n")

    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            group_type = "Channel" if dialog.is_channel else "Group"
            print(f"{group_type}: {dialog.name}")
            print(f"  ID: {dialog.id}")
            print()

    await client.disconnect()

    # Clean up session file
    session_file = Path(f"{session_name}.session")
    if session_file.exists():
        session_file.unlink()
        print("(Temporary session file cleaned up)")


if __name__ == "__main__":
    asyncio.run(main())
