# Internal API Documentation
## Telegram Signal Translator Bot

**Version:** 1.0.0
**Last Updated:** 2025-12-01
**Purpose:** Internal reference for module interfaces, function signatures, and data contracts

---

## Table of Contents

1. [Module Overview](#1-module-overview)
2. [Key Function Signatures](#2-key-function-signatures)
3. [Data Models](#3-data-models)
4. [Error Handling Patterns](#4-error-handling-patterns)
5. [Retry Logic](#5-retry-logic)
6. [Database Schema](#6-database-schema)
7. [Configuration](#7-configuration)

---

## 1. Module Overview

| Module | Responsibility | Key Dependencies |
|--------|----------------|------------------|
| `src/main.py` | Application entry point, Telethon client orchestration | `telethon`, `config`, `handlers` |
| `src/config.py` | Load and validate environment variables from `.env` | `os`, `pydantic` |
| `src/db/connection.py` | PostgreSQL connection pool management (asyncpg) | `asyncpg`, `config` |
| `src/db/queries.py` | Database helper functions (CRUD operations) | `asyncpg`, `connection` |
| `src/handlers/signal_handler.py` | Process new trading signals (`#Идея` detection) | `translators`, `parsers`, `media`, `db` |
| `src/handlers/update_handler.py` | Process signal updates (reply messages) | `translators`, `media`, `db` |
| `src/translators/gemini.py` | Gemini API text translation | `google.generativeai` |
| `src/translators/google.py` | Google Translate fallback | `google.cloud.translate_v2` |
| `src/translators/fallback.py` | Translation orchestration with fallback logic | `gemini`, `google` |
| `src/ocr/gemini_ocr.py` | Extract and translate text from images using Gemini Vision | `google.generativeai` |
| `src/media/downloader.py` | Download and store Telegram media files | `telethon`, `os`, `db` |
| `src/parsers/signal_parser.py` | Extract structured trading fields via regex | `re` |
| `src/formatters/message.py` | Build final translated messages, restore trading terms | `typing` |
| `src/utils/logger.py` | Structured logging configuration (JSON format) | `structlog`, `logging` |
| `src/telethon_setup.py` | Initialize and configure Telethon clients | `telethon`, `config` |

---

## 2. Key Function Signatures

### 2.1 Handlers

#### `src/handlers/signal_handler.py`

```python
async def handle_new_signal(message: Message, event: events.NewMessage.Event) -> None:
    """
    Process a new trading signal from the source group.

    Workflow:
    1. Create DB record with PENDING status
    2. Extract structured fields (pair, direction, TP, SL, etc.)
    3. Download media (if present)
    4. Translate text + OCR image in parallel
    5. Post to target group
    6. Update DB with POSTED status and target_message_id
    7. Clean up downloaded media

    Args:
        message: Telethon message object from source group
        event: Telethon NewMessage event

    Returns:
        None (async task, no return value)

    Raises:
        Does not raise. All exceptions are caught, logged, and stored in DB.
        On error, signal status set to ERROR_POSTING_FAILED or ERROR_TRANSLATION_FAILED.

    Side Effects:
        - Creates record in `signals` table
        - Downloads media to MEDIA_DOWNLOAD_DIR
        - Posts message to target group via publisher client
        - Deletes local media file after posting
    """
```

#### `src/handlers/update_handler.py`

```python
async def handle_signal_update(message: Message, event: events.NewMessage.Event) -> None:
    """
    Process a reply to an existing trading signal.

    Workflow:
    1. Find parent signal in DB using reply_to_msg_id
    2. If parent not found, ignore (orphan reply)
    3. Create DB record in signal_updates table
    4. Download media (if present)
    5. Translate text + OCR image
    6. Post as reply to target group (using parent's target_message_id)
    7. Update DB with POSTED status
    8. Clean up media

    Args:
        message: Telethon message object (reply from source group)
        event: Telethon NewMessage event

    Returns:
        None

    Raises:
        Does not raise. Errors logged and stored in DB.

    Side Effects:
        - Creates record in `signal_updates` table
        - Posts reply message to target group
        - Deletes local media file
    """
```

---

### 2.2 Translators

#### `src/translators/fallback.py`

```python
async def translate_text_with_fallback(text: str, timeout: int = 30) -> str:
    """
    Translate text using Gemini with Google Translate fallback.

    Strategy:
    1. Try Gemini API with timeout
    2. If timeout or error → fallback to Google Translate
    3. If both fail → return original text (caller logs error)

    Args:
        text: Russian text to translate
        timeout: Max seconds to wait for Gemini response (default: 30)

    Returns:
        Translated English text, or original text if both APIs fail

    Raises:
        Does not raise. Returns original text on failure.

    Example:
        >>> text = "Вход: 0.98-0.9283"
        >>> result = await translate_text_with_fallback(text)
        >>> print(result)
        "Entry: 0.98-0.9283"
    """
```

#### `src/translators/gemini.py`

```python
async def gemini_translate(text: str) -> str:
    """
    Translate text using Google Gemini API.

    Prompt instructions:
    - Preserve: TP1, TP2, TP3, SL, LONG, SHORT, tickers (BTC/USDT)
    - Preserve: Numbers, currency symbols, emojis
    - Preserve: Line breaks and formatting
    - Translate: Descriptive text only

    Args:
        text: Russian text to translate

    Returns:
        Translated English text

    Raises:
        asyncio.TimeoutError: If API call exceeds timeout
        google.api_core.exceptions.GoogleAPIError: On API errors

    Example:
        >>> text = "#Идея\\n\\nXION/USDT LONG\\n\\nВход: 0.98"
        >>> result = await gemini_translate(text)
        >>> print(result)
        "#Idea\\n\\nXION/USDT LONG\\n\\nEntry: 0.98"
    """
```

#### `src/translators/google.py`

```python
async def google_translate(text: str) -> str:
    """
    Fallback translation using Google Translate API.

    Note: May incorrectly translate trading terms (e.g., "TP1" → "TP 1").
    Post-processing applied via restore_trading_terms().

    Args:
        text: Russian text to translate

    Returns:
        Translated English text with trading terms restored

    Raises:
        google.cloud.exceptions.GoogleCloudError: On API errors

    Example:
        >>> text = "Риск: 2%"
        >>> result = await google_translate(text)
        >>> print(result)
        "Risk: 2%"
    """
```

---

### 2.3 OCR

#### `src/ocr/gemini_ocr.py`

```python
async def translate_image_ocr(image_path: str) -> Optional[str]:
    """
    Extract and translate text from trading chart images.

    Uses Gemini Vision API to:
    1. Extract visible text (chart labels, indicators, notes)
    2. Translate extracted text to English
    3. Preserve numbers and tickers

    Args:
        image_path: Local file path to downloaded image

    Returns:
        Formatted string: "[On chart]: <translated_text>"
        Returns None if no text found or OCR fails

    Raises:
        google.api_core.exceptions.GoogleAPIError: On API errors
        FileNotFoundError: If image_path does not exist

    Example:
        >>> ocr_text = await translate_image_ocr("/tmp/signals/chart123.jpg")
        >>> print(ocr_text)
        "[On chart]: Resistance at 0.98, Support at 0.92"
    """
```

---

### 2.4 Media

#### `src/media/downloader.py`

```python
async def download_and_process_media(
    client: TelegramClient,
    message: Message,
    entity_id: int,
    is_update: bool = False
) -> Optional[dict]:
    """
    Download media from Telegram message and store metadata.

    Workflow:
    1. Check if message has photo or document
    2. Download to MEDIA_DOWNLOAD_DIR
    3. Validate file size (skip if > MAX_IMAGE_SIZE_MB)
    4. Update DB record with local_path
    5. Return media metadata

    Args:
        client: Telethon client instance (reader)
        message: Telethon message with media
        entity_id: signal_id or update_id for DB record
        is_update: If True, update signal_updates table; else signals table

    Returns:
        dict with keys:
            - local_path: str (absolute path to downloaded file)
            - file_name: str (filename)
            - file_size: int (bytes)
            - downloaded_at: datetime
        Returns None if no media or download fails

    Raises:
        Does not raise. Returns None on errors.

    Side Effects:
        - Creates file in MEDIA_DOWNLOAD_DIR
        - Updates DB record with image_local_path

    Example:
        >>> media = await download_and_process_media(client, msg, signal_id)
        >>> print(media['local_path'])
        "/tmp/signals/photo_2025_12_01_abc123.jpg"
    """
```

---

### 2.5 Parsers

#### `src/parsers/signal_parser.py`

```python
def parse_trading_signal(text: str) -> dict:
    """
    Extract structured trading fields from signal text using regex.

    Extracted fields (all optional):
    - pair: Trading pair (e.g., "BTC/USDT", "XION/USDT")
    - direction: "LONG" or "SHORT"
    - timeframe: e.g., "15мин", "1H", "4H", "D", "W"
    - entry_range: Entry price range (e.g., "0.98-0.9283")
    - tp1, tp2, tp3: Take profit levels (float)
    - sl: Stop loss (float)
    - risk_percent: Risk percentage (float)

    Args:
        text: Full message text (Russian or English)

    Returns:
        dict mapping field names to extracted values (or None if not found)

    Raises:
        Does not raise. Invalid data returns None for that field.

    Regex Patterns:
        - Pair: r'\b([A-Z][A-Z0-9]*/[A-Z][A-Z0-9]*)\b'
        - Direction: r'\b(LONG|SHORT)\b' (case-insensitive)
        - Timeframe: r'(\d+\s*[мм][и]?[н]?|1[Hh]|4[Hh]|[Dd]|[Ww])'
        - Entry: r'[Вв]ход[а]?:?\s*(\d+\.?\d*[-–]\d+\.?\d*)'
        - TP1/2/3: r'TP[1-3]:?\s*\$?(\d+\.?\d*)'
        - SL: r'(?:SL|Стоп):?\s*\$?(\d+\.?\d*)'
        - Risk: r'[Рр]иск:?\s*(\d+)%?'

    Example:
        >>> text = "XION/USDT LONG\\n\\nВход: 0.98-0.9283\\nTP1: 1.05\\nSL: 0.90"
        >>> fields = parse_trading_signal(text)
        >>> print(fields)
        {
            'pair': 'XION/USDT',
            'direction': 'LONG',
            'entry_range': '0.98-0.9283',
            'tp1': 1.05,
            'sl': 0.90,
            'timeframe': None,
            'tp2': None,
            'tp3': None,
            'risk_percent': None
        }
    """
```

---

### 2.6 Formatters

#### `src/formatters/message.py`

```python
def build_final_message(
    translated_text: str,
    image_ocr: Optional[str],
    parsed_fields: dict
) -> str:
    """
    Construct final message to post to target group.

    Format:
        <translated_text>

        [Chart OCR:]
        <image_ocr_text>

    Args:
        translated_text: Translated signal text
        image_ocr: Extracted and translated image text (or None)
        parsed_fields: Structured fields (currently unused, reserved for future formatting)

    Returns:
        Formatted message string ready to post

    Example:
        >>> msg = build_final_message(
        ...     "XION/USDT LONG\\n\\nEntry: 0.98",
        ...     "[On chart]: Resistance at 1.05",
        ...     {}
        ... )
        >>> print(msg)
        XION/USDT LONG

        Entry: 0.98

        _Chart OCR:_
        [On chart]: Resistance at 1.05
    """

def restore_trading_terms(text: str) -> str:
    """
    Post-process Google Translate output to restore trading terms.

    Fixes common translation errors:
    - "tp 1" → "TP1"
    - "tp 2" → "TP2"
    - "tp 3" → "TP3"
    - "sl " → "SL "
    - "long" → "LONG"
    - "short" → "SHORT"

    Args:
        text: Translated text from Google Translate

    Returns:
        Text with trading terms corrected

    Example:
        >>> text = "tp 1: $1.05, sl : $0.90, direction: long"
        >>> result = restore_trading_terms(text)
        >>> print(result)
        "TP1: $1.05, SL: $0.90, direction: LONG"
    """
```

---

### 2.7 Database Queries

#### `src/db/queries.py`

```python
async def db_insert_signal(signal_data: dict) -> int:
    """
    Insert new signal record into `signals` table.

    Args:
        signal_data: dict with keys:
            - source_chat_id: int (required)
            - source_message_id: int (required)
            - source_user_id: int (optional)
            - original_text: str (required)
            - status: str (default: 'PENDING')
            - created_at: datetime (optional)

    Returns:
        signal_id: int (primary key of inserted record)

    Raises:
        asyncpg.UniqueViolationError: If (source_chat_id, source_message_id) already exists
        asyncpg.PostgresError: On other DB errors

    Example:
        >>> data = {
        ...     'source_chat_id': -100123456789,
        ...     'source_message_id': 54321,
        ...     'original_text': 'XION/USDT LONG...',
        ...     'status': 'PENDING'
        ... }
        >>> signal_id = await db_insert_signal(data)
        >>> print(signal_id)
        42
    """

async def db_update_signal(signal_id: int, data: dict) -> None:
    """
    Update existing signal record.

    Args:
        signal_id: Primary key of signal to update
        data: dict with any combination of:
            - status: str
            - translated_text: str
            - target_message_id: int
            - target_chat_id: int
            - pair, direction, timeframe, etc. (structured fields)
            - processed_at: datetime
            - error_message: str

    Returns:
        None

    Raises:
        asyncpg.PostgresError: On DB errors

    Example:
        >>> await db_update_signal(42, {
        ...     'status': 'POSTED',
        ...     'target_message_id': 98765,
        ...     'processed_at': datetime.utcnow()
        ... })
    """

async def db_find_signal_by_source_msg(
    chat_id: int,
    msg_id: int
) -> Optional[dict]:
    """
    Find signal by source group message ID (for reply handling).

    Args:
        chat_id: source_chat_id
        msg_id: source_message_id

    Returns:
        dict with signal data (all columns) or None if not found

    Raises:
        asyncpg.PostgresError: On DB errors

    Example:
        >>> parent = await db_find_signal_by_source_msg(-100123456789, 54321)
        >>> if parent:
        ...     print(parent['target_message_id'])
        98765
    """

async def db_insert_signal_update(update_data: dict) -> int:
    """
    Insert new update record into `signal_updates` table.

    Args:
        update_data: dict with keys:
            - signal_id: int (foreign key to signals.id)
            - source_chat_id: int
            - source_message_id: int
            - original_text: str
            - status: str (default: 'PENDING')

    Returns:
        update_id: int (primary key)

    Raises:
        asyncpg.ForeignKeyViolationError: If signal_id doesn't exist
        asyncpg.UniqueViolationError: If source_message_id already exists
        asyncpg.PostgresError: On other errors
    """

async def db_update_signal_update(update_id: int, data: dict) -> None:
    """
    Update existing signal_updates record.

    Args:
        update_id: Primary key of update to modify
        data: dict with fields to update (same as signals table)

    Returns:
        None

    Raises:
        asyncpg.PostgresError: On DB errors
    """
```

---

### 2.8 Telethon Setup

#### `src/telethon_setup.py`

```python
async def init_reader_client(config: Config) -> TelegramClient:
    """
    Initialize Telethon client for reading source group.

    Args:
        config: Configuration object with READER_* settings

    Returns:
        Connected TelegramClient instance

    Raises:
        telethon.errors.AuthKeyError: If session file invalid
        telethon.errors.PhoneNumberInvalidError: If phone number invalid

    Side Effects:
        - Creates .session file if not exists (requires phone verification)
        - Connects to Telegram MTProto API
    """

async def init_publisher_client(config: Config) -> TelegramClient:
    """
    Initialize Telethon client for posting to target group.

    Args:
        config: Configuration object with PUBLISHER_* settings

    Returns:
        Connected TelegramClient instance

    Raises:
        telethon.errors.AuthKeyError: If session file invalid
        telethon.errors.PhoneNumberInvalidError: If phone number invalid

    Side Effects:
        - Creates .session file if not exists
        - Connects to Telegram MTProto API
    """

def register_handlers(
    client: TelegramClient,
    config: Config
) -> None:
    """
    Register event handlers on reader client.

    Registers:
    - NewMessage handler: Detects #Идея signals and replies

    Args:
        client: Reader Telethon client
        config: Configuration object

    Returns:
        None

    Side Effects:
        - Attaches event listeners to client
        - Handlers run in background asyncio tasks
    """
```

---

## 3. Data Models

### 3.1 SignalData (Database Row)

**Table:** `signals`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class SignalData:
    """
    Represents a trading signal record in the database.
    """
    # Primary key
    id: int

    # Source tracking
    source_chat_id: int          # SOURCE_GROUP_ID (-100...)
    source_message_id: int       # Unique per group
    source_user_id: Optional[int]

    # Target tracking (populated after posting)
    target_chat_id: Optional[int]
    target_message_id: Optional[int]

    # Structured fields (extracted via regex, nullable)
    pair: Optional[str]          # e.g., "BTC/USDT"
    direction: Optional[str]     # "LONG" or "SHORT"
    timeframe: Optional[str]     # e.g., "15мин", "1H", "4H"
    entry_range: Optional[str]   # e.g., "0.98-0.9283"
    tp1: Optional[float]
    tp2: Optional[float]
    tp3: Optional[float]
    sl: Optional[float]
    risk_percent: Optional[float]

    # Content
    original_text: str           # Full Russian text
    translated_text: Optional[str]
    image_source_url: Optional[str]
    image_local_path: Optional[str]
    image_ocr_text: Optional[str]

    # Metadata
    created_at: datetime
    processed_at: Optional[datetime]
    status: str                  # See Signal Status Values below
    error_message: Optional[str]
```

---

### 3.2 ParsedFields (In-Memory)

```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class ParsedFields:
    """
    Structured trading signal fields extracted via regex.
    All fields optional (may be None if not found in text).
    """
    pair: Optional[str]          # e.g., "XION/USDT"
    direction: Optional[str]     # "LONG" or "SHORT"
    timeframe: Optional[str]     # e.g., "15мин", "1H", "4H", "D"
    entry_range: Optional[str]   # e.g., "0.98-0.9283"
    tp1: Optional[float]
    tp2: Optional[float]
    tp3: Optional[float]
    sl: Optional[float]
    risk_percent: Optional[float]
```

---

### 3.3 MediaInfo (In-Memory)

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MediaInfo:
    """
    Metadata about downloaded media file.
    """
    local_path: str              # Absolute path, e.g., "/tmp/signals/photo123.jpg"
    file_name: str               # e.g., "photo123.jpg"
    file_size: int               # Bytes
    downloaded_at: datetime
```

---

### 3.4 Signal Status Values

**Enum-like constants (stored as VARCHAR in DB):**

| Status | Description | Next Actions |
|--------|-------------|--------------|
| `PENDING` | Signal detected, DB record created | Start processing (parse, translate) |
| `PROCESSING` | Translation/OCR in progress | Wait for API responses |
| `POSTED` | Successfully posted to target group | None (terminal state) |
| `ERROR_TRANSLATION_FAILED` | Gemini + Google Translate both failed | Manual review, retry translation |
| `ERROR_POSTING_FAILED` | Failed to post to Telegram | Manual retry (check permissions) |
| `ERROR_OCR_FAILED` | Image OCR failed (non-critical) | Proceed without OCR text |

**State Transitions:**

```
PENDING → PROCESSING → POSTED (success)
                    → ERROR_TRANSLATION_FAILED (API failure)
                    → ERROR_POSTING_FAILED (Telegram error)
```

---

## 4. Error Handling Patterns

### 4.1 Translation Errors

**Pattern:** Try primary API, fallback to secondary, return original on total failure

```python
try:
    # Primary: Gemini API
    result = await asyncio.wait_for(gemini_translate(text), timeout=30)
    return result
except (asyncio.TimeoutError, google.api_core.exceptions.GoogleAPIError) as e:
    logger.warning(f"Gemini failed: {e}, trying Google Translate")
    try:
        # Fallback: Google Translate
        result = await google_translate(text)
        return result
    except Exception as e2:
        logger.error(f"Both translation APIs failed: {e2}")
        # Return original text, log error, mark status
        return text
```

**Status Codes:**
- Gemini timeout → Fallback, no error status
- Both fail → Set status to `ERROR_TRANSLATION_FAILED`

---

### 4.2 Media Download Errors

**Pattern:** Log and proceed without media (non-blocking)

```python
try:
    media_info = await download_and_process_media(client, message, signal_id)
except Exception as e:
    logger.warning(f"Media download failed: {e}")
    media_info = None  # Proceed without media

# Later...
if media_info:
    ocr_text = await translate_image_ocr(media_info['local_path'])
else:
    ocr_text = None  # No media to OCR
```

**Do NOT fail signal processing if media fails.**

---

### 4.3 Database Errors

**Pattern:** Log and skip signal (don't crash service)

```python
try:
    signal_id = await db_insert_signal(signal_data)
except asyncpg.UniqueViolationError:
    logger.warning(f"Signal already exists: {signal_data['source_message_id']}")
    return  # Skip duplicate
except asyncpg.PostgresError as e:
    logger.error(f"DB error: {e}", exc_info=True)
    return  # Skip signal, don't crash
```

**Do NOT retry DB operations automatically** (risk of duplicate posts).

---

### 4.4 Telegram Posting Errors

**Pattern:** Exponential backoff retry up to 3 times, then mark as failed

```python
for attempt in range(1, 4):
    try:
        posted_msg = await client_publisher.send_message(...)
        break  # Success
    except telethon.errors.FloodWaitError as e:
        wait_time = e.seconds
        logger.warning(f"FloodWait: {wait_time}s, attempt {attempt}/3")
        await asyncio.sleep(wait_time)
    except telethon.errors.ChatWriteForbiddenError:
        logger.error("No write permission in target group")
        await db_update_signal(signal_id, {
            'status': 'ERROR_POSTING_FAILED',
            'error_message': 'ChatWriteForbidden'
        })
        return
    except Exception as e:
        logger.error(f"Telegram error: {e}, attempt {attempt}/3")
        await asyncio.sleep(2 ** attempt)  # 2s, 4s, 8s
else:
    # Max retries exceeded
    await db_update_signal(signal_id, {
        'status': 'ERROR_POSTING_FAILED',
        'error_message': 'Max retries exceeded'
    })
```

---

## 5. Retry Logic

### 5.1 Telegram Errors

**Exponential Backoff:**

| Attempt | Wait Time | Action |
|---------|-----------|--------|
| 1 | 0s | Immediate first try |
| 2 | 2s | Retry after 2 seconds |
| 3 | 4s | Retry after 4 seconds |
| 4+ | — | Mark as ERROR_POSTING_FAILED |

**Max Retries:** 3

**Backoff Formula:** `wait_time = 2 ** attempt` (seconds)

**Exceptions:**
- `FloodWaitError`: Use `e.seconds` instead of exponential backoff
- `ChatWriteForbiddenError`: Do NOT retry (permission issue)

---

### 5.2 API Errors (Translation/OCR)

**No Retry, Immediate Fallback:**

| Step | Action | Timeout |
|------|--------|---------|
| 1 | Try Gemini API | 30 seconds |
| 2 | On timeout/error → Google Translate | No timeout |
| 3 | On both failures → Use original text | — |

**Rationale:** Fallback is faster than retry. No point retrying Gemini if it's timing out.

---

### 5.3 Database Errors

**No Retry:**

- `UniqueViolationError`: Skip (duplicate signal)
- Other errors: Log and skip (don't retry to avoid duplicates)

**Rationale:** DB errors usually indicate data inconsistency. Retrying risks duplicate posts.

---

## 6. Database Schema

### 6.1 `signals` Table

```sql
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,

    -- Source group tracking
    source_chat_id BIGINT NOT NULL,
    source_message_id BIGINT NOT NULL,
    source_user_id BIGINT,

    -- Target group tracking
    target_chat_id BIGINT,
    target_message_id BIGINT,

    -- Extracted signal fields (all nullable)
    pair VARCHAR(20),
    direction VARCHAR(10),
    timeframe VARCHAR(20),
    entry_range VARCHAR(50),
    tp1 NUMERIC(20,10),
    tp2 NUMERIC(20,10),
    tp3 NUMERIC(20,10),
    sl NUMERIC(20,10),
    risk_percent FLOAT,

    -- Content
    original_text TEXT NOT NULL,
    translated_text TEXT,
    image_source_url TEXT,
    image_local_path TEXT,
    image_ocr_text TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(30) DEFAULT 'PENDING',
    error_message TEXT,

    CONSTRAINT unique_source_msg UNIQUE (source_chat_id, source_message_id),
    CONSTRAINT check_status CHECK (status IN (
        'PENDING', 'PROCESSING', 'POSTED',
        'ERROR_TRANSLATION_FAILED', 'ERROR_POSTING_FAILED', 'ERROR_OCR_FAILED'
    ))
);

CREATE INDEX idx_source_msg ON signals(source_chat_id, source_message_id);
CREATE INDEX idx_target_msg ON signals(target_message_id);
CREATE INDEX idx_status ON signals(status);
```

---

### 6.2 `signal_updates` Table

```sql
CREATE TABLE signal_updates (
    id SERIAL PRIMARY KEY,

    signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,

    -- Source reply
    source_chat_id BIGINT NOT NULL,
    source_message_id BIGINT NOT NULL,
    source_user_id BIGINT,

    -- Target reply
    target_chat_id BIGINT,
    target_message_id BIGINT,

    -- Content
    original_text TEXT NOT NULL,
    translated_text TEXT,
    image_source_url TEXT,
    image_local_path TEXT,
    image_ocr_text TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(30) DEFAULT 'PENDING',
    error_message TEXT,

    CONSTRAINT unique_source_reply UNIQUE (source_chat_id, source_message_id),
    CONSTRAINT check_status CHECK (status IN (
        'PENDING', 'PROCESSING', 'POSTED',
        'ERROR_TRANSLATION_FAILED', 'ERROR_POSTING_FAILED', 'ERROR_OCR_FAILED'
    ))
);

CREATE INDEX idx_signal_updates_parent ON signal_updates(signal_id);
CREATE INDEX idx_source_reply ON signal_updates(source_chat_id, source_message_id);
```

---

### 6.3 `translation_cache` Table (Optional)

```sql
CREATE TABLE translation_cache (
    id SERIAL PRIMARY KEY,
    source_text_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA256(source_text)
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    language_pair VARCHAR(10) DEFAULT 'ru_en',
    model VARCHAR(50),                             -- 'gemini' or 'google_translate'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    usage_count INT DEFAULT 1
);

CREATE INDEX idx_source_hash ON translation_cache(source_text_hash);
```

**Usage:**

```python
import hashlib

text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
cached = await db.fetch_one(
    "SELECT translated_text FROM translation_cache WHERE source_text_hash = $1",
    text_hash
)

if cached:
    return cached['translated_text']
else:
    # Translate and cache
    translated = await translate_text_with_fallback(text)
    await db.execute(
        "INSERT INTO translation_cache (source_text_hash, source_text, translated_text, model) VALUES ($1, $2, $3, $4)",
        text_hash, text, translated, 'gemini'
    )
    return translated
```

---

## 7. Configuration

### 7.1 Environment Variables

**Loaded from `.env` file by `src/config.py`**

#### Telegram Accounts

```ini
# Reader Account (Reads from SOURCE_GROUP)
READER_API_ID=1234567
READER_API_HASH=abcdef123456789abcdef123456789ab
READER_PHONE=+1234567890
READER_SESSION_FILE=reader.session

# Publisher Account (Writes to TARGET_GROUP)
PUBLISHER_API_ID=9876543
PUBLISHER_API_HASH=zyxwvu987654321zyxwvu987654321zy
PUBLISHER_PHONE=+0987654321
PUBLISHER_SESSION_FILE=publisher.session
```

#### Group IDs

```ini
SOURCE_GROUP_ID=-100123456789      # Must start with -100 for supergroups
TARGET_GROUP_ID=-100987654321
SOURCE_ALLOWED_USERS=123456789,987654321  # Optional: CSV of allowed sender IDs
```

#### APIs

```ini
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.0-flash      # or gemini-1.5-pro

GOOGLE_TRANSLATE_API_KEY=...       # Optional for paid tier
```

#### Database

```ini
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=signal_bot
POSTGRES_HOST=db                   # Docker service name
POSTGRES_PORT=5432

SQLALCHEMY_ECHO=False              # Set True for SQL debug logs
```

#### Application

```ini
LOG_LEVEL=INFO                     # DEBUG, INFO, WARNING, ERROR
ENVIRONMENT=production             # development, staging, production
MAX_RETRIES=3
TIMEOUT_GEMINI_SEC=30
TIMEOUT_TELEGRAM_SEC=15
```

#### Media

```ini
MEDIA_DOWNLOAD_DIR=/tmp/signals
MAX_IMAGE_SIZE_MB=50
```

---

### 7.2 Config Class

**`src/config.py`**

```python
from pydantic import BaseSettings, Field
from typing import Optional, List

class Config(BaseSettings):
    """
    Application configuration loaded from environment variables.
    """
    # Telegram Reader
    READER_API_ID: int
    READER_API_HASH: str
    READER_PHONE: str
    READER_SESSION_FILE: str = "reader.session"

    # Telegram Publisher
    PUBLISHER_API_ID: int
    PUBLISHER_API_HASH: str
    PUBLISHER_PHONE: str
    PUBLISHER_SESSION_FILE: str = "publisher.session"

    # Groups
    SOURCE_GROUP_ID: int
    TARGET_GROUP_ID: int
    SOURCE_ALLOWED_USERS: Optional[str] = None  # CSV string

    # APIs
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GOOGLE_TRANSLATE_API_KEY: Optional[str] = None

    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    SQLALCHEMY_ECHO: bool = False

    # Redis (optional)
    REDIS_URL: Optional[str] = None

    # Application
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "production"
    MAX_RETRIES: int = 3
    TIMEOUT_GEMINI_SEC: int = 30
    TIMEOUT_TELEGRAM_SEC: int = 15

    # Media
    MEDIA_DOWNLOAD_DIR: str = "/tmp/signals"
    MAX_IMAGE_SIZE_MB: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def allowed_users(self) -> List[int]:
        """Parse SOURCE_ALLOWED_USERS CSV to list of ints."""
        if not self.SOURCE_ALLOWED_USERS:
            return []
        return [int(uid.strip()) for uid in self.SOURCE_ALLOWED_USERS.split(',')]

    @property
    def postgres_dsn(self) -> str:
        """Build PostgreSQL connection string."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
```

**Usage:**

```python
from src.config import Config

config = Config()
print(config.GEMINI_API_KEY)
print(config.postgres_dsn)
print(config.allowed_users)  # List[int]
```

---

## Appendix: Example Workflows

### A. New Signal Flow

```
1. Telethon listener receives NewMessage event
2. Check: message contains "#Идея"? → Yes
3. Check: message.is_reply? → No (new signal)
4. Create asyncio.task(handle_new_signal(message, event))

In handle_new_signal():
5. Insert DB record (status=PENDING)
6. Update status to PROCESSING
7. Parse structured fields (regex)
8. Download media (if present)
9. Parallel: translate text + OCR image
10. Build final message
11. Post to target group
12. Update DB (status=POSTED, target_message_id=...)
13. Delete local media file
```

---

### B. Signal Update (Reply) Flow

```
1. Telethon listener receives NewMessage event
2. Check: message contains "#Идея"? → Yes
3. Check: message.is_reply? → Yes
4. Extract reply_to_msg_id
5. Query DB: find signal with source_message_id = reply_to_msg_id
6. If NOT found → ignore (orphan reply)
7. If found → Create asyncio.task(handle_signal_update(message, event))

In handle_signal_update():
8. Insert signal_updates record (status=PROCESSING)
9. Download media (if present)
10. Parallel: translate text + OCR image
11. Build final message
12. Post as reply to target_message_id (from parent signal)
13. Update signal_updates DB (status=POSTED)
14. Delete local media file
```

---

### C. Translation Fallback Flow

```
In translate_text_with_fallback(text, timeout=30):

1. Try Gemini:
   - Set asyncio timeout to 30 seconds
   - Call gemini_translate(text)
   - If success → return translated text

2. On timeout or error:
   - Log warning: "Gemini failed, trying Google Translate"
   - Call google_translate(text)
   - If success → return translated text

3. On both failures:
   - Log error: "All translation methods failed"
   - Return original text (caller marks ERROR_TRANSLATION_FAILED)
```

---

## Document Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2025-12-01 | Initial API documentation | System |

---

**End of Document**