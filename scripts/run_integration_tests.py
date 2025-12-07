#!/usr/bin/env python3
"""
Integration Test Runner for Telegram Signal Translator Bot

This script sends test signals to SOURCE_GROUP using the Publisher account.
The bot (running in Docker) should detect, translate, and post to TARGET_GROUP.

NOTE: Uses Publisher account because Telegram doesn't send updates back to the
      client that sent the message. Publisher sends to SOURCE_GROUP, and the
      Reader (bot) receives these messages as normal incoming events.

Usage:
    python scripts/run_integration_tests.py --all                    # Run all tests
    python scripts/run_integration_tests.py --test INT-001 INT-002  # Run specific tests
    python scripts/run_integration_tests.py --dry-run               # Show what would be sent
    python scripts/run_integration_tests.py --list                  # List available tests
    python scripts/run_integration_tests.py --delay 45              # Set delay between tests

Requirements:
    - PUBLISHER_API_ID, PUBLISHER_API_HASH, PUBLISHER_PHONE in .env
    - PUBLISHER_SESSION_STRING (preferred) or PUBLISHER_SESSION_FILE
    - SOURCE_GROUP_ID configured
    - Publisher account must be a member of SOURCE_GROUP
    - tests/data/integration_test_signals.json exists
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

# Load environment variables
load_dotenv()


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class IntegrationTestRunner:
    """Runner for integration tests"""

    def __init__(self, dry_run: bool = False, delay: int = 30):
        self.dry_run = dry_run
        self.delay = delay
        self.client: Optional[TelegramClient] = None
        self.source_group_id: Optional[int] = None
        self.project_root = Path(__file__).parent.parent
        self.test_data_path = self.project_root / "tests" / "data" / "integration_test_signals.json"

        # Track sent messages for reply tests
        self.sent_messages: Dict[str, int] = {}

        # Test results
        self.results = {
            'passed': [],
            'failed': [],
            'skipped': []
        }

    async def init_client(self) -> None:
        """Initialize Telethon client with Publisher account credentials"""
        api_id = os.getenv("PUBLISHER_API_ID")
        api_hash = os.getenv("PUBLISHER_API_HASH")
        phone = os.getenv("PUBLISHER_PHONE")
        session_string = os.getenv("PUBLISHER_SESSION_STRING")
        session_file = os.getenv("PUBLISHER_SESSION_FILE", "sessions/publisher.session")

        if not all([api_id, api_hash, phone]):
            raise ValueError(
                "Missing required environment variables:\n"
                "  PUBLISHER_API_ID\n"
                "  PUBLISHER_API_HASH\n"
                "  PUBLISHER_PHONE\n"
                "Please check your .env file."
            )

        # Determine session type
        if session_string:
            print(f"{Colors.CYAN}Using StringSession for authentication{Colors.ENDC}")
            session = StringSession(session_string)
        else:
            print(f"{Colors.CYAN}Using file-based session: {session_file}{Colors.ENDC}")
            session_path = Path(session_file)
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session = session_file

        # Initialize client
        self.client = TelegramClient(
            session=session,
            api_id=int(api_id),
            api_hash=api_hash
        )

        # Connect and authenticate
        await self.client.connect()

        if not await self.client.is_user_authorized():
            if session_string:
                raise ValueError(
                    "PUBLISHER_SESSION_STRING is invalid or expired.\n"
                    "Please regenerate it using scripts/auth_local.py"
                )
            else:
                print(f"{Colors.YELLOW}Authentication required...{Colors.ENDC}")
                await self.client.start(phone=phone)

        # Verify connection
        me = await self.client.get_me()
        print(f"{Colors.GREEN}Connected as: {me.first_name} (@{me.username or 'no username'}){Colors.ENDC}")
        print(f"User ID: {me.id}\n")

    async def verify_group_access(self) -> None:
        """Verify Publisher has access to SOURCE_GROUP"""
        source_group_id_str = os.getenv("SOURCE_GROUP_ID")

        if not source_group_id_str:
            raise ValueError("SOURCE_GROUP_ID not set in .env file")

        self.source_group_id = int(source_group_id_str)

        try:
            entity = await self.client.get_entity(self.source_group_id)
            group_title = getattr(entity, 'title', 'Unknown')
            print(f"{Colors.GREEN}Access verified to SOURCE_GROUP:{Colors.ENDC}")
            print(f"  Group ID: {self.source_group_id}")
            print(f"  Group Title: {group_title}\n")
        except Exception as e:
            raise RuntimeError(
                f"Cannot access SOURCE_GROUP (ID: {self.source_group_id})\n"
                f"Error: {e}\n"
                f"Make sure the Publisher account is a member of this group."
            )

    def load_test_data(self) -> List[Dict]:
        """Load integration test data from JSON file"""
        if not self.test_data_path.exists():
            raise FileNotFoundError(
                f"Test data file not found: {self.test_data_path}\n"
                f"Please create tests/data/integration_test_signals.json\n"
                f"See docs/testing.md for the expected format."
            )

        with open(self.test_data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle both formats: direct array or object with test_cases array
        if isinstance(data, list):
            tests = data
        elif isinstance(data, dict) and 'test_cases' in data:
            tests = data['test_cases']
        else:
            raise ValueError(
                "Test data must be either:\n"
                "  - A JSON array of test objects, OR\n"
                "  - A JSON object with 'test_cases' array"
            )

        if not isinstance(tests, list):
            raise ValueError("test_cases must be a JSON array")

        return tests

    def list_tests(self, tests: List[Dict]) -> None:
        """List all available tests"""
        print(f"{Colors.BOLD}{Colors.HEADER}Available Integration Tests:{Colors.ENDC}\n")

        for test in tests:
            test_id = test.get('test_id', 'UNKNOWN')
            name = test.get('name', '')
            description = test.get('description', 'No description')
            has_image = test.get('has_image', False) or test.get('image_file') is not None
            is_reply = test.get('reply_to_test_id') is not None
            wait_time = test.get('wait_seconds', 15)

            # Print test ID and name
            if name:
                print(f"{Colors.CYAN}{test_id}{Colors.ENDC}: {name}")
            else:
                print(f"{Colors.CYAN}{test_id}{Colors.ENDC}")

            # Print description if different from name
            if description and description != name:
                print(f"  {description}")

            flags = []
            if has_image:
                flags.append("image")
            if is_reply:
                flags.append(f"reply to {test.get('reply_to_test_id')}")
            if wait_time > 15:
                flags.append(f"wait {wait_time}s")

            if flags:
                print(f"  [{', '.join(flags)}]")
            print()

    async def run_test(self, test: Dict) -> bool:
        """
        Run a single integration test

        Returns:
            bool: True if test passed, False if failed
        """
        test_id = test.get('test_id', 'UNKNOWN')
        name = test.get('name', '')
        description = test.get('description', 'No description')
        message_text = test.get('message_text', '')
        image_file = test.get('image_file')
        reply_to_test_id = test.get('reply_to_test_id')
        wait_seconds = test.get('wait_seconds', 15)

        print(f"{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
        title = name if name else description
        print(f"{Colors.BOLD}Running: {test_id} - {title}{Colors.ENDC}")

        # Resolve reply_to message ID if this is a reply
        reply_to_msg_id = None
        if reply_to_test_id:
            if reply_to_test_id not in self.sent_messages:
                error_msg = f"Parent test '{reply_to_test_id}' not run yet or failed"
                print(f"{Colors.RED}  SKIP: {error_msg}{Colors.ENDC}\n")
                self.results['skipped'].append({
                    'test_id': test_id,
                    'reason': error_msg
                })
                return False

            reply_to_msg_id = self.sent_messages[reply_to_test_id]
            print(f"  {Colors.YELLOW}Replying to message ID: {reply_to_msg_id}{Colors.ENDC}")

        # Resolve image file if present
        file_path = None
        if image_file:
            # Image file path is relative to tests/data/
            file_path = self.project_root / "tests" / "data" / image_file
            if not file_path.exists():
                error_msg = f"Image file not found: {file_path}"
                print(f"{Colors.RED}  FAIL: {error_msg}{Colors.ENDC}\n")
                self.results['failed'].append({
                    'test_id': test_id,
                    'error': error_msg
                })
                return False

            print(f"  Image: {image_file}")

        # Display message preview
        preview = message_text[:100].replace('\n', ' ')
        if len(message_text) > 100:
            preview += "..."
        print(f"  Message: {preview}")

        if self.dry_run:
            print(f"{Colors.YELLOW}  [DRY RUN] Would send message{Colors.ENDC}\n")

            # In dry-run mode, assign a fake message ID for reply tests
            fake_msg_id = 99999 + len(self.sent_messages)
            self.sent_messages[test_id] = fake_msg_id

            self.results['passed'].append({
                'test_id': test_id,
                'dry_run': True
            })
            return True

        # Send message
        try:
            message = await self.client.send_message(
                entity=self.source_group_id,
                message=message_text,
                file=str(file_path) if file_path else None,
                reply_to=reply_to_msg_id
            )

            message_id = message.id
            self.sent_messages[test_id] = message_id

            print(f"{Colors.GREEN}  Sent message ID: {message_id}{Colors.ENDC}")
            print(f"  Waiting {wait_seconds}s for bot to process...")
            await asyncio.sleep(wait_seconds)

            print(f"  Waiting {self.delay}s before next test...")
            await asyncio.sleep(self.delay)

            self.results['passed'].append({
                'test_id': test_id,
                'message_id': message_id
            })

            return True

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"{Colors.RED}  FAIL: {error_msg}{Colors.ENDC}\n")
            self.results['failed'].append({
                'test_id': test_id,
                'error': error_msg
            })
            return False

    async def run_tests(self, test_ids: Optional[List[str]] = None) -> None:
        """
        Run integration tests

        Args:
            test_ids: List of test IDs to run. If None, run all tests.
        """
        tests = self.load_test_data()

        # Filter tests if specific IDs requested
        if test_ids:
            filtered_tests = []
            for test_id in test_ids:
                found = False
                for test in tests:
                    if test.get('test_id') == test_id:
                        filtered_tests.append(test)
                        found = True
                        break

                if not found:
                    print(f"{Colors.YELLOW}Warning: Test '{test_id}' not found{Colors.ENDC}")

            tests = filtered_tests

        if not tests:
            print(f"{Colors.RED}No tests to run{Colors.ENDC}")
            return

        print(f"{Colors.BOLD}{Colors.HEADER}Starting Integration Tests{Colors.ENDC}")
        print(f"Tests to run: {len(tests)}")
        print(f"Delay between tests: {self.delay}s")
        if self.dry_run:
            print(f"{Colors.YELLOW}DRY RUN MODE - No messages will be sent{Colors.ENDC}")
        print()

        # Run each test
        for i, test in enumerate(tests, 1):
            print(f"{Colors.BOLD}[{i}/{len(tests)}]{Colors.ENDC}")
            await self.run_test(test)

        # Print summary
        self.print_summary()

    def print_summary(self) -> None:
        """Print test execution summary"""
        total = len(self.results['passed']) + len(self.results['failed']) + len(self.results['skipped'])

        print(f"\n{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.HEADER}SUMMARY{Colors.ENDC}\n")

        print(f"{Colors.GREEN}Passed: {len(self.results['passed'])}/{total}{Colors.ENDC}")
        for result in self.results['passed']:
            test_id = result['test_id']
            if result.get('dry_run'):
                print(f"  - {test_id} (dry run)")
            else:
                print(f"  - {test_id} (message ID: {result['message_id']})")

        if self.results['failed']:
            print(f"\n{Colors.RED}Failed: {len(self.results['failed'])}/{total}{Colors.ENDC}")
            for result in self.results['failed']:
                print(f"  - {result['test_id']}: {result['error']}")

        if self.results['skipped']:
            print(f"\n{Colors.YELLOW}Skipped: {len(self.results['skipped'])}/{total}{Colors.ENDC}")
            for result in self.results['skipped']:
                print(f"  - {result['test_id']}: {result['reason']}")

        print(f"\n{Colors.BOLD}{'=' * 60}{Colors.ENDC}")

    async def disconnect(self) -> None:
        """Disconnect Telethon client"""
        if self.client:
            await self.client.disconnect()
            print(f"\n{Colors.CYAN}Disconnected from Telegram{Colors.ENDC}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Integration test runner for Telegram Signal Translator Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --all                    # Run all tests
  %(prog)s --test INT-001 INT-002  # Run specific tests
  %(prog)s --dry-run               # Show what would be sent
  %(prog)s --list                  # List available tests
  %(prog)s --delay 45              # Set 45s delay between tests
        """
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all integration tests'
    )

    parser.add_argument(
        '--test',
        nargs='+',
        metavar='TEST_ID',
        help='Run specific tests by ID (e.g., INT-001 INT-002)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be sent without actually sending'
    )

    parser.add_argument(
        '--delay',
        type=int,
        default=30,
        metavar='SECONDS',
        help='Seconds to wait between tests (default: 30)'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available tests and exit'
    )

    args = parser.parse_args()

    # Validate arguments
    if not any([args.all, args.test, args.list]):
        parser.print_help()
        print(f"\n{Colors.RED}Error: Must specify --all, --test, or --list{Colors.ENDC}")
        sys.exit(1)

    # Initialize runner
    runner = IntegrationTestRunner(dry_run=args.dry_run, delay=args.delay)

    try:
        # Load test data first (for --list command)
        tests = runner.load_test_data()

        # Handle --list command
        if args.list:
            runner.list_tests(tests)
            return

        # Initialize Telegram client
        await runner.init_client()
        await runner.verify_group_access()

        # Run tests
        if args.all:
            await runner.run_tests()
        elif args.test:
            await runner.run_tests(args.test)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.ENDC}")
        sys.exit(130)

    except Exception as e:
        print(f"\n{Colors.RED}{Colors.BOLD}ERROR:{Colors.ENDC} {Colors.RED}{e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await runner.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
