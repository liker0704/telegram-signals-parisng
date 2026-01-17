"""Structured logging setup using structlog."""

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

# Project root for absolute paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Third-party loggers that should be quieter
NOISY_LOGGERS = [
    "telethon",
    "httpx",
    "httpcore",
    "openai",
    "anthropic",
    "langchain",
    "google.generativeai",
]

# Sensitive data patterns to mask in logs
SENSITIVE_PATTERNS = [
    (re.compile(r'(api[_-]?key\s*[=:]\s*)([^\s,;]+)', re.IGNORECASE), r'\1***MASKED***'),
    (re.compile(r'(token\s*[=:]\s*)([^\s,;]+)', re.IGNORECASE), r'\1***MASKED***'),
    (re.compile(r'(password\s*[=:]\s*)([^\s,;]+)', re.IGNORECASE), r'\1***MASKED***'),
    (re.compile(r'(secret\s*[=:]\s*)([^\s,;]+)', re.IGNORECASE), r'\1***MASKED***'),
    (re.compile(r'(authorization\s*[=:]\s*)([^\s,;]+)', re.IGNORECASE), r'\1***MASKED***'),
    (re.compile(r'(bearer\s+)([^\s,;]+)', re.IGNORECASE), r'\1***MASKED***'),

    # JSON format with quotes - "key": "value"
    (re.compile(r'("(?:api[_-]?key|token|password|secret|session[_-]?string|authorization)"\s*:\s*")([^"]+)(")', re.IGNORECASE), r'\1***MASKED***\3'),

    # Session strings (Telegram Telethon format - base64-like long strings)
    (re.compile(r'(session[_-]?string\s*[=:]\s*)([A-Za-z0-9+/=]{20,})', re.IGNORECASE), r'\1***MASKED***'),

    # Phone numbers (international format)
    (re.compile(r'(\+\d{1,3}[\s-]?)(\d{3,4}[\s-]?\d{3,4}[\s-]?\d{2,4})'), r'\1***MASKED***'),
]


def mask_sensitive_data(logger, method_name, event_dict):
    """
    Mask sensitive data in log events.

    Applies regex patterns to string values in event_dict to hide
    API keys, tokens, passwords, and other secrets.

    Args:
        logger: The logger instance
        method_name: The logging method name
        event_dict: The event dictionary to process

    Returns:
        Modified event_dict with sensitive data masked
    """
    for key, value in event_dict.items():
        if isinstance(value, str):
            for pattern, replacement in SENSITIVE_PATTERNS:
                value = pattern.sub(replacement, value)
            event_dict[key] = value
    return event_dict


def setup_logging(log_level: str = "INFO", environment: str = "production") -> None:
    """
    Configure structlog based on environment.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        environment: Environment name (development, staging, production)
    """
    # Set up stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Common processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        mask_sensitive_data,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if environment == "development":
        # Pretty console output for development
        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
        )
    else:
        # JSON output for production
        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )

    # Apply formatter to root logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Add rotating file handler for production
    if environment == "production":
        log_dir = PROJECT_ROOT / "logs"
        log_dir.mkdir(exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_dir / "app.log"),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name, typically __name__

    Returns:
        Configured structlog BoundLogger instance
    """
    return structlog.get_logger(name)
