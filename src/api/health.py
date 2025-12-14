"""
Health check HTTP server for monitoring.

Provides /health endpoint for external health checks (Render.com, etc.)
"""

import time
import asyncio
from typing import Optional
from aiohttp import web

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Server state
_server_start_time: Optional[float] = None
_runner: Optional[web.AppRunner] = None
_site: Optional[web.TCPSite] = None


async def health_handler(request: web.Request) -> web.Response:
    """Handle health check requests."""
    status = {
        "status": "ok",
        "uptime_seconds": int(time.time() - _server_start_time) if _server_start_time else 0,
        "environment": config.ENVIRONMENT,
    }

    # Check database
    try:
        from src.db.connection import get_pool
        pool = get_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
            status["database"] = "connected"
        else:
            status["database"] = "not_initialized"
    except Exception as e:
        status["database"] = "disconnected"
        logger.debug("Health check: database error", error=str(e))

    # Check Telegram clients
    try:
        from src.telethon_setup import get_reader_client, get_publisher_client

        reader = get_reader_client()
        status["reader_client"] = "connected" if reader and reader.is_connected() else "disconnected"

        publisher = get_publisher_client()
        status["publisher_client"] = "connected" if publisher and publisher.is_connected() else "disconnected"
    except Exception as e:
        status["reader_client"] = "unknown"
        status["publisher_client"] = "unknown"
        logger.debug("Health check: client error", error=str(e))

    return web.json_response(status)


async def start_health_server() -> None:
    """Start the health check HTTP server."""
    global _server_start_time, _runner, _site

    _server_start_time = time.time()

    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    _runner = web.AppRunner(app)
    await _runner.setup()

    _site = web.TCPSite(_runner, "0.0.0.0", config.API_PORT)
    await _site.start()

    logger.info("Health server started", port=config.API_PORT)


async def stop_health_server() -> None:
    """Stop the health check HTTP server."""
    global _runner, _site

    if _runner:
        await _runner.cleanup()
        _runner = None
        _site = None
        logger.info("Health server stopped")
