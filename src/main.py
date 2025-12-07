"""
Telegram Signal Translator Bot - Main Entry Point

An asynchronous service that:
- Reads trading signals (#Идея) from a Russian Telegram group
- Translates text + OCR images via Gemini API
- Posts translated signals to an English Telegram group
- Maintains message threading (reply chains)
"""

import asyncio
import signal
import sys

from telethon import events

from src.config import config
from src.utils.logger import setup_logging, get_logger
from src.db.connection import init_db, close_db
from src.telethon_setup import (
    init_clients,
    verify_group_access,
    disconnect_clients,
    get_reader_client
)
from src.handlers.signal_handler import handle_new_signal
from src.handlers.update_handler import handle_signal_update
from src.parsers.signal_parser import is_signal

# Initialize logging
setup_logging(config.LOG_LEVEL, config.ENVIRONMENT)
logger = get_logger(__name__)


def register_handlers(reader_client) -> None:
    """
    Register event handlers for the reader client.

    Handlers:
    - New signal (#Идея in message)
    - Signal update (reply to existing signal)
    """

    @reader_client.on(events.NewMessage(chats=[config.SOURCE_GROUP_ID], incoming=True, outgoing=True))
    async def on_new_message(event):
        """
        Handle any new message in the source group.

        Routes messages to appropriate handler:
        - If contains #Идея -> handle_new_signal (creates new signal)
        - If is a reply (to any message) -> handle_signal_update (checks if parent is signal)
        - Otherwise -> ignore

        Note: incoming=True, outgoing=True allows receiving both:
        - Messages from other users (incoming)
        - Messages from the reader account itself (outgoing) - useful for testing
        In production, you may want to set outgoing=False to only process others' messages.
        """
        message = event.message
        text = message.text or ''

        try:
            if is_signal(text):
                # New signal with #Идея marker
                asyncio.create_task(handle_new_signal(event))
            elif message.is_reply:
                # Reply to some message - handler will check if parent is a signal
                asyncio.create_task(handle_signal_update(event))
            # else: regular message without #Идея and not a reply - ignore
        except Exception as e:
            logger.error("Error dispatching message handler",
                        message_id=message.id,
                        error=str(e))

    logger.info("Event handlers registered",
                source_group=config.SOURCE_GROUP_ID)


async def health_check_loop():
    """
    Periodic health check for database and client connections.

    Runs every 5 minutes to verify:
    - Database connection pool is healthy
    - Telethon clients are connected
    """
    while True:
        await asyncio.sleep(300)  # 5 minutes

        try:
            # Check database
            from src.db.connection import get_pool
            pool = get_pool()
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
            logger.debug("Health check: Database OK")

            # Check Telethon clients
            reader = get_reader_client()
            if reader.is_connected():
                logger.debug("Health check: Reader client OK")
            else:
                logger.warning("Health check: Reader client disconnected")

        except Exception as e:
            logger.error("Health check failed", error=str(e))


async def main():
    """
    Main entry point for the bot.

    Initialization sequence:
    1. Setup logging
    2. Initialize database connection pool
    3. Initialize Telethon clients (Reader + Publisher)
    4. Verify group access
    5. Register event handlers
    6. Start health check loop
    7. Run until disconnected
    """
    logger.info("Starting Telegram Signal Translator Bot",
                environment=config.ENVIRONMENT,
                source_group=config.SOURCE_GROUP_ID,
                target_group=config.TARGET_GROUP_ID)

    try:
        # Step 1: Initialize database
        logger.info("Initializing database connection...")
        await init_db()

        # Step 2: Initialize Telethon clients
        logger.info("Initializing Telegram clients...")
        reader, publisher = await init_clients()

        # Step 3: Verify group access
        logger.info("Verifying group access...")
        await verify_group_access(reader, publisher)

        # Step 4: Register handlers
        register_handlers(reader)

        # Step 5: Start health check
        asyncio.create_task(health_check_loop())

        logger.info("Bot started successfully. Listening for signals...")

        # Keep running until disconnected
        await reader.run_until_disconnected()

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=True)
        raise
    finally:
        # Cleanup
        logger.info("Shutting down...")
        await disconnect_clients()
        await close_db()
        logger.info("Shutdown complete")


def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Received shutdown signal", signal=signum)
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Run the bot
    asyncio.run(main())
