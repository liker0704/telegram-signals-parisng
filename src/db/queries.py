"""Database queries for signals and signal_updates tables."""

from datetime import datetime, timezone
from typing import Optional

from src.db.connection import fetchrow, fetchval, execute
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Whitelist of allowed columns for UPDATE operations
ALLOWED_SIGNAL_COLUMNS = frozenset({
    'status', 'pair', 'direction', 'timeframe', 'entry_range',
    'tp1', 'tp2', 'tp3', 'sl', 'risk_percent', 'target_chat_id',
    'target_message_id', 'translated_text', 'image_ocr_text',
    'processed_at', 'error_message', 'image_local_path',
    'forward_chat_id', 'forward_message_id'
})

ALLOWED_SIGNAL_UPDATE_COLUMNS = frozenset({
    'status', 'pair', 'direction', 'timeframe', 'entry_range',
    'tp1', 'tp2', 'tp3', 'sl', 'risk_percent', 'target_chat_id',
    'target_message_id', 'translated_text', 'image_ocr_text',
    'processed_at', 'error_message', 'image_local_path',
    'forward_chat_id', 'forward_message_id'
})


# =============================================================================
# SIGNALS TABLE OPERATIONS
# =============================================================================

async def db_insert_signal(signal_data: dict) -> int:
    """
    Insert a new signal into the database.

    Args:
        signal_data: Dict with keys matching signals table columns:
            - source_chat_id (required)
            - source_message_id (required)
            - source_user_id (required)
            - original_text (required)
            - status (default: 'PENDING')
            - pair, direction, timeframe, entry_range (optional)
            - tp1, tp2, tp3, sl, risk_percent (optional)

    Returns:
        int: The ID of the inserted signal
    """
    query = """
        INSERT INTO signals (
            source_chat_id, source_message_id, source_user_id,
            original_text, status, created_at,
            pair, direction, timeframe, entry_range,
            tp1, tp2, tp3, sl, risk_percent
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
        )
        RETURNING id
    """

    signal_id = await fetchval(
        query,
        signal_data.get('source_chat_id'),
        signal_data.get('source_message_id'),
        signal_data.get('source_user_id'),
        signal_data.get('original_text'),
        signal_data.get('status', 'PENDING'),
        signal_data.get('created_at', datetime.now(timezone.utc)),
        signal_data.get('pair'),
        signal_data.get('direction'),
        signal_data.get('timeframe'),
        signal_data.get('entry_range'),
        signal_data.get('tp1'),
        signal_data.get('tp2'),
        signal_data.get('tp3'),
        signal_data.get('sl'),
        signal_data.get('risk_percent'),
    )

    logger.info("Inserted signal", signal_id=signal_id,
                source_msg=signal_data.get('source_message_id'))
    return signal_id


async def db_update_signal(signal_id: int, data: dict) -> None:
    """
    Update a signal with the given data.

    Args:
        signal_id: The signal ID to update
        data: Dict of column names to new values
    """
    if not data:
        return

    # Validate column names against whitelist
    invalid_keys = set(data.keys()) - ALLOWED_SIGNAL_COLUMNS
    if invalid_keys:
        raise ValueError(f"Invalid column names: {invalid_keys}")

    # Build dynamic UPDATE query
    set_clauses = []
    values = []
    for i, (key, value) in enumerate(data.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        values.append(value)

    values.append(signal_id)
    query = f"""
        UPDATE signals
        SET {', '.join(set_clauses)}
        WHERE id = ${len(values)}
    """

    await execute(query, *values)
    logger.debug("Updated signal", signal_id=signal_id, fields=list(data.keys()))


async def db_find_signal_by_source_msg(
    source_chat_id: int,
    source_message_id: int
) -> Optional[dict]:
    """
    Find a signal by source chat and message ID.

    Returns:
        dict or None: The signal record as dict, or None if not found
    """
    query = """
        SELECT * FROM signals
        WHERE source_chat_id = $1 AND source_message_id = $2
    """
    row = await fetchrow(query, source_chat_id, source_message_id)
    return dict(row) if row else None


async def db_find_signal_by_id(signal_id: int) -> Optional[dict]:
    """Find a signal by its ID."""
    query = "SELECT * FROM signals WHERE id = $1"
    row = await fetchrow(query, signal_id)
    return dict(row) if row else None


# =============================================================================
# SIGNAL_UPDATES TABLE OPERATIONS
# =============================================================================

async def db_insert_signal_update(update_data: dict) -> int:
    """
    Insert a new signal update (reply) into the database.

    Args:
        update_data: Dict with keys:
            - signal_id (required): Parent signal ID
            - source_chat_id (required)
            - source_message_id (required)
            - source_user_id (optional)
            - original_text (required)
            - status (default: 'PENDING')

    Returns:
        int: The ID of the inserted update
    """
    query = """
        INSERT INTO signal_updates (
            signal_id, source_chat_id, source_message_id, source_user_id,
            original_text, status, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
    """

    update_id = await fetchval(
        query,
        update_data.get('signal_id'),
        update_data.get('source_chat_id'),
        update_data.get('source_message_id'),
        update_data.get('source_user_id'),
        update_data.get('original_text'),
        update_data.get('status', 'PENDING'),
        update_data.get('created_at', datetime.now(timezone.utc)),
    )

    logger.info("Inserted signal update", update_id=update_id,
                signal_id=update_data.get('signal_id'))
    return update_id


async def db_update_signal_update(update_id: int, data: dict) -> None:
    """Update a signal_update record."""
    if not data:
        return

    # Validate column names against whitelist
    invalid_keys = set(data.keys()) - ALLOWED_SIGNAL_UPDATE_COLUMNS
    if invalid_keys:
        raise ValueError(f"Invalid column names: {invalid_keys}")

    set_clauses = []
    values = []
    for i, (key, value) in enumerate(data.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        values.append(value)

    values.append(update_id)
    query = f"""
        UPDATE signal_updates
        SET {', '.join(set_clauses)}
        WHERE id = ${len(values)}
    """

    await execute(query, *values)
    logger.debug("Updated signal_update", update_id=update_id)


async def db_find_update_by_source_msg(
    source_chat_id: int,
    source_message_id: int
) -> Optional[dict]:
    """Find a signal update by source message."""
    query = """
        SELECT * FROM signal_updates
        WHERE source_chat_id = $1 AND source_message_id = $2
    """
    row = await fetchrow(query, source_chat_id, source_message_id)
    return dict(row) if row else None


# =============================================================================
# TRANSLATION CACHE OPERATIONS
# =============================================================================

async def db_get_cached_translation(source_text_hash: str) -> Optional[str]:
    """
    Get cached translation by source text hash.

    Returns:
        str or None: The cached translated text
    """
    query = """
        UPDATE translation_cache
        SET usage_count = usage_count + 1, last_used_at = NOW()
        WHERE source_text_hash = $1
        RETURNING translated_text
    """
    return await fetchval(query, source_text_hash)


async def db_cache_translation(
    source_text_hash: str,
    source_text: str,
    translated_text: str,
    model: str = "gemini"
) -> None:
    """Cache a translation."""
    query = """
        INSERT INTO translation_cache (
            source_text_hash, source_text, translated_text, model
        ) VALUES ($1, $2, $3, $4)
        ON CONFLICT (source_text_hash) DO UPDATE SET
            translated_text = EXCLUDED.translated_text,
            last_used_at = NOW(),
            usage_count = translation_cache.usage_count + 1
    """
    await execute(query, source_text_hash, source_text, translated_text, model)
