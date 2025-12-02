"""
Message Formatter Module

Build final messages for posting and restore trading terms after translation.
"""

import re


def build_final_message(
    translated_text: str,
    image_ocr: str | None = None,
    parsed_fields: dict | None = None
) -> str:
    """
    Construct final English message to post.

    Args:
        translated_text: Translated signal text
        image_ocr: OCR text from chart image (optional)
        parsed_fields: Extracted trading fields (optional, not currently used)

    Returns:
        Final formatted message string

    Example:
        >>> build_final_message("Entry: 50000", "Chart shows BTC/USDT")
        'Entry: 50000\\n\\n_Chart OCR:_\\nChart shows BTC/USDT'
    """
    parts = [translated_text]

    if image_ocr:
        parts.append(f"\n\n_Chart OCR:_\n{image_ocr}")

    return '\n'.join(parts)


def restore_trading_terms(text: str) -> str:
    """
    Post-process translation to ensure trading terms are preserved.

    Google Translate sometimes lowercases or spaces out terms.
    This function restores them to the proper trading format.

    Fixes:
        - 'tp 1' -> 'TP1'
        - 'tp 2' -> 'TP2'
        - 'tp 3' -> 'TP3'
        - 'sl ' -> 'SL '
        - 'long' -> 'LONG'
        - 'short' -> 'SHORT'

    Args:
        text: Text with potentially malformed trading terms

    Returns:
        Text with trading terms restored to proper format

    Example:
        >>> text = "tp 1: $100000, tp 2: $105000, direction: long"
        >>> restore_trading_terms(text)
        'TP1: $100000, TP2: $105000, direction: LONG'
    """
    replacements = {
        'tp 1': 'TP1',
        'tp 2': 'TP2',
        'tp 3': 'TP3',
        'tp1': 'TP1',
        'tp2': 'TP2',
        'tp3': 'TP3',
        'sl ': 'SL ',
        'sl:': 'SL:',
        ' long': ' LONG',
        ' short': ' SHORT',
    }

    result = text
    for original, replacement in replacements.items():
        # Case-insensitive replacement
        result = re.sub(re.escape(original), replacement, result, flags=re.IGNORECASE)

    return result
