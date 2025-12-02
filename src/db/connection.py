"""Database connection management using asyncpg."""

import asyncpg
from typing import Optional
from contextlib import asynccontextmanager

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def init_db() -> asyncpg.Pool:
    """
    Initialize the database connection pool.

    Returns:
        asyncpg.Pool: The connection pool

    Raises:
        Exception: If connection fails
    """
    global _pool

    if _pool is not None:
        return _pool

    logger.info("Initializing database connection pool",
                host=config.POSTGRES_HOST,
                database=config.POSTGRES_DB)

    _pool = await asyncpg.create_pool(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        database=config.POSTGRES_DB,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )

    logger.info("Database connection pool initialized")
    return _pool


async def close_db() -> None:
    """Close the database connection pool."""
    global _pool

    if _pool is not None:
        logger.info("Closing database connection pool")
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """
    Get the current connection pool.

    Returns:
        asyncpg.Pool: The connection pool

    Raises:
        RuntimeError: If pool is not initialized
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool


@asynccontextmanager
async def get_connection():
    """
    Get a connection from the pool as async context manager.

    Usage:
        async with get_connection() as conn:
            result = await conn.fetch("SELECT * FROM signals")
    """
    pool = get_pool()
    async with pool.acquire() as connection:
        yield connection


async def execute(query: str, *args) -> str:
    """Execute a query and return status."""
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def fetch(query: str, *args) -> list:
    """Execute a query and return all results."""
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args):
    """Execute a query and return single row."""
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    """Execute a query and return single value."""
    async with get_connection() as conn:
        return await conn.fetchval(query, *args)
