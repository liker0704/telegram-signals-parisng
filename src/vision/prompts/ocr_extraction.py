"""OCR extraction prompts for vision providers (Gemini, GPT-4V, Claude Vision, etc.)."""

# Russian → English trading terminology dictionary
TRADING_TERMS = {
    # Direction/Position Type
    'ЛОНГ': 'LONG',
    'ЛОН': 'LONG',
    'LONG': 'LONG',
    'ШОРТ': 'SHORT',
    'SHORT': 'SHORT',
    'ПОКУПКА': 'BUY',
    'ПРОДАЖА': 'SELL',

    # Entry/Exit Points
    'Вход': 'Entry',
    'ВХОД': 'ENTRY',
    'Вхід': 'Entry',  # Ukrainian variant
    'Зона входа': 'Entry Zone',
    'Точка входа': 'Entry Point',
    'Вход от': 'Entry from',
    'Вход до': 'Entry to',

    # Take Profit
    'Тейк': 'TP',
    'ТЕЙК': 'TP',
    'Тейк профит': 'Take Profit',
    'Тейк-профит': 'Take Profit',
    'Цель': 'Target',
    'ЦЕЛЬ': 'TARGET',
    'Профит': 'Profit',
    'TP': 'TP',
    'Take Profit': 'Take Profit',

    # Stop Loss
    'Стоп': 'SL',
    'СТОП': 'SL',
    'Стоп лосс': 'Stop Loss',
    'Стоп-лосс': 'Stop Loss',
    'Стоплосс': 'Stop Loss',
    'SL': 'SL',
    'Stop Loss': 'Stop Loss',

    # Risk Management
    'Риск': 'Risk',
    'РИСК': 'RISK',
    'Плечо': 'Leverage',
    'ПЛЕЧО': 'LEVERAGE',
    'Депозит': 'Deposit',
    'ДЕПОЗИТ': 'DEPOSIT',

    # Timeframes
    'Таймфрейм': 'Timeframe',
    'ТФ': 'TF',
    'TF': 'TF',
    'минута': 'minute',
    'мин': 'min',
    'час': 'hour',
    'ч': 'h',
    'день': 'day',
    'д': 'd',
    'неделя': 'week',
    'н': 'w',
    'месяц': 'month',
    'м': 'm',

    # Exchanges/Platforms
    'БАЙБИТ': 'BYBIT',
    'БИНАНС': 'BINANCE',
    'БІТФІНЕКС': 'BITFINEX',
    'БИТФИНЕКС': 'BITFINEX',
    'БИРЖА': 'EXCHANGE',

    # Order Types
    'Рынок': 'Market',
    'РЫНОК': 'MARKET',
    'Лимит': 'Limit',
    'ЛИМИТ': 'LIMIT',
    'Маркет': 'Market',
    'МАРКЕТ': 'MARKET',

    # Chart Indicators
    'Поддержка': 'Support',
    'ПОДДЕРЖКА': 'SUPPORT',
    'Сопротивление': 'Resistance',
    'СОПРОТИВЛЕНИЕ': 'RESISTANCE',
    'Уровень': 'Level',
    'УРОВЕНЬ': 'LEVEL',
    'Линия': 'Line',
    'ЛИНИЯ': 'LINE',
    'Тренд': 'Trend',
    'ТРЕНД': 'TREND',

    # Signal Status
    'Активен': 'Active',
    'АКТИВЕН': 'ACTIVE',
    'Закрыт': 'Closed',
    'ЗАКРЫТ': 'CLOSED',
    'Отменен': 'Cancelled',
    'ОТМЕНЕН': 'CANCELLED',
    'Ожидание': 'Pending',
    'ОЖИДАНИЕ': 'PENDING',

    # Common Words
    'Цена': 'Price',
    'ЦЕНА': 'PRICE',
    'Объем': 'Volume',
    'ОБЪЕМ': 'VOLUME',
    'Время': 'Time',
    'ВРЕМЯ': 'TIME',
    'Дата': 'Date',
    'ДАТА': 'DATE',
    'Пара': 'Pair',
    'ПАРА': 'PAIR',

    # Miscellaneous
    'Идея': 'Idea',
    'ИДЕЯ': 'IDEA',
    'Сигнал': 'Signal',
    'СИГНАЛ': 'SIGNAL',
    'Анализ': 'Analysis',
    'АНАЛИЗ': 'ANALYSIS',
    'Прогноз': 'Forecast',
    'ПРОГНОЗ': 'FORECAST',
}


OCR_EXTRACTION_PROMPT = """Extract ALL visible text from this trading chart/screenshot image.

IMPORTANT INSTRUCTIONS:
1. Find EVERY piece of text in the image (labels, numbers, symbols, annotations)
2. Text may be in Russian, English, or Cyrillic characters
3. Translate ALL Russian/Cyrillic text to English
4. Preserve exact formatting of: numbers, currency symbols ($, €, ₽), percentages (%), ticker symbols (BTC/USDT, ETH/USD)
5. For each text element, output BOTH original and English translation

OUTPUT FORMAT:
For each text element found, use this exact format:
ORIGINAL: [original text exactly as shown] -> ENGLISH: [English translation]

TRANSLATION RULES:
- If text is already in English → ENGLISH should be same as ORIGINAL
- If text contains numbers/symbols only → ENGLISH should be same as ORIGINAL
- If text is Russian/Cyrillic → translate to English
- Use trading-specific terminology:
  * ЛОНГ / ЛОН → LONG
  * ШОРТ → SHORT
  * Вход → Entry
  * Тейк / Тейк-профит → TP / Take Profit
  * Стоп / Стоп-лосс → SL / Stop Loss
  * БАЙБИТ → BYBIT
  * БИНАНС → BINANCE
  * Риск → Risk
  * Плечо → Leverage
  * Цена → Price
  * Цель → Target
  * Поддержка → Support
  * Сопротивление → Resistance

EXAMPLES:
✅ CORRECT:
ORIGINAL: ЛОНГ → ENGLISH: LONG
ORIGINAL: BTC/USDT → ENGLISH: BTC/USDT
ORIGINAL: 45,230.5 → ENGLISH: 45,230.5
ORIGINAL: Вход: 1.2345 → ENGLISH: Entry: 1.2345
ORIGINAL: Тейк 1 → ENGLISH: TP 1
ORIGINAL: Стоп-лосс → ENGLISH: Stop Loss
ORIGINAL: 5x → ENGLISH: 5x
ORIGINAL: БАЙБИТ → ENGLISH: BYBIT

❌ INCORRECT:
ORIGINAL: ЛОНГ → ENGLISH: Long (should be uppercase LONG)
ORIGINAL: Вход → ENGLISH: Entrance (should be Entry)
ORIGINAL: Тейк → ENGLISH: Take (should be TP)

SPECIAL CASES:
- Mixed text: "ЛОНГ BTC/USDT" → ENGLISH: "LONG BTC/USDT"
- Dates: "12.12.2025" → preserve as is
- Percentages: "3.5%" → preserve as is
- Decimal numbers: "1,234.56" or "1.234,56" → preserve format
- Chart labels: translate but keep technical meaning

If NO text is visible or readable in the image, return exactly:
NO_TEXT_FOUND

Otherwise, list ALL text elements in the format above, one per line.
"""
