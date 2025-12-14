#!/usr/bin/env python3
"""
Script to check recent messages from a Telegram group.

Usage:
    python scripts/check_group_messages.py GROUP_ID [--limit N]

Examples:
    python scripts/check_group_messages.py -1002880553977
    python scripts/check_group_messages.py -1002880553977 --limit 20
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
    DIM = '\033[2m'


async def check_messages(group_id: int, limit: int = 10):
    """Fetch and display recent messages from a group."""

    session = os.getenv("READER_SESSION_STRING")
    api_id = os.getenv("READER_API_ID")
    api_hash = os.getenv("READER_API_HASH")

    if not session or not api_id or not api_hash:
        print(f"{Colors.FAIL}Missing READER credentials in .env{Colors.ENDC}")
        sys.exit(1)

    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    await client.start()

    try:
        # Get entity info
        try:
            entity = await client.get_entity(group_id)
            title = getattr(entity, 'title', 'Unknown')

            print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
            print(f"{Colors.HEADER}{Colors.BOLD}{'Group: ' + title:^70}{Colors.ENDC}")
            print(f"{Colors.OKCYAN}ID: {group_id}{Colors.ENDC}")
            print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

        except Exception as e:
            print(f"{Colors.FAIL}Cannot access group {group_id}: {e}{Colors.ENDC}")
            await client.disconnect()
            return

        # Fetch messages
        print(f"{Colors.OKBLUE}Last {limit} messages:{Colors.ENDC}\n")

        messages = await client.get_messages(group_id, limit=limit)

        if not messages:
            print(f"{Colors.WARNING}No messages found{Colors.ENDC}")
            return

        for msg in reversed(messages):
            # Format timestamp
            time_str = msg.date.strftime("%Y-%m-%d %H:%M")

            # Get sender name
            sender_name = "Unknown"
            if msg.sender:
                sender_name = getattr(msg.sender, 'first_name', '') or ''
                if hasattr(msg.sender, 'last_name') and msg.sender.last_name:
                    sender_name += f" {msg.sender.last_name}"
                if hasattr(msg.sender, 'username') and msg.sender.username:
                    sender_name += f" (@{msg.sender.username})"

            # Message content
            text = msg.text or ""
            if msg.media:
                media_type = type(msg.media).__name__
                text = f"[{media_type}] {text}" if text else f"[{media_type}]"

            # Truncate long messages
            if len(text) > 200:
                text = text[:200] + "..."

            print(f"{Colors.DIM}{time_str}{Colors.ENDC} {Colors.OKGREEN}{sender_name}{Colors.ENDC}")
            if text:
                print(f"  {text}")
            print()

    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description='Check recent messages from a Telegram group')
    parser.add_argument('group_id', type=int, help='Group ID (e.g., -1002880553977)')
    parser.add_argument('--limit', '-l', type=int, default=10, help='Number of messages to fetch (default: 10)')

    args = parser.parse_args()
    asyncio.run(check_messages(args.group_id, args.limit))


if __name__ == "__main__":
    main()
