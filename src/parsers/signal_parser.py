"""
Signal Parser Module
Parse trading signals to extract structured fields using regex.
"""

import re


def is_signal(text: str) -> bool:
    """
    Check if text contains signal marker (case-insensitive).

    Supports:
    - #Идея / #идея (Cyrillic)
    - #Idea / #idea (Latin)

    Args:
        text: Message text to check

    Returns:
        True if text contains signal marker, False otherwise
    """
    if not text:
        return False
    text_lower = text.lower()
    return '#идея' in text_lower or '#idea' in text_lower


def parse_trading_signal(text: str) -> dict:
    """
    Extract structured trading fields from signal text.
    All fields are optional - return None for missing fields.

    Supports both English and Russian formats:
    - Direction: LONG/SHORT or ЛОНГ/ШОРТ
    - Take profits: TP1/TP2/TP3 or Тейк 1/Тейк 2/Тейк 3
    - Timeframe: 15M, 5M, 1H, 4H, 15М, 5М etc.

    Args:
        text: Signal message text to parse

    Returns:
        dict with keys:
        - pair: str | None        # e.g., "BTC/USDT", "XION/USDT"
        - direction: str | None   # "LONG" or "SHORT" (uppercase)
        - timeframe: str | None   # e.g., "15M", "1H", "4H", "D", "W"
        - entry_range: str | None # e.g., "0.98-0.9283"
        - tp1: float | None       # Take Profit 1
        - tp2: float | None       # Take Profit 2
        - tp3: float | None       # Take Profit 3
        - sl: float | None        # Stop Loss
        - risk_percent: float | None

    Example:
        >>> text = '''#идея Торговая идея на BTC/USDT 15М ШОРТ
        ... Вход: 95000-96000
        ... Тейк 1: 100000
        ... Тейк 2: 105000
        ... Стоп: 90000'''
        >>> result = parse_trading_signal(text)
        >>> result['pair']
        'BTC/USDT'
        >>> result['direction']
        'SHORT'
    """
    if not text:
        return _empty_signal_dict()

    fields = {}

    # Extract Pair: BTC/USDT, XION/USDT, YBU/USDT, etc.
    pair_match = re.search(r'\b([A-Z][A-Z0-9]*\/[A-Z][A-Z0-9]*)\b', text)
    fields['pair'] = pair_match.group(1) if pair_match else None

    # Extract Direction: LONG/SHORT (English) or ЛОНГ/ШОРТ (Russian)
    # Normalize to uppercase English
    direction_match = re.search(r'\b(LONG|SHORT|ЛОНГ|ШОРТ)\b', text, re.IGNORECASE)
    if direction_match:
        direction = direction_match.group(1).upper()
        # Normalize Russian to English
        if direction in ('ЛОНГ', 'лонг'):
            direction = 'LONG'
        elif direction in ('ШОРТ', 'шорт'):
            direction = 'SHORT'
        fields['direction'] = direction
    else:
        fields['direction'] = None

    # Extract Timeframe: 15M, 5M, 1H, 4H, D, W (both English M and Russian М)
    timeframe_match = re.search(r'\b(\d+\s*[MМmм]|\d+\s*[Hh]|[Dd]|[Ww])\b', text)
    if timeframe_match:
        tf = timeframe_match.group(1).strip().upper()
        # Normalize Russian М to English M
        tf = tf.replace('М', 'M')
        fields['timeframe'] = tf
    else:
        fields['timeframe'] = None

    # Extract Entry Range: Вход: 0.4852 - 0.4922 or Вход: 0.4852-0.4922
    entry_match = re.search(r'[Вв]ход[а]?:?\s*(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)', text)
    if entry_match:
        fields['entry_range'] = f"{entry_match.group(1)}-{entry_match.group(2)}"
    else:
        fields['entry_range'] = None

    # Extract TP1: "TP1: 100000" or "Тейк 1: 0.4773" or "Тейк1: 0.4773"
    tp1_match = re.search(r'(?:TP\s*1|Тейк\s*1):?\s*\$?(\d+\.?\d*)', text, re.IGNORECASE)
    fields['tp1'] = float(tp1_match.group(1)) if tp1_match else None

    # Extract TP2: "TP2: 105000" or "Тейк 2: 0.4658"
    tp2_match = re.search(r'(?:TP\s*2|Тейк\s*2):?\s*\$?(\d+\.?\d*)', text, re.IGNORECASE)
    fields['tp2'] = float(tp2_match.group(1)) if tp2_match else None

    # Extract TP3: "TP3: 110000" or "Тейк 3: 0.12761"
    tp3_match = re.search(r'(?:TP\s*3|Тейк\s*3):?\s*\$?(\d+\.?\d*)', text, re.IGNORECASE)
    fields['tp3'] = float(tp3_match.group(1)) if tp3_match else None

    # Extract SL: "SL: 90000" or "Стоп: 0.4997"
    sl_match = re.search(r'(?:SL|Стоп):?\s*\$?(\d+\.?\d*)', text, re.IGNORECASE)
    fields['sl'] = float(sl_match.group(1)) if sl_match else None

    # Extract Risk: "Риск: 2%" or "риск: 2"
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
