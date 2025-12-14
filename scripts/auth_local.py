#!/usr/bin/env python3
"""
Local Authentication Script for Telegram Signal Translator Bot

This script must be run LOCALLY (not in Docker) to generate session strings
for Reader and/or Publisher accounts.

Usage:
    # Authenticate both accounts (default)
    python auth_local.py

    # Authenticate only reader
    python auth_local.py --reader

    # Authenticate only publisher
    python auth_local.py --publisher

    # Get user IDs by username (requires existing session)
    python auth_local.py --get-users @username1 @username2

    # Get group ID by name (requires existing session)
    python auth_local.py --get-group "Group Name"

This is a ONE-TIME setup. Session strings remain valid until you explicitly
logout or revoke the session in Telegram settings.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Please run: pip install telethon python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()


# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print a colored header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.OKGREEN}{Colors.BOLD}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.FAIL}{Colors.BOLD}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print an info message."""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


async def authenticate_account(account_name: str, api_id: int, api_hash: str, phone: str) -> str:
    """
    Authenticate a Telegram account and return the StringSession.

    Args:
        account_name: Human-readable account name (e.g., "Reader", "Publisher")
        api_id: Telegram API ID
        api_hash: Telegram API hash
        phone: Phone number in international format

    Returns:
        StringSession string that can be stored in environment variables
    """
    print_header(f"Authenticating {account_name} Account")

    print_info(f"Phone number: {phone}")
    print_info(f"API ID: {api_id}")
    print_warning("You will receive a verification code via Telegram...")

    # Create client with empty StringSession (will be generated during auth)
    client = TelegramClient(StringSession(), api_id, api_hash)

    await client.start(phone=phone)

    # Get the StringSession
    session_string = client.session.save()

    # Verify connection
    me = await client.get_me()
    print_success(f"Successfully authenticated as: {me.first_name} (ID: {me.id})")
    if me.username:
        print_info(f"Username: @{me.username}")

    # Disconnect (session string is now saved)
    await client.disconnect()

    return session_string


async def get_user_ids(usernames: list[str]):
    """Get user IDs for given usernames using existing session."""
    print_header("Getting User IDs")

    # Try publisher session first, then reader
    session_string = os.getenv('PUBLISHER_SESSION_STRING') or os.getenv('READER_SESSION_STRING')
    api_id = int(os.getenv('PUBLISHER_API_ID') or os.getenv('READER_API_ID'))
    api_hash = os.getenv('PUBLISHER_API_HASH') or os.getenv('READER_API_HASH')

    if not session_string:
        print_error("No session string found. Run authentication first.")
        sys.exit(1)

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.start()

    print_info("Connected to Telegram\n")

    results = []
    for username in usernames:
        # Remove @ if present
        username = username.lstrip('@')
        try:
            user = await client.get_entity(username)
            print_success(f"@{username}: {user.id}")
            results.append((username, user.id))
        except Exception as e:
            print_error(f"@{username}: Not found - {e}")

    await client.disconnect()

    if results:
        print(f"\n{Colors.BOLD}For .env (SOURCE_ALLOWED_USERS):{Colors.ENDC}")
        user_ids = ','.join(str(uid) for _, uid in results)
        print(f"SOURCE_ALLOWED_USERS={user_ids}")

    return results


async def get_group_id(group_name: str):
    """Get group ID by name using existing session."""
    print_header("Getting Group ID")

    # Try publisher session first, then reader
    session_string = os.getenv('PUBLISHER_SESSION_STRING') or os.getenv('READER_SESSION_STRING')
    api_id = int(os.getenv('PUBLISHER_API_ID') or os.getenv('READER_API_ID'))
    api_hash = os.getenv('PUBLISHER_API_HASH') or os.getenv('READER_API_HASH')

    if not session_string:
        print_error("No session string found. Run authentication first.")
        sys.exit(1)

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.start()

    print_info(f"Searching for group: {group_name}\n")

    # Get all dialogs and search for the group
    found = False
    async for dialog in client.iter_dialogs():
        if group_name.lower() in dialog.name.lower():
            entity = dialog.entity
            # For supergroups/channels, we need the full ID with -100 prefix
            if hasattr(entity, 'megagroup') or hasattr(entity, 'broadcast'):
                group_id = f"-100{entity.id}"
            else:
                group_id = f"-{entity.id}"

            print_success(f"Found: {dialog.name}")
            print_info(f"  ID: {group_id}")
            print_info(f"  Type: {'Channel' if hasattr(entity, 'broadcast') and entity.broadcast else 'Group'}")

            print(f"\n{Colors.BOLD}For .env:{Colors.ENDC}")
            print(f"TARGET_GROUP_ID={group_id}")
            found = True

    if not found:
        print_error(f"Group '{group_name}' not found")
        print_info("Make sure you are a member of this group")

    await client.disconnect()


async def main_auth(auth_reader: bool, auth_publisher: bool):
    """Main authentication flow."""

    print_header("Telegram Signal Translator Bot - Local Authentication")

    if not auth_reader and not auth_publisher:
        # Default: authenticate both
        auth_reader = True
        auth_publisher = True

    # Validate environment variables
    required_vars = []
    if auth_reader:
        required_vars.extend(['READER_API_ID', 'READER_API_HASH', 'READER_PHONE'])
    if auth_publisher:
        required_vars.extend(['PUBLISHER_API_ID', 'PUBLISHER_API_HASH', 'PUBLISHER_PHONE'])

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print_error("Missing required environment variables in .env file:")
        for var in missing_vars:
            print(f"  • {var}")
        print("\nPlease configure your .env file and try again.")
        sys.exit(1)

    try:
        reader_session = None
        publisher_session = None

        # Authenticate Reader account
        if auth_reader:
            reader_api_id = int(os.getenv('READER_API_ID'))
            reader_api_hash = os.getenv('READER_API_HASH')
            reader_phone = os.getenv('READER_PHONE')

            reader_session = await authenticate_account(
                "Reader",
                reader_api_id,
                reader_api_hash,
                reader_phone
            )
            print("\n" + "="*70 + "\n")

        # Authenticate Publisher account
        if auth_publisher:
            publisher_api_id = int(os.getenv('PUBLISHER_API_ID'))
            publisher_api_hash = os.getenv('PUBLISHER_API_HASH')
            publisher_phone = os.getenv('PUBLISHER_PHONE')

            publisher_session = await authenticate_account(
                "Publisher",
                publisher_api_id,
                publisher_api_hash,
                publisher_phone
            )

        # Display results
        print_header("Authentication Complete!")

        print(f"\n{Colors.BOLD}Add these lines to your .env file:{Colors.ENDC}\n")

        print(f"{Colors.OKGREEN}# Session strings (generated by auth_local.py){Colors.ENDC}")
        if reader_session:
            print(f"READER_SESSION_STRING={reader_session}")
        if publisher_session:
            print(f"PUBLISHER_SESSION_STRING={publisher_session}")

        print(f"\n{Colors.WARNING}{Colors.BOLD}SECURITY NOTES:{Colors.ENDC}")
        print(f"{Colors.WARNING}  • Keep these session strings SECRET{Colors.ENDC}")
        print(f"{Colors.WARNING}  • Never commit .env to version control{Colors.ENDC}")

        print_success("\nSetup complete!")

    except Exception as e:
        print_error(f"Authentication failed: {str(e)}")
        sys.exit(1)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Telegram authentication and utility script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --publisher                    # Authenticate publisher only
  %(prog)s --reader                       # Authenticate reader only
  %(prog)s --get-users @user1 @user2      # Get user IDs
  %(prog)s --get-group "Trading Group"    # Get group ID
        """
    )

    parser.add_argument('--reader', action='store_true',
                        help='Authenticate only the reader account')
    parser.add_argument('--publisher', action='store_true',
                        help='Authenticate only the publisher account')
    parser.add_argument('--get-users', nargs='+', metavar='@USERNAME',
                        help='Get user IDs for given usernames')
    parser.add_argument('--get-group', metavar='NAME',
                        help='Get group ID by name')

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        if args.get_users:
            asyncio.run(get_user_ids(args.get_users))
        elif args.get_group:
            asyncio.run(get_group_id(args.get_group))
        else:
            asyncio.run(main_auth(args.reader, args.publisher))
    except KeyboardInterrupt:
        print_warning("\n\nCancelled by user.")
        sys.exit(1)
