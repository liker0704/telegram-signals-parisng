"""
Signal Parser Module
Parse trading signals to extract structured fields using regex.
"""

import re
from typing import Optional


def is_signal(text: str) -> bool:
    """
    Check if text contains #Идея marker.

    Args:
        text: Message text to check

    Returns:
        True if text contains signal marker, False otherwise
    """
    return '#Идея' in (text or '')


def parse_trading_signal(text: str) -> dict:
    """
    Extract structured trading fields from signal text.
    All fields are optional - return None for missing fields.

    Args:
        text: Signal message text to parse

    Returns:
        dict with keys:
        - pair: str | None        # e.g., "BTC/USDT", "XION/USDT"
        - direction: str | None   # "LONG" or "SHORT" (uppercase)
        - timeframe: str | None   # e.g., "15мин", "1H", "4H", "D", "W"
        - entry_range: str | None # e.g., "0.98-0.9283"
        - tp1: float | None       # Take Profit 1
        - tp2: float | None       # Take Profit 2
        - tp3: float | None       # Take Profit 3
        - sl: float | None        # Stop Loss
        - risk_percent: float | None

    Example:
        >>> text = '''#Идея BTC/USDT 4H LONG
        ... Вход: 95000-96000
        ... TP1: $100000
        ... TP2: $105000
        ... SL: $90000
        ... Риск: 2%'''
        >>> result = parse_trading_signal(text)
        >>> result['pair']
        'BTC/USDT'
        >>> result['direction']
        'LONG'
        >>> result['tp1']
        100000.0
    """
    if not text:
        return _empty_signal_dict()

    fields = {}

    # Extract Pair: BTC/USDT, XION/USDT, etc.
    pair_match = re.search(r'\b([A-Z][A-Z0-9]*\/[A-Z][A-Z0-9]*)\b', text)
    fields['pair'] = pair_match.group(1) if pair_match else None

    # Extract Direction: LONG or SHORT (case-insensitive, normalized to uppercase)
    direction_match = re.search(r'\b(LONG|SHORT)\b', text, re.IGNORECASE)
    fields['direction'] = direction_match.group(1).upper() if direction_match else None

    # Extract Timeframe: 15мин, 1H, 4H, D, W
    # Use word boundaries to avoid matching single letters in words
    timeframe_match = re.search(r'\b(\d+\s*[мм][и]?[н]?|[1-9]\d*[Hh]|[Dd]|[Ww])\b', text)
    fields['timeframe'] = timeframe_match.group(1).strip() if timeframe_match else None

    # Extract Entry Range: Вход: 0.98-0.9283 or Входа: ...
    entry_match = re.search(r'[Вв]ход[а]?:?\s*(\d+\.?\d*[-–]\d+\.?\d*)', text)
    fields['entry_range'] = entry_match.group(1) if entry_match else None

    # Extract TP1: TP1: $100000 or TP1: 100000
    tp1_match = re.search(r'TP1:?\s*\$?(\d+\.?\d*)', text, re.IGNORECASE)
    fields['tp1'] = float(tp1_match.group(1)) if tp1_match else None

    # Extract TP2: TP2: $105000 or TP2: 105000
    tp2_match = re.search(r'TP2:?\s*\$?(\d+\.?\d*)', text, re.IGNORECASE)
    fields['tp2'] = float(tp2_match.group(1)) if tp2_match else None

    # Extract TP3: TP3: $110000 or TP3: 110000
    tp3_match = re.search(r'TP3:?\s*\$?(\d+\.?\d*)', text, re.IGNORECASE)
    fields['tp3'] = float(tp3_match.group(1)) if tp3_match else None

    # Extract SL: SL: $90000 or Стоп: 90000
    sl_match = re.search(r'(?:SL|Стоп):?\s*\$?(\d+\.?\d*)', text, re.IGNORECASE)
    fields['sl'] = float(sl_match.group(1)) if sl_match else None

    # Extract Risk: Риск: 2% or риск: 2
    risk_match = re.search(r'[Рр]иск:?\s*(\d+\.?\d*)%?', text)
    fields['risk_percent'] = float(risk_match.group(1)) if risk_match else None

    return fields


def _empty_signal_dict() -> dict:
    """
    Return an empty signal dictionary with all fields set to None.

    Returns:
        Dictionary with all signal fields initialized to None
    """
    return {
        'pair': None,
        'direction': None,
        'timeframe': None,
        'entry_range': None,
        'tp1': None,
        'tp2': None,
        'tp3': None,
        'sl': None,
        'risk_percent': None
    }
