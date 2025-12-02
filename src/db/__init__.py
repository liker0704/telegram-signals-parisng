"""Database module for Telegram Signal Translator Bot."""

from src.db.connection import (
    init_db,
    close_db,
    get_pool,
    get_connection,
    execute,
    fetch,
    fetchrow,
    fetchval,
)

from src.db.queries import (
    db_insert_signal,
    db_update_signal,
    db_find_signal_by_source_msg,
    db_find_signal_by_id,
    db_insert_signal_update,
    db_update_signal_update,
    db_find_update_by_source_msg,
    db_get_cached_translation,
    db_cache_translation,
)

__all__ = [
    # Connection functions
    "init_db",
    "close_db",
    "get_pool",
    "get_connection",
    "execute",
    "fetch",
    "fetchrow",
    "fetchval",
    # Query functions
    "db_insert_signal",
    "db_update_signal",
    "db_find_signal_by_source_msg",
    "db_find_signal_by_id",
    "db_insert_signal_update",
    "db_update_signal_update",
    "db_find_update_by_source_msg",
    "db_get_cached_translation",
    "db_cache_translation",
]
