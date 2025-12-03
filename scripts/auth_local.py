#!/usr/bin/env python3
"""
Local Authentication Script for Telegram Signal Translator Bot

This script must be run LOCALLY (not in Docker) to generate session strings
for both Reader and Publisher accounts.

Usage:
    1. Ensure you have installed dependencies: pip install telethon python-dotenv
    2. Run this script: python auth_local.py
    3. Follow the prompts to authenticate both accounts
    4. Copy the generated session strings to your .env file
    5. Run the bot in Docker with the session strings

This is a ONE-TIME setup. Session strings remain valid until you explicitly
logout or revoke the session in Telegram settings.
"""

import asyncio
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

import os

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

    Raises:
        Exception: If authentication fails
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


async def main():
    """Main authentication flow."""

    print_header("Telegram Signal Translator Bot - Local Authentication")

    print("""
This script will authenticate both Telegram accounts and generate session strings.

REQUIREMENTS:
  • Two separate Telegram accounts (Reader and Publisher)
  • API credentials from https://my.telegram.org/apps
  • Access to both phone numbers to receive verification codes
  • .env file with API credentials configured

IMPORTANT:
  • This script must run LOCALLY, not inside Docker
  • Keep generated session strings secure (they grant account access)
  • Session strings remain valid until you logout or revoke access
""")

    input(f"{Colors.BOLD}Press ENTER to continue...{Colors.ENDC}")

    # Validate environment variables
    required_vars = [
        'READER_API_ID', 'READER_API_HASH', 'READER_PHONE',
        'PUBLISHER_API_ID', 'PUBLISHER_API_HASH', 'PUBLISHER_PHONE'
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print_error("Missing required environment variables in .env file:")
        for var in missing_vars:
            print(f"  • {var}")
        print("\nPlease configure your .env file and try again.")
        sys.exit(1)

    try:
        # Get credentials from environment
        reader_api_id = int(os.getenv('READER_API_ID'))
        reader_api_hash = os.getenv('READER_API_HASH')
        reader_phone = os.getenv('READER_PHONE')

        publisher_api_id = int(os.getenv('PUBLISHER_API_ID'))
        publisher_api_hash = os.getenv('PUBLISHER_API_HASH')
        publisher_phone = os.getenv('PUBLISHER_PHONE')

        # Authenticate Reader account
        reader_session = await authenticate_account(
            "Reader",
            reader_api_id,
            reader_api_hash,
            reader_phone
        )

        print("\n" + "="*70 + "\n")

        # Authenticate Publisher account
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
        print(f"READER_SESSION_STRING={reader_session}")
        print(f"PUBLISHER_SESSION_STRING={publisher_session}")

        print(f"\n{Colors.WARNING}{Colors.BOLD}SECURITY NOTES:{Colors.ENDC}")
        print(f"{Colors.WARNING}  • Keep these session strings SECRET{Colors.ENDC}")
        print(f"{Colors.WARNING}  • Never commit .env to version control{Colors.ENDC}")
        print(f"{Colors.WARNING}  • Session strings grant full account access{Colors.ENDC}")
        print(f"{Colors.WARNING}  • Revoke sessions in Telegram Settings > Privacy > Active Sessions{Colors.ENDC}")

        print(f"\n{Colors.OKBLUE}{Colors.BOLD}NEXT STEPS:{Colors.ENDC}")
        print(f"{Colors.OKBLUE}  1. Add the session strings above to your .env file{Colors.ENDC}")
        print(f"{Colors.OKBLUE}  2. Start the Docker containers: docker-compose up -d{Colors.ENDC}")
        print(f"{Colors.OKBLUE}  3. View logs: docker-compose logs -f app{Colors.ENDC}")

        print_success("\nSetup complete! You can now run the bot in Docker.")

    except Exception as e:
        print_error(f"Authentication failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_warning("\n\nAuthentication cancelled by user.")
        sys.exit(1)
