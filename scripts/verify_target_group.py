"""
Script to verify translated messages in TARGET_GROUP after integration tests.

This script fetches recent messages from TARGET_GROUP to manually verify
that translations appeared correctly. Uses the Publisher client (Account B)
which has access to TARGET_GROUP.

Usage:
    python scripts/verify_target_group.py [options]

Options:
    --limit N       Number of messages to fetch (default: 10)
    --since N       Only show messages from last N minutes (default: 60)

Examples:
    python scripts/verify_target_group.py
    python scripts/verify_target_group.py --limit 20
    python scripts/verify_target_group.py --since 30 --limit 15

Environment Variables Required:
    - PUBLISHER_API_ID, PUBLISHER_API_HASH, PUBLISHER_PHONE
    - PUBLISHER_SESSION_STRING (preferred) or PUBLISHER_SESSION_FILE
    - TARGET_GROUP_ID
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Message

# Load .env file
load_dotenv()

import os


def get_publisher_credentials() -> tuple:
    """
    Get Publisher account credentials from environment.

    Returns:
        Tuple of (api_id, api_hash, phone, session_string, session_file)
    """
    api_id = os.getenv("PUBLISHER_API_ID")
    api_hash = os.getenv("PUBLISHER_API_HASH")
    phone = os.getenv("PUBLISHER_PHONE")
    session_string = os.getenv("PUBLISHER_SESSION_STRING")
    session_file = os.getenv("PUBLISHER_SESSION_FILE", "sessions/publisher.session")

    return api_id, api_hash, phone, session_string, session_file


def get_target_group_id() -> Optional[int]:
    """
    Get TARGET_GROUP_ID from environment.

    Returns:
        Group ID as integer, or None if not set
    """
    group_id = os.getenv("TARGET_GROUP_ID")
    if group_id:
        try:
            return int(group_id)
        except ValueError:
            print(f"ERROR: TARGET_GROUP_ID is not a valid integer: {group_id}")
            return None
    return None


def truncate_text(text: str, max_length: int = 200) -> str:
    """
    Truncate text to max_length characters, adding '...' if truncated.

    Args:
        text: Text to truncate
        max_length: Maximum length before truncation

    Returns:
        Truncated text with '...' suffix if needed
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[:max_length] + "..."


def format_message(msg: Message, index: int) -> str:
    """
    Format a Telegram message for display.

    Args:
        msg: Telethon Message object
        index: Message index in the list

    Returns:
        Formatted message string
    """
    # Message ID
    output = [f"[{msg.id}] {msg.date.strftime('%Y-%m-%d %H:%M:%S')} UTC"]

    # Message text (truncated if too long)
    text = msg.text or msg.message or ""
    if text:
        truncated_text = truncate_text(text, max_length=200)
        output.append(f"Text: {truncated_text}")
    else:
        output.append("Text: <No text>")

    # Media presence
    if msg.media:
        media_type = type(msg.media).__name__
        output.append(f"Media: Yes ({media_type})")
    else:
        output.append("Media: No")

    # Reply information
    if msg.reply_to:
        reply_to_msg_id = msg.reply_to.reply_to_msg_id
        output.append(f"Reply to: {reply_to_msg_id}")
    else:
        output.append("Reply to: None")

    return "\n".join(output)


async def verify_target_group(limit: int = 10, since_minutes: int = 60):
    """
    Fetch and display recent messages from TARGET_GROUP.

    Args:
        limit: Maximum number of messages to fetch
        since_minutes: Only show messages from last N minutes
    """
    # Get credentials
    api_id, api_hash, phone, session_string, session_file = get_publisher_credentials()

    if not all([api_id, api_hash, phone]):
        print("ERROR: Missing Publisher credentials in .env file!")
        print("\nRequired environment variables:")
        print("  PUBLISHER_API_ID=your_api_id")
        print("  PUBLISHER_API_HASH=your_api_hash")
        print("  PUBLISHER_PHONE=+your_phone")
        print("  PUBLISHER_SESSION_STRING=your_session_string  (preferred)")
        print("  OR")
        print("  PUBLISHER_SESSION_FILE=path/to/session.file")
        return

    # Get target group ID
    target_group_id = get_target_group_id()
    if not target_group_id:
        print("ERROR: TARGET_GROUP_ID not set in .env file!")
        print("\nRequired environment variable:")
        print("  TARGET_GROUP_ID=-100xxxxxxxxxx")
        return

    # Determine session type
    if session_string:
        session = StringSession(session_string)
        print("Using StringSession for authentication...")
    else:
        session_path = Path(session_file)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session = session_file
        print(f"Using file-based session: {session_file}")

    # Initialize client
    client = TelegramClient(
        session=session,
        api_id=int(api_id),
        api_hash=api_hash
    )

    try:
        # Connect
        await client.connect()

        # Authenticate if needed
        if not await client.is_user_authorized():
            if session_string:
                print("ERROR: PUBLISHER_SESSION_STRING is invalid or expired!")
                print("Please regenerate it using scripts/auth_local.py")
                return
            else:
                print("File-based session requires interactive authentication...")
                await client.start(phone=phone)

        # Get user info
        me = await client.get_me()
        print(f"Connected as: {me.first_name} (ID: {me.id}, @{me.username or 'N/A'})")

        # Get target group entity
        try:
            target_entity = await client.get_entity(target_group_id)
            group_title = getattr(target_entity, 'title', 'Unknown')
            print(f"Target group: {group_title} (ID: {target_group_id})")
        except Exception as e:
            print(f"ERROR: Cannot access TARGET_GROUP_ID {target_group_id}")
            print(f"Error: {e}")
            print("\nMake sure:")
            print("  1. The Publisher account is a member of this group")
            print("  2. The group ID is correct (negative, starts with -100)")
            return

        # Calculate time threshold
        time_threshold = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)

        print(f"\nFetching up to {limit} messages from last {since_minutes} minutes...")
        print("=" * 60)

        # Fetch messages
        messages_found = []
        async for message in client.iter_messages(target_group_id, limit=limit):
            # Check if message is within time window
            if message.date < time_threshold:
                continue

            messages_found.append(message)

        # Display results
        if not messages_found:
            print(f"\nNo messages found in the last {since_minutes} minutes.")
            print("\nTips:")
            print("  - Run integration tests first to generate messages")
            print("  - Increase --since parameter if tests were run earlier")
            print("  - Check that TARGET_GROUP_ID is correct")
        else:
            print(f"\nRecent messages in TARGET_GROUP (last {since_minutes} min):")
            print("=" * 60)
            print()

            for idx, msg in enumerate(messages_found, start=1):
                print(format_message(msg, idx))
                print()
                print("-" * 60)
                print()

            print("=" * 60)
            print(f"Found {len(messages_found)} message(s) in the last {since_minutes} minutes.")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Disconnect
        await client.disconnect()
        print("\nDisconnected.")


def parse_arguments():
    """
    Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Verify translated messages in TARGET_GROUP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/verify_target_group.py
  python scripts/verify_target_group.py --limit 20
  python scripts/verify_target_group.py --since 30 --limit 15
        """
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of messages to fetch (default: 10)"
    )

    parser.add_argument(
        "--since",
        type=int,
        default=60,
        help="Only show messages from last N minutes (default: 60)"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    # Validate arguments
    if args.limit <= 0:
        print("ERROR: --limit must be greater than 0")
        sys.exit(1)

    if args.since <= 0:
        print("ERROR: --since must be greater than 0")
        sys.exit(1)

    # Run verification
    asyncio.run(verify_target_group(
        limit=args.limit,
        since_minutes=args.since
    ))


if __name__ == "__main__":
    main()
