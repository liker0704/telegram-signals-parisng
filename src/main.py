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
from typing import Set

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
from src.api.health import start_health_server, stop_health_server

# Initialize logging
setup_logging(config.LOG_LEVEL, config.ENVIRONMENT)
logger = get_logger(__name__)

# Global state for graceful shutdown
_shutdown_event: asyncio.Event = None
_running_tasks: Set[asyncio.Task] = set()


def _task_done_callback(task: asyncio.Task) -> None:
    """Remove completed task from tracking set and log errors."""
    _running_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("Background task failed",
                    task_name=task.get_name(),
                    error=str(exc),
                    exc_info=exc)


def create_tracked_task(coro, name: str = None) -> asyncio.Task:
    """Create an asyncio task that is tracked for graceful shutdown."""
    task = asyncio.create_task(coro, name=name)
    _running_tasks.add(task)
    task.add_done_callback(_task_done_callback)
    return task


def _handle_shutdown_signal() -> None:
    """Handle shutdown signal by setting the shutdown event."""
    logger.info("Shutdown signal received")
    if _shutdown_event and not _shutdown_event.is_set():
        _shutdown_event.set()


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
            if is_signal(text, user_id=message.sender_id):
                # New signal with #Идея marker
                create_tracked_task(handle_new_signal(event), name=f"signal_{message.id}")
            elif message.is_reply:
                # Reply to some message - handler will check if parent is a signal
                create_tracked_task(handle_signal_update(event), name=f"update_{message.id}")
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
    """Main entry point with graceful shutdown support."""
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_shutdown_signal)

    try:
        # Initialize database
        logger.info("Initializing database connection...")
        await init_db()

        # Initialize Telegram clients
        logger.info("Initializing Telegram clients...")
        reader, publisher = await init_clients()

        # Verify group access
        logger.info("Verifying group access...")
        await verify_group_access(reader, publisher)

        # Register event handlers
        register_handlers(reader)

        # Start health check
        create_tracked_task(health_check_loop(), name="health_check")

        # Start HTTP health server
        await start_health_server()

        logger.info("Bot started, listening for signals...", health_port=config.API_PORT)

        # Run until shutdown
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(reader.run_until_disconnected()),
                asyncio.create_task(_shutdown_event.wait())
            ],
            return_when=asyncio.FIRST_COMPLETED
        )

    except Exception as e:
        logger.error("Fatal error in main", error=str(e))
        raise
    finally:
        logger.info("Initiating graceful shutdown...")

        # Stop health server
        try:
            await stop_health_server()
        except Exception as e:
            logger.warning("Error stopping health server", error=str(e))

        # Cancel running tasks
        for task in list(_running_tasks):
            task.cancel()

        if _running_tasks:
            await asyncio.gather(*_running_tasks, return_exceptions=True)

        # Cleanup
        try:
            await disconnect_clients()
        except Exception as e:
            logger.warning("Error cleaning up clients", error=str(e))

        try:
            await close_db()
        except Exception as e:
            logger.warning("Error closing database", error=str(e))

        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Application crashed", error=str(e))
        sys.exit(1)
