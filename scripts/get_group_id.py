"""
Script to find Telegram group IDs.
Run this to list all your groups/chats and their IDs.

Usage:
    python scripts/get_group_id.py                # Use reader session
    python scripts/get_group_id.py publisher      # Use publisher session
    python scripts/get_group_id.py --search NAME  # Search by name
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def get_client(account_type: str) -> TelegramClient:
    """Get Telegram client for account type."""
    if account_type == "publisher":
        session = os.getenv("PUBLISHER_SESSION_STRING")
        api_id = os.getenv("PUBLISHER_API_ID")
        api_hash = os.getenv("PUBLISHER_API_HASH")
        phone = os.getenv("PUBLISHER_PHONE")
    else:
        session = os.getenv("READER_SESSION_STRING")
        api_id = os.getenv("READER_API_ID")
        api_hash = os.getenv("READER_API_HASH")
        phone = os.getenv("READER_PHONE")

    if not api_id or not api_hash:
        print(f"{Colors.FAIL}Missing API credentials for {account_type} in .env{Colors.ENDC}")
        sys.exit(1)

    # Use session string if available, otherwise use phone auth
    if session:
        return TelegramClient(StringSession(session), int(api_id), api_hash), None
    else:
        return TelegramClient(f"session_{account_type}", int(api_id), api_hash), phone


async def list_groups(account_type: str, search: str = None):
    """List all groups/channels."""
    client, phone = get_client(account_type)

    if phone:
        print(f"{Colors.WARNING}No session string found, using phone auth...{Colors.ENDC}")
        await client.start(phone=phone)
    else:
        await client.start()

    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'Groups/Channels for ' + account_type.upper():^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

    count = 0
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            # Apply search filter if provided
            if search and search.lower() not in dialog.name.lower():
                continue

            entity = dialog.entity
            # Supergroups/channels need -100 prefix
            if hasattr(entity, 'megagroup') or hasattr(entity, 'broadcast'):
                full_id = f"-100{entity.id}"
            else:
                full_id = f"-{entity.id}"

            group_type = "Channel" if dialog.is_channel else "Group"
            type_color = Colors.OKBLUE if dialog.is_channel else Colors.OKCYAN

            print(f"{type_color}{Colors.BOLD}{group_type}:{Colors.ENDC} {dialog.name}")
            print(f"  {Colors.OKGREEN}ID: {full_id}{Colors.ENDC}")
            print()
            count += 1

    print(f"{Colors.BOLD}Total: {count} groups/channels{Colors.ENDC}")

    await client.disconnect()

    # Clean up temp session if created
    session_file = Path(f"session_{account_type}.session")
    if session_file.exists():
        session_file.unlink()


def main():
    parser = argparse.ArgumentParser(description='List Telegram groups and their IDs')
    parser.add_argument('account', nargs='?', default='reader',
                        choices=['reader', 'publisher', 'r', 'p'],
                        help='Account to use (default: reader)')
    parser.add_argument('--search', '-s', metavar='NAME',
                        help='Filter groups by name')

    args = parser.parse_args()

    account = 'publisher' if args.account in ('publisher', 'p') else 'reader'

    asyncio.run(list_groups(account, args.search))


if __name__ == "__main__":
    main()
