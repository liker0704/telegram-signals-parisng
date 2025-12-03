"""Telethon client initialization and management."""

from pathlib import Path
from typing import Optional, Tuple

from telethon import TelegramClient
from telethon.sessions import StringSession

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Global client instances
_reader_client: Optional[TelegramClient] = None
_publisher_client: Optional[TelegramClient] = None


async def init_reader_client() -> TelegramClient:
    """
    Initialize the Reader client (Account A).
    This client listens to the source group for signals.

    Uses StringSession if READER_SESSION_STRING is provided in environment,
    otherwise falls back to file-based session (requires interactive auth).

    Returns:
        TelegramClient: Initialized and connected reader client

    Raises:
        ValueError: If neither session string nor valid session file is available
    """
    global _reader_client

    if _reader_client is not None and _reader_client.is_connected():
        return _reader_client

    # Determine session type
    if config.READER_SESSION_STRING:
        # Use StringSession (preferred for Docker)
        session = StringSession(config.READER_SESSION_STRING)
        logger.info("Initializing Reader client with StringSession",
                    api_id=config.READER_API_ID)
    else:
        # Use file-based session (legacy, requires interactive auth)
        session_path = Path(config.READER_SESSION_FILE)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session = config.READER_SESSION_FILE
        logger.info("Initializing Reader client with file-based session",
                    api_id=config.READER_API_ID,
                    session_file=config.READER_SESSION_FILE)
        logger.warning("File-based sessions require interactive authentication. "
                      "Consider using READER_SESSION_STRING instead.")

    _reader_client = TelegramClient(
        session=session,
        api_id=config.READER_API_ID,
        api_hash=config.READER_API_HASH
    )

    # Connect and authenticate
    # If using StringSession, this should work without interaction
    # If using file-based session without existing file, this will require interaction
    await _reader_client.connect()

    if not await _reader_client.is_user_authorized():
        if config.READER_SESSION_STRING:
            raise ValueError(
                "READER_SESSION_STRING provided but authorization failed. "
                "The session string may be invalid or expired. "
                "Please regenerate it using auth_local.py"
            )
        else:
            # File-based session requires interactive auth
            await _reader_client.start(phone=config.READER_PHONE)

    # Verify connection
    me = await _reader_client.get_me()
    logger.info("Reader client connected",
                user_id=me.id,
                username=me.username,
                session_type="StringSession" if config.READER_SESSION_STRING else "FileSession")

    return _reader_client


async def init_publisher_client() -> TelegramClient:
    """
    Initialize the Publisher client (Account B).
    This client posts translated signals to the target group.

    Uses StringSession if PUBLISHER_SESSION_STRING is provided in environment,
    otherwise falls back to file-based session (requires interactive auth).

    Returns:
        TelegramClient: Initialized and connected publisher client

    Raises:
        ValueError: If neither session string nor valid session file is available
    """
    global _publisher_client

    if _publisher_client is not None and _publisher_client.is_connected():
        return _publisher_client

    # Determine session type
    if config.PUBLISHER_SESSION_STRING:
        # Use StringSession (preferred for Docker)
        session = StringSession(config.PUBLISHER_SESSION_STRING)
        logger.info("Initializing Publisher client with StringSession",
                    api_id=config.PUBLISHER_API_ID)
    else:
        # Use file-based session (legacy, requires interactive auth)
        session_path = Path(config.PUBLISHER_SESSION_FILE)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session = config.PUBLISHER_SESSION_FILE
        logger.info("Initializing Publisher client with file-based session",
                    api_id=config.PUBLISHER_API_ID,
                    session_file=config.PUBLISHER_SESSION_FILE)
        logger.warning("File-based sessions require interactive authentication. "
                      "Consider using PUBLISHER_SESSION_STRING instead.")

    _publisher_client = TelegramClient(
        session=session,
        api_id=config.PUBLISHER_API_ID,
        api_hash=config.PUBLISHER_API_HASH
    )

    # Connect and authenticate
    # If using StringSession, this should work without interaction
    # If using file-based session without existing file, this will require interaction
    await _publisher_client.connect()

    if not await _publisher_client.is_user_authorized():
        if config.PUBLISHER_SESSION_STRING:
            raise ValueError(
                "PUBLISHER_SESSION_STRING provided but authorization failed. "
                "The session string may be invalid or expired. "
                "Please regenerate it using auth_local.py"
            )
        else:
            # File-based session requires interactive auth
            await _publisher_client.start(phone=config.PUBLISHER_PHONE)

    # Verify connection
    me = await _publisher_client.get_me()
    logger.info("Publisher client connected",
                user_id=me.id,
                username=me.username,
                session_type="StringSession" if config.PUBLISHER_SESSION_STRING else "FileSession")

    return _publisher_client


async def init_clients() -> Tuple[TelegramClient, TelegramClient]:
    """
    Initialize both Reader and Publisher clients.

    Returns:
        Tuple of (reader_client, publisher_client)
    """
    reader = await init_reader_client()
    publisher = await init_publisher_client()
    return reader, publisher


async def verify_group_access(
    reader: TelegramClient,
    publisher: TelegramClient
) -> bool:
    """
    Verify that clients have access to their respective groups.

    Args:
        reader: Reader client
        publisher: Publisher client

    Returns:
        bool: True if both have access

    Raises:
        Exception: If access verification fails
    """
    # Verify Reader has access to source group
    try:
        source_entity = await reader.get_entity(config.SOURCE_GROUP_ID)
        logger.info("Reader has access to source group",
                    group_id=config.SOURCE_GROUP_ID,
                    group_title=getattr(source_entity, 'title', 'N/A'))
    except Exception as e:
        logger.error("Reader cannot access source group",
                     group_id=config.SOURCE_GROUP_ID,
                     error=str(e))
        raise

    # Verify Publisher has access to target group
    try:
        target_entity = await publisher.get_entity(config.TARGET_GROUP_ID)
        logger.info("Publisher has access to target group",
                    group_id=config.TARGET_GROUP_ID,
                    group_title=getattr(target_entity, 'title', 'N/A'))
    except Exception as e:
        logger.error("Publisher cannot access target group",
                     group_id=config.TARGET_GROUP_ID,
                     error=str(e))
        raise

    return True


def get_reader_client() -> TelegramClient:
    """Get the reader client instance."""
    if _reader_client is None:
        raise RuntimeError("Reader client not initialized. Call init_reader_client() first.")
    return _reader_client


def get_publisher_client() -> TelegramClient:
    """Get the publisher client instance."""
    if _publisher_client is None:
        raise RuntimeError("Publisher client not initialized. Call init_publisher_client() first.")
    return _publisher_client


async def disconnect_clients() -> None:
    """Disconnect both clients gracefully."""
    global _reader_client, _publisher_client

    if _reader_client:
        logger.info("Disconnecting Reader client")
        await _reader_client.disconnect()
        _reader_client = None

    if _publisher_client:
        logger.info("Disconnecting Publisher client")
        await _publisher_client.disconnect()
        _publisher_client = None
