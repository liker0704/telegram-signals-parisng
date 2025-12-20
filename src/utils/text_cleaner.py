"""Text cleaning utilities for filtering promotional content."""

import re
from typing import List

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Patterns to remove from messages
PROMO_PATTERNS: List[re.Pattern] = [
    # Any markdown link containing tribute.app (donation links)
    re.compile(
        r'\[[\*\s]*[^\]]*\]'  # Any link text (may contain asterisks)
        r'\(https?://t\.me/tribute/[^)]+\)',  # Tribute app URL
        re.IGNORECASE
    ),
    # Any markdown link to maxmotruk.com (training/courses)
    re.compile(
        r'\[[\*\s]*[^\]]*\]'  # Any link text
        r'\(https?://(?:www\.)?maxmotruk\.com[^)]*\)',  # maxmotruk URL
        re.IGNORECASE
    ),
    # Donation text patterns (with or without links)
    re.compile(
        r'\[[\*\s]*(?:Отправить донат|Donate to)[^\]]*\]'
        r'\([^)]+\)',
        re.IGNORECASE
    ),
    # Training patterns
    re.compile(
        r'\[[\*\s]*(?:Пройти обучение|Take training|Join course)[^\]]*\]'
        r'\([^)]+\)',
        re.IGNORECASE
    ),
]

# Patterns for formatting cleanup after removal
CLEANUP_PATTERNS: List[tuple] = [
    # Green emoji with surrounding formatting: **🟢**** ** etc
    (re.compile(r'\*{0,4}🟢\*{0,4}\s*\*{0,4}\s*'), ''),
    # Leftover pipe separators with whitespace/asterisks
    (re.compile(r'[\s\*]*\|[\s\*]*\|[\s\*]*'), ''),
    (re.compile(r'[\s\*]*\|[\s\*]*$', re.MULTILINE), ''),
    (re.compile(r'^[\s\*]*\|[\s\*]*', re.MULTILINE), ''),
    # Multiple asterisks in a row
    (re.compile(r'\*{3,}'), ''),
    # Orphaned asterisk pairs
    (re.compile(r'\*\*\s*\*\*'), ''),
]

# Pattern for trailing separators that might be left after removal
TRAILING_SEPARATOR_PATTERN = re.compile(r'(\s*\|\s*)+$')


def strip_promo_content(text: str) -> str:
    """
    Remove promotional content (donation links, course links) from message text.

    Args:
        text: Original message text

    Returns:
        Cleaned text with promo content removed
    """
    if not text:
        return text

    original_text = text
    cleaned = text

    # Apply promo removal patterns
    for pattern in PROMO_PATTERNS:
        cleaned = pattern.sub('', cleaned)

    # Apply cleanup patterns for leftover formatting
    for pattern, replacement in CLEANUP_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)

    # Clean up resulting formatting issues
    # Remove trailing pipe separators
    cleaned = TRAILING_SEPARATOR_PATTERN.sub('', cleaned)

    # Remove multiple consecutive newlines (more than 2)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    # Remove trailing whitespace on each line
    cleaned = '\n'.join(line.rstrip() for line in cleaned.split('\n'))

    # Remove trailing empty lines
    cleaned = cleaned.rstrip()

    # Log if we removed something
    if cleaned != original_text:
        removed_chars = len(original_text) - len(cleaned)
        logger.debug("Stripped promo content",
                    removed_chars=removed_chars,
                    original_len=len(original_text))

    return cleaned


def contains_promo_content(text: str) -> bool:
    """
    Check if text contains promotional content.

    Args:
        text: Text to check

    Returns:
        True if promo content detected
    """
    if not text:
        return False

    for pattern in PROMO_PATTERNS:
        if pattern.search(text):
            return True

    return False
