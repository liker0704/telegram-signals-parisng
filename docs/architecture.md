# Telegram Signal Translator Bot - Architecture Documentation

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Descriptions](#2-component-descriptions)
3. [Data Flow](#3-data-flow)
4. [Database Schema](#4-database-schema)
5. [Message Threading Logic](#5-message-threading-logic)
6. [Error Handling Strategy](#6-error-handling-strategy)
7. [Performance](#7-performance)

---

## 1. System Overview

The Telegram Signal Translator Bot is an asynchronous backend service that bridges Russian and English trading signal communities. It employs a dual-account architecture using two separate Telegram user accounts working in parallel to read, translate, and republish trading signals while maintaining conversation threading.

### High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM ARCHITECTURE                                  │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐         ┌──────────────────────┐         ┌─────────────────────┐
│   Account A         │         │     Core Logic       │         │   Account B         │
│   (Reader)          │         │                      │         │   (Publisher)       │
│                     │         │  ┌────────────────┐  │         │                     │
│ Telethon Client 1   │────────>│  │  PostgreSQL    │  │<────────│ Telethon Client 2   │
│                     │         │  │     +          │  │         │                     │
│ Listen to:          │         │  │    Redis       │  │         │ Send to:            │
│ SOURCE_GROUP_ID     │         │  └────────────────┘  │         │ TARGET_GROUP_ID     │
│                     │         │                      │         │                     │
│ Events Received:    │         │  Processing Pipeline:│         │                     │
│ • new_message       │         │  ─────────────────── │         │                     │
│ • message_edited    │         │  1. process_signal() │         │                     │
│ • reply detected    │         │  2. translate_text() │         │                     │
│                     │         │  3. handle_replies() │         │                     │
│        │            │         │  4. map_message_ids()│         │         ▲           │
│        ▼            │         │  5. OCR images       │         │         │           │
│  ┌──────────────┐   │         │  6. cache trans.     │         │  ┌──────────────┐   │
│  │ Async Queue  │   │         │  7. store mapping    │         │  │ Post Message │   │
│  │ (asyncio.Queue)  │         │                      │         │  │ with Media   │   │
│  └──────────────┘   │         │                      │         │  └──────────────┘   │
└─────────────────────┘         └──────────────────────┘         └─────────────────────┘
        │                                  │                                  ▲
        │                                  │                                  │
        └──────────────────────────────────┴──────────────────────────────────┘
                        Signal Flow: Detect → Process → Translate → Publish
```

### Key Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Reader Client** | Telethon 1.36+ (MTProto) | Listens to source group for new signals |
| **Publisher Client** | Telethon 1.36+ (MTProto) | Posts translated signals to target group |
| **Translation Engine** | Google Gemini 2.0 Flash | Translates Russian text to English |
| **OCR Engine** | Gemini Vision API | Extracts text from trading chart images |
| **Fallback Translator** | Google Translate API | Fallback when Gemini fails |
| **Database** | PostgreSQL 15+ (asyncpg) | Stores signals, mappings, cache |
| **Cache** | Redis 7+ | Session persistence, translation cache |
| **Queue** | asyncio.Queue (built-in) | Async task coordination |
| **Logger** | structlog | Structured JSON logging |

### Core Design Principles

1. **Separation of Concerns**: Reader and Publisher clients are completely isolated
2. **Fault Tolerance**: Graceful degradation with fallback mechanisms
3. **Low Latency**: Target <60s end-to-end processing time
4. **Message Fidelity**: Preserve formatting, emojis, trading terminology
5. **Thread Integrity**: Maintain reply chains across source and target groups
6. **Idempotency**: Prevent duplicate signal posting

---

## 2. Component Descriptions

### 2.1 Reader Client (Account A)

**Purpose**: Monitor source Telegram group for trading signals

**Technology**: Telethon MTProto Client with user account credentials

**Responsibilities**:
- Authenticate with Telegram using Account A credentials
- Join and monitor `SOURCE_GROUP_ID`
- Detect messages containing `#Идея` hashtag (signal marker)
- Listen for three event types:
  - `new_message`: New signal posted
  - `message_edited`: Existing signal modified
  - Reply events: Updates to existing signals
- Extract message metadata:
  - Message ID (for mapping)
  - Sender ID (optional whitelist filtering)
  - Timestamp
  - Media attachments (photos, documents)
  - Reply information (is_reply, reply_to_msg_id)
- Push events to async processing queue
- Maintain persistent session (stored in `.session` file)

**Event Handler Flow**:
```python
@client_reader.on(events.NewMessage(chats=[SOURCE_GROUP_ID]))
async def on_new_message(event):
    message = event.message

    # Filter: Only process messages with #Идея
    if '#Идея' not in (message.text or ''):
        return

    # Check if reply (update to existing signal)
    if message.is_reply:
        asyncio.create_task(handle_signal_update(message, event))
        return

    # Otherwise: new signal
    asyncio.create_task(handle_new_signal(message, event))
```

**Configuration**:
- `READER_API_ID`: Telegram API ID
- `READER_API_HASH`: Telegram API Hash
- `READER_PHONE`: Phone number for authentication
- `READER_SESSION_FILE`: Path to persistent session file
- `SOURCE_GROUP_ID`: Group chat ID to monitor
- `SOURCE_ALLOWED_USERS`: CSV list of whitelisted user IDs (optional)

**Error Handling**:
- Connection loss: Exponential backoff reconnection (1s, 2s, 4s)
- Authentication failure: Log error and halt service
- Message parsing errors: Log and skip message (don't crash)

---

### 2.2 Core Logic Layer

**Purpose**: Orchestrate signal processing pipeline from detection to publication

**Components**:

#### 2.2.1 Signal Parser (`src/parsers/signal_parser.py`)

Extracts structured trading data using regex patterns:

```python
def parse_trading_signal(text: str) -> dict:
    """Extract trading fields from signal text"""
    fields = {}

    # Pair: BTC/USDT, XION/USDT, etc.
    match = re.search(r'\b([A-Z][A-Z0-9]*\/[A-Z][A-Z0-9]*)\b', text)
    fields['pair'] = match.group(1) if match else None

    # Direction: LONG or SHORT
    match = re.search(r'\b(LONG|SHORT)\b', text, re.IGNORECASE)
    fields['direction'] = match.group(1).upper() if match else None

    # Timeframe: 15мин, 1H, 4H, D, W
    match = re.search(r'(\d+\s*[мм][и]?[н]?|1[Hh]|4[Hh]|[Dd]|[Ww])', text)
    fields['timeframe'] = match.group(1).strip() if match else None

    # Entry Range: 0.98-0.9283
    match = re.search(r'[Вв]ход[а]?:?\s*(\d+\.?\d*[-–]\d+\.?\d*)', text)
    fields['entry_range'] = match.group(1) if match else None

    # Take Profit levels: TP1, TP2, TP3
    for i in range(1, 4):
        match = re.search(rf'TP{i}:?\s*\$?(\d+\.?\d*)', text)
        fields[f'tp{i}'] = float(match.group(1)) if match else None

    # Stop Loss: SL or Стоп
    match = re.search(r'(?:SL|Стоп):?\s*\$?(\d+\.?\d*)', text)
    fields['sl'] = float(match.group(1)) if match else None

    # Risk Percentage
    match = re.search(r'[Рр]иск:?\s*(\d+)%?', text)
    fields['risk_percent'] = float(match.group(1)) if match else None

    return fields
```

**Important**: All fields are optional (nullable). Parser never fails if fields are missing.

#### 2.2.2 Translation Engine (`src/translators/`)

**Primary: Gemini API** (`gemini.py`)

```python
async def gemini_translate(text: str) -> str:
    """Translate Russian to English using Gemini"""
    import google.generativeai as genai

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)

    prompt = f"""Translate the following trading signal text from Russian to English.
IMPORTANT RULES:
- Keep these terms EXACTLY as is: TP1, TP2, TP3, SL, LONG, SHORT, tickers (e.g., BTC/USDT)
- Preserve all numbers and price levels exactly
- Preserve emojis
- Preserve line breaks and formatting
- Only translate descriptive text

Text to translate:
{text}

Return ONLY the translated text, nothing else."""

    response = model.generate_content(prompt)
    return response.text
```

**Fallback: Google Translate** (`google.py`)

```python
async def google_translate(text: str) -> str:
    """Fallback translation using Google Translate API"""
    from google.cloud import translate_v2

    client = translate_v2.Client()
    result = client.translate(text, target_language='en')

    # Post-process: restore trading terms
    translated = result['translatedText']
    translated = restore_trading_terms(translated)
    return translated
```

**Orchestration with Fallback** (`fallback.py`)

```python
async def translate_text_with_fallback(text: str, timeout: int = 30) -> str:
    """Try Gemini first, fallback to Google Translate on failure"""
    try:
        # Attempt Gemini with timeout
        result = await asyncio.wait_for(
            gemini_translate(text),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("Gemini timeout, falling back to Google Translate")
        return await google_translate(text)
    except Exception as e:
        logger.warning(f"Gemini error: {e}, falling back")
        return await google_translate(text)
```

**Terminology Preservation**:

After Google Translate, run post-processing to restore trading terms:

```python
def restore_trading_terms(text: str) -> str:
    """Fix accidentally translated trading terms"""
    replacements = {
        'tp 1': 'TP1', 'tp1': 'TP1',
        'tp 2': 'TP2', 'tp2': 'TP2',
        'tp 3': 'TP3', 'tp3': 'TP3',
        'sl ': 'SL ', 'stop loss': 'SL',
        'long': 'LONG',
        'short': 'SHORT',
    }

    for original, replacement in replacements.items():
        text = text.replace(original.lower(), replacement)

    return text
```

#### 2.2.3 OCR Engine (`src/ocr/gemini_ocr.py`)

Extracts text from trading chart images using Gemini Vision:

```python
async def translate_image_ocr(image_path: str) -> str:
    """Extract and translate text from trading chart image"""
    import google.generativeai as genai

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)

    # Upload image file
    file = genai.upload_file(image_path)

    prompt = """Extract ALL visible text from this trading chart/screenshot image.
If text is visible, translate it to English.
Preserve numbers, currency symbols, and ticker symbols (e.g., BTC/USDT, $, %).
If no readable text is found on the image, return 'NO_TEXT_FOUND'.

Return in format:
EXTRACTED: [original language text]
TRANSLATED: [english translation]

If no text found:
EXTRACTED: (none)
TRANSLATED: (none)"""

    response = model.generate_content([prompt, file])

    # Parse structured response
    text = response.text
    lines = text.split('\n')

    extracted = None
    translated = None
    for line in lines:
        if line.startswith('EXTRACTED:'):
            extracted = line.replace('EXTRACTED:', '').strip()
        elif line.startswith('TRANSLATED:'):
            translated = line.replace('TRANSLATED:', '').strip()

    if extracted == '(none)' or extracted == 'NO_TEXT_FOUND':
        return None

    return f"[On chart]: {translated}" if translated else None
```

**Configuration**:
- `GEMINI_API_KEY`: Google AI API key
- `GEMINI_MODEL`: Model name (default: `gemini-2.0-flash`)
- `TIMEOUT_GEMINI_SEC`: Max API timeout (default: 30s)

**Parallel Processing**:

Text translation and image OCR run concurrently:

```python
translation_result = await asyncio.gather(
    translate_text_with_fallback(message.text),
    translate_image_ocr(media_info['local_path']) if media_info else asyncio.sleep(0),
    return_exceptions=True
)

translated_text = translation_result[0]
image_ocr = translation_result[1] if len(translation_result) > 1 else None
```

#### 2.2.4 Media Downloader (`src/media/downloader.py`)

Downloads and stores media attachments:

```python
async def download_and_process_media(client, message, entity_id, is_update=False):
    """Download media from Telegram message"""
    import os

    if not message.photo and not message.document:
        return None

    # Create media directory
    os.makedirs(config.MEDIA_DOWNLOAD_DIR, exist_ok=True)

    # Download file
    file_path = await message.download_media(
        file=config.MEDIA_DOWNLOAD_DIR
    )

    # Enforce size limit
    if os.path.getsize(file_path) > config.MAX_IMAGE_SIZE_MB * 1024 * 1024:
        logger.warning(f"Image too large: {file_path}")
        os.remove(file_path)
        return None

    # Save metadata to database
    file_record = {
        'local_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'downloaded_at': datetime.utcnow()
    }

    # Update DB with file path
    if is_update:
        await db.execute(
            "UPDATE signal_updates SET image_local_path = %s WHERE id = %s",
            (file_path, entity_id)
        )
    else:
        await db.execute(
            "UPDATE signals SET image_local_path = %s WHERE id = %s",
            (file_path, entity_id)
        )

    return file_record
```

**Configuration**:
- `MEDIA_DOWNLOAD_DIR`: Local directory for downloaded files (default: `/tmp/signals`)
- `MAX_IMAGE_SIZE_MB`: Max file size to process (default: 50 MB)

**Cleanup Policy**: Files are deleted after successful posting to target group to conserve disk space.

#### 2.2.5 Message Formatter (`src/formatters/message.py`)

Builds final English message for posting:

```python
def build_final_message(translated_text: str, image_ocr: str, parsed_fields: dict) -> str:
    """Construct final English message to post to target group"""
    parts = [translated_text]

    # Append OCR results if available
    if image_ocr:
        parts.append(f"\n\n_Chart OCR:_\n{image_ocr}")

    return '\n'.join(parts)
```

**Output Example**:
```
LONG BTC/USDT 15min
Entry: 65000-65500
TP1: 66000
TP2: 67000
TP3: 68000
SL: 64000
Risk: 2%

Test signal for verification

_Chart OCR:_
[On chart]: BTCUSDT 15m, RSI: 45.2, MACD: Bullish divergence
```

#### 2.2.6 Database Manager (`src/db/`)

Handles all database operations using asyncpg connection pool:

**Connection Pool** (`connection.py`):
```python
import asyncpg

async def init_db(config):
    """Initialize PostgreSQL connection pool"""
    global pool
    pool = await asyncpg.create_pool(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        database=config.POSTGRES_DB,
        min_size=2,
        max_size=10
    )
    logger.info("Database pool initialized")
```

**Query Operations** (`queries.py`):
```python
async def db_insert_signal(signal_data: dict) -> int:
    """Insert new signal record, return signal_id"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO signals (
                source_chat_id, source_message_id, source_user_id,
                original_text, status, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id""",
            signal_data['source_chat_id'],
            signal_data['source_message_id'],
            signal_data['source_user_id'],
            signal_data['original_text'],
            signal_data['status'],
            signal_data['created_at']
        )
        return row['id']

async def db_update_signal(signal_id: int, updates: dict) -> None:
    """Update signal record with new fields"""
    # Dynamic UPDATE query builder
    set_clause = ', '.join([f"{k} = ${i+2}" for i, k in enumerate(updates.keys())])
    query = f"UPDATE signals SET {set_clause} WHERE id = $1"

    async with pool.acquire() as conn:
        await conn.execute(query, signal_id, *updates.values())

async def db_find_signal_by_source_msg(chat_id: int, msg_id: int) -> dict:
    """Find signal by source message ID (for reply handling)"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM signals
               WHERE source_chat_id = $1 AND source_message_id = $2""",
            chat_id, msg_id
        )
        return dict(row) if row else None
```

---

### 2.3 Publisher Client (Account B)

**Purpose**: Post translated signals to target Telegram group

**Technology**: Telethon MTProto Client with separate user account credentials

**Responsibilities**:
- Authenticate with Telegram using Account B credentials
- Join `TARGET_GROUP_ID` with write permissions
- Receive posting requests from core logic
- Post messages with media attachments
- Handle reply threading (reply_to parameter)
- Return posted message ID for mapping storage
- Maintain persistent session

**Posting Operations**:

**New Signal**:
```python
posted_msg = await client_publisher.send_message(
    entity=config.TARGET_GROUP_ID,
    message=final_message,
    file=media_info['local_path'] if media_info else None
)
target_msg_id = posted_msg.id
```

**Reply to Existing Signal**:
```python
posted_msg = await client_publisher.send_message(
    entity=config.TARGET_GROUP_ID,
    message=final_message,
    file=media_info['local_path'] if media_info else None,
    reply_to=parent_signal['target_message_id']  # Thread messages
)
target_update_msg_id = posted_msg.id
```

**Configuration**:
- `PUBLISHER_API_ID`: Telegram API ID
- `PUBLISHER_API_HASH`: Telegram API Hash
- `PUBLISHER_PHONE`: Phone number for authentication
- `PUBLISHER_SESSION_FILE`: Path to persistent session file
- `TARGET_GROUP_ID`: Group chat ID to post to

**Error Handling**:
- Rate limiting: Respect Telegram rate limits (avoid flood wait)
- Connection loss: Exponential backoff reconnection
- Permission errors: Log and mark signal as `ERROR_POSTING_FAILED`
- Media upload failures: Retry 3 times, then post without media

---

## 3. Data Flow

### 3.1 New Signal Processing Flow

**Step-by-Step Execution**:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          NEW SIGNAL FLOW                                   │
└────────────────────────────────────────────────────────────────────────────┘

1. EVENT DETECTION (Reader Client)
   │
   ├─> Message posted in SOURCE_GROUP
   ├─> Contains "#Идея" hashtag
   ├─> Not a reply (new signal)
   └─> Extract: message_id, sender_id, text, media, timestamp
        │
        ▼

2. DATABASE RECORD CREATION
   │
   ├─> INSERT INTO signals (status='PENDING')
   ├─> Store: source_chat_id, source_message_id, original_text, created_at
   └─> Return: signal_id (e.g., 42)
        │
        ▼

3. STATUS UPDATE
   │
   ├─> UPDATE signals SET status='PROCESSING' WHERE id=42
   └─> Prevents duplicate processing
        │
        ▼

4. STRUCTURED FIELD EXTRACTION
   │
   ├─> parse_trading_signal(text)
   ├─> Extract: pair, direction, timeframe, entry_range, tp1-3, sl, risk
   └─> UPDATE signals SET pair=..., direction=..., WHERE id=42
        │
        ▼

5. MEDIA DOWNLOAD (if present)
   │
   ├─> Check: message.photo or message.document?
   ├─> download_and_process_media()
   ├─> Save to: /tmp/signals/<filename>
   ├─> UPDATE signals SET image_local_path=... WHERE id=42
   └─> Return: {local_path, file_size}
        │
        ▼

6. PARALLEL TRANSLATION + OCR
   │
   ├─> asyncio.gather([
   │       translate_text_with_fallback(text),     # 3-8 seconds
   │       translate_image_ocr(image_path)         # 2-5 seconds
   │   ])
   │
   ├─> Gemini API: Translate Russian → English
   ├─> Preserve: TP1, TP2, TP3, SL, LONG, SHORT, tickers
   ├─> Fallback: Google Translate if Gemini fails
   └─> Return: (translated_text, image_ocr_text)
        │
        ▼

7. MESSAGE FORMATTING
   │
   ├─> build_final_message(translated_text, image_ocr, parsed_fields)
   ├─> Combine text + OCR results
   └─> Format for target group
        │
        ▼

8. PUBLISH TO TARGET GROUP (Publisher Client)
   │
   ├─> client_publisher.send_message(
   │       entity=TARGET_GROUP_ID,
   │       message=final_message,
   │       file=image_path
   │   )
   ├─> Wait for confirmation
   └─> Return: target_message_id (e.g., 7890)
        │
        ▼

9. DATABASE MAPPING UPDATE
   │
   ├─> UPDATE signals SET
   │       target_message_id=7890,
   │       target_chat_id=TARGET_GROUP_ID,
   │       translated_text=...,
   │       image_ocr_text=...,
   │       status='POSTED',
   │       processed_at=NOW()
   │   WHERE id=42
   │
   └─> Mapping stored: source_msg_id → target_msg_id
        │
        ▼

10. CLEANUP
   │
   ├─> Delete local media file: os.remove(image_path)
   └─> Free disk space

   ✅ COMPLETE (Total time: ~6-12 seconds)
```

### 3.2 Reply Handling Flow (Signal Updates)

**Step-by-Step Execution**:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        REPLY HANDLING FLOW                                 │
└────────────────────────────────────────────────────────────────────────────┘

1. EVENT DETECTION (Reader Client)
   │
   ├─> Message posted in SOURCE_GROUP
   ├─> Contains "#Идея" hashtag (optional for replies)
   ├─> event.message.is_reply == True
   └─> Extract: reply_to_msg_id (parent message ID)
        │
        ▼

2. PARENT SIGNAL LOOKUP
   │
   ├─> db_find_signal_by_source_msg(SOURCE_GROUP_ID, reply_to_msg_id)
   ├─> Query: SELECT * FROM signals WHERE source_message_id = reply_to_msg_id
   │
   ├─> IF NOT FOUND:
   │   └─> Log warning: "Reply to unknown signal"
   │   └─> IGNORE (orphan reply, not a signal update)
   │
   ├─> IF FOUND:
   │   └─> Return: parent_signal {id, target_message_id, ...}
        │
        ▼

3. CREATE UPDATE RECORD
   │
   ├─> INSERT INTO signal_updates (
   │       signal_id=parent_signal.id,
   │       source_chat_id=SOURCE_GROUP_ID,
   │       source_message_id=reply_message_id,
   │       original_text=...,
   │       status='PROCESSING'
   │   )
   └─> Return: update_id (e.g., 15)
        │
        ▼

4. PROCESS UPDATE (same as new signal)
   │
   ├─> Download media (if present)
   ├─> Translate text with fallback
   ├─> OCR image (if present)
   └─> Build final message
        │
        ▼

5. POST AS THREADED REPLY (Publisher Client)
   │
   ├─> client_publisher.send_message(
   │       entity=TARGET_GROUP_ID,
   │       message=final_message,
   │       file=image_path,
   │       reply_to=parent_signal.target_message_id  ← KEY: Thread preservation
   │   )
   │
   └─> Return: target_update_msg_id (e.g., 7891)
        │
        ▼

6. DATABASE UPDATE
   │
   ├─> UPDATE signal_updates SET
   │       target_message_id=7891,
   │       target_chat_id=TARGET_GROUP_ID,
   │       translated_text=...,
   │       status='POSTED',
   │       processed_at=NOW()
   │   WHERE id=15
   │
   └─> Mapping stored: reply linked to parent via signal_id FK

   ✅ COMPLETE

RESULT:
   Source Group:                    Target Group:
   ┌──────────────────┐            ┌──────────────────┐
   │ Signal (msg 123) │  ────>     │ Signal (msg 7890)│
   │  └─> Reply (456) │  ────>     │  └─> Reply (7891)│
   └──────────────────┘            └──────────────────┘

   Reply chain preserved!
```

### 3.3 Error Recovery Flow

**Translation Failure**:
```
Gemini API Call
    │
    ├─> Timeout after 30s
    │   └─> Fallback: Google Translate
    │       └─> Success → Continue
    │
    ├─> API Error (rate limit, auth failure)
    │   └─> Fallback: Google Translate
    │       └─> Success → Continue
    │
    └─> Both fail
        └─> Post original Russian text
        └─> UPDATE signals SET status='ERROR_TRANSLATION_FAILED'
```

**Posting Failure**:
```
Publisher Client send_message()
    │
    ├─> FloodWait Error (rate limit)
    │   └─> Wait N seconds
    │   └─> Retry (up to 3 attempts)
    │
    ├─> Permission Error
    │   └─> Log error
    │   └─> UPDATE signals SET status='ERROR_POSTING_FAILED'
    │
    └─> Network Error
        └─> Retry with exponential backoff (1s, 2s, 4s)
        └─> After 3 failures: mark ERROR_POSTING_FAILED
```

---

## 4. Database Schema

### 4.1 Table: `signals`

**Purpose**: Store main trading signals with source→target mapping

```sql
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,

    -- Source group tracking
    source_chat_id BIGINT NOT NULL,          -- SOURCE_GROUP_ID (e.g., -100123456789)
    source_message_id BIGINT NOT NULL,       -- Message ID in source group
    source_user_id BIGINT NOT NULL,          -- Author Telegram user ID

    -- Target group tracking
    target_chat_id BIGINT,                   -- TARGET_GROUP_ID (populated after posting)
    target_message_id BIGINT,                -- Message ID in target group

    -- Extracted trading signal fields (all nullable)
    pair VARCHAR(20),                        -- e.g., "BTC/USDT", "XION/USDT"
    direction VARCHAR(10),                   -- "LONG" or "SHORT"
    timeframe VARCHAR(20),                   -- e.g., "15мин", "1H", "4H", "D"
    entry_range VARCHAR(50),                 -- e.g., "0.98-0.9283"
    tp1 NUMERIC(20,10),                      -- Take Profit 1
    tp2 NUMERIC(20,10),                      -- Take Profit 2
    tp3 NUMERIC(20,10),                      -- Take Profit 3
    sl NUMERIC(20,10),                       -- Stop Loss
    risk_percent FLOAT,                      -- Risk percentage (e.g., 2.0)

    -- Content
    original_text TEXT NOT NULL,             -- Full Russian text (as received)
    translated_text TEXT,                    -- Full English translation
    image_source_url TEXT,                   -- Telegram file URL (original image)
    image_local_path TEXT,                   -- Local filesystem path (/tmp/signals/...)
    image_ocr_text TEXT,                     -- Extracted text from image (translated)

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,   -- When translation completed
    status VARCHAR(30) DEFAULT 'PENDING',
    error_message TEXT,                      -- Error details if failed

    -- Constraints
    CONSTRAINT unique_source_msg UNIQUE (source_chat_id, source_message_id),
    CONSTRAINT check_status CHECK (status IN (
        'PENDING',
        'PROCESSING',
        'POSTED',
        'ERROR_TRANSLATION_FAILED',
        'ERROR_POSTING_FAILED',
        'ERROR_OCR_FAILED'
    ))
);

-- Indexes for performance
CREATE INDEX idx_source_msg ON signals(source_chat_id, source_message_id);
CREATE INDEX idx_target_msg ON signals(target_message_id);
CREATE INDEX idx_status ON signals(status);
CREATE INDEX idx_created_at ON signals(created_at DESC);
CREATE INDEX idx_pair_direction ON signals(pair, direction);
```

**Status Values**:
- `PENDING`: Signal detected, waiting for processing
- `PROCESSING`: Translation/OCR in progress
- `POSTED`: Successfully posted to target group
- `ERROR_TRANSLATION_FAILED`: Gemini + Google Translate both failed
- `ERROR_POSTING_FAILED`: Unable to post to target group
- `ERROR_OCR_FAILED`: Image OCR failed (signal still posted without OCR)

**Usage Example**:
```sql
-- Find all posted BTC/USDT LONG signals in last 7 days
SELECT * FROM signals
WHERE pair = 'BTC/USDT'
  AND direction = 'LONG'
  AND status = 'POSTED'
  AND created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;

-- Find source message mapping for reply handling
SELECT id, target_message_id FROM signals
WHERE source_chat_id = -100123456789
  AND source_message_id = 456;
```

---

### 4.2 Table: `signal_updates`

**Purpose**: Store replies and updates to existing signals (maintain thread history)

```sql
CREATE TABLE signal_updates (
    id SERIAL PRIMARY KEY,

    -- Parent signal reference
    signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,

    -- Source reply tracking
    source_chat_id BIGINT NOT NULL,          -- SOURCE_GROUP_ID
    source_message_id BIGINT NOT NULL,       -- Reply message ID in source group
    source_user_id BIGINT,                   -- Reply author Telegram user ID

    -- Target reply tracking
    target_chat_id BIGINT,                   -- TARGET_GROUP_ID
    target_message_id BIGINT,                -- Reply message ID in target group

    -- Content
    original_text TEXT NOT NULL,             -- Russian reply text
    translated_text TEXT,                    -- English translation
    image_source_url TEXT,                   -- Image URL (if attached)
    image_local_path TEXT,                   -- Local image path
    image_ocr_text TEXT,                     -- OCR results

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(30) DEFAULT 'PENDING',
    error_message TEXT,

    -- Constraints
    CONSTRAINT unique_source_reply UNIQUE (source_chat_id, source_message_id),
    CONSTRAINT check_status CHECK (status IN (
        'PENDING',
        'PROCESSING',
        'POSTED',
        'ERROR_TRANSLATION_FAILED',
        'ERROR_POSTING_FAILED',
        'ERROR_OCR_FAILED'
    ))
);

-- Indexes
CREATE INDEX idx_signal_updates_parent ON signal_updates(signal_id);
CREATE INDEX idx_source_reply ON signal_updates(source_chat_id, source_message_id);
CREATE INDEX idx_created_at ON signal_updates(created_at DESC);
```

**Foreign Key Behavior**:
- `ON DELETE CASCADE`: If parent signal is deleted, all updates are deleted too

**Usage Example**:
```sql
-- Find all updates for a specific signal
SELECT * FROM signal_updates
WHERE signal_id = 42
ORDER BY created_at ASC;

-- Find total update count per signal
SELECT s.id, s.pair, COUNT(u.id) as update_count
FROM signals s
LEFT JOIN signal_updates u ON s.id = u.signal_id
WHERE s.status = 'POSTED'
GROUP BY s.id, s.pair
ORDER BY update_count DESC;
```

---

### 4.3 Table: `translation_cache`

**Purpose**: Cache translations to reduce API costs and improve latency

```sql
CREATE TABLE translation_cache (
    id SERIAL PRIMARY KEY,

    source_text_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA256 hash of source_text
    source_text TEXT NOT NULL,                     -- Original Russian text
    translated_text TEXT NOT NULL,                 -- Cached English translation
    language_pair VARCHAR(10) DEFAULT 'ru_en',     -- Source→Target language
    model VARCHAR(50),                             -- 'gemini' or 'google_translate'

    -- Usage tracking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    usage_count INT DEFAULT 1,

    -- Metadata
    avg_confidence FLOAT                           -- Translation confidence (if available)
);

-- Indexes
CREATE INDEX idx_source_hash ON translation_cache(source_text_hash);
CREATE INDEX idx_usage_count ON translation_cache(usage_count DESC);
CREATE INDEX idx_last_used ON translation_cache(last_used_at DESC);
```

**Cache Key Generation**:
```python
import hashlib

def get_cache_key(text: str) -> str:
    """Generate SHA256 hash for cache lookup"""
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
```

**Cache Lookup**:
```python
async def get_cached_translation(text: str) -> str:
    """Check cache before calling API"""
    cache_key = get_cache_key(text)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT translated_text FROM translation_cache
               WHERE source_text_hash = $1""",
            cache_key
        )

        if row:
            # Update usage stats
            await conn.execute(
                """UPDATE translation_cache
                   SET usage_count = usage_count + 1,
                       last_used_at = NOW()
                   WHERE source_text_hash = $1""",
                cache_key
            )
            logger.info(f"Cache hit for text hash {cache_key[:8]}...")
            return row['translated_text']

    return None  # Cache miss
```

**Cache Storage**:
```python
async def store_translation(source: str, translated: str, model: str):
    """Store translation in cache"""
    cache_key = get_cache_key(source)

    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO translation_cache (
                source_text_hash, source_text, translated_text, model
            ) VALUES ($1, $2, $3, $4)
            ON CONFLICT (source_text_hash) DO UPDATE
            SET usage_count = translation_cache.usage_count + 1,
                last_used_at = NOW()""",
            cache_key, source, translated, model
        )
```

**Cache Eviction Policy**:
```sql
-- Remove entries not used in 90 days
DELETE FROM translation_cache
WHERE last_used_at < NOW() - INTERVAL '90 days'
  AND usage_count < 5;
```

---

### 4.4 Database Relationships

```
┌─────────────────────┐
│      signals        │
│─────────────────────│
│ id (PK)             │←─────────┐
│ source_message_id   │          │
│ target_message_id   │          │ Foreign Key
│ pair, direction     │          │ (ON DELETE CASCADE)
│ original_text       │          │
│ translated_text     │          │
│ status              │          │
└─────────────────────┘          │
                                  │
                                  │
                        ┌─────────────────────┐
                        │  signal_updates     │
                        │─────────────────────│
                        │ id (PK)             │
                        │ signal_id (FK) ─────┘
                        │ source_message_id   │
                        │ target_message_id   │
                        │ original_text       │
                        │ translated_text     │
                        │ status              │
                        └─────────────────────┘

┌─────────────────────┐
│ translation_cache   │
│─────────────────────│
│ id (PK)             │
│ source_text_hash    │ (UNIQUE)
│ source_text         │
│ translated_text     │
│ model               │
│ usage_count         │
└─────────────────────┘
```

---

## 5. Message Threading Logic

### 5.1 Threading Mechanism

**Objective**: Maintain reply chains between source and target groups so conversations remain coherent.

**Challenge**:
- Source group uses message IDs: `123, 456, 789`
- Target group uses different IDs: `7890, 7891, 7892`
- Must map source reply relationships to target reply relationships

**Solution**: Store bidirectional message ID mapping in database

### 5.2 Reply Detection

**Step 1: Detect Reply in Source Group**

```python
@client_reader.on(events.NewMessage(chats=[SOURCE_GROUP_ID]))
async def on_new_message(event):
    message = event.message

    # Check if message is a reply
    if message.is_reply:
        # Extract parent message ID
        reply_to_msg_id = message.reply_to_msg_id

        # This is an update to an existing signal
        await handle_signal_update(message, reply_to_msg_id)
```

**Step 2: Lookup Parent Signal**

```python
async def handle_signal_update(message, reply_to_msg_id):
    # Query database for parent signal
    parent_signal = await db_find_signal_by_source_msg(
        config.SOURCE_GROUP_ID,
        reply_to_msg_id
    )

    if not parent_signal:
        # Reply to non-signal message (ignore)
        logger.warning(f"Reply to unknown signal {reply_to_msg_id}")
        return

    # Found parent signal with target_message_id
    logger.info(f"Reply detected: parent signal_id={parent_signal['id']}")
```

### 5.3 Thread Preservation

**Step 3: Post as Threaded Reply in Target Group**

```python
# Translate reply text
translated_text = await translate_text_with_fallback(message.text)

# Post as reply to parent target message
posted_msg = await client_publisher.send_message(
    entity=config.TARGET_GROUP_ID,
    message=translated_text,
    reply_to=parent_signal['target_message_id']  # KEY: Preserve thread
)

logger.info(f"Posted reply {posted_msg.id} → parent {parent_signal['target_message_id']}")
```

**Step 4: Store Update Mapping**

```python
# Store in signal_updates table
await db_insert_signal_update({
    'signal_id': parent_signal['id'],
    'source_message_id': message.id,
    'target_message_id': posted_msg.id,
    'translated_text': translated_text,
    'status': 'POSTED'
})
```

### 5.4 Visual Mapping Example

**Source Group** (Russian):
```
Message 123: #Идея BTC/USDT LONG ...
  └─> Reply 456: "Пробит TP1" (TP1 hit)
       └─> Reply 789: "Закрываем половину" (Close half position)
```

**Database Mapping**:
```
signals table:
  id=42, source_message_id=123, target_message_id=7890

signal_updates table:
  id=15, signal_id=42, source_message_id=456, target_message_id=7891
  id=16, signal_id=42, source_message_id=789, target_message_id=7892
```

**Target Group** (English):
```
Message 7890: #Signal BTC/USDT LONG ...
  └─> Reply 7891: "TP1 hit"
       └─> Reply 7892: "Close half position"
```

**Thread Integrity Maintained!**

### 5.5 Edge Cases

**Case 1: Reply to Deleted Signal**

```python
parent_signal = await db_find_signal_by_source_msg(...)

if not parent_signal:
    # Parent signal was deleted or never processed
    # Option 1: Ignore reply
    logger.warning("Orphan reply detected")
    return

    # Option 2: Post as standalone message (no threading)
    # await post_without_threading(message)
```

**Case 2: Nested Replies (depth > 1)**

Telegram supports deep reply chains:
```
A → B → C → D
```

Current implementation: Always replies to immediate parent
- D replies to C
- C replies to B
- B replies to A

Database stores full chain via `signal_updates.signal_id` linking to parent signal.

**Case 3: Reply Before Parent is Processed**

Race condition:
1. Signal posted (msg 123) → processing started
2. User immediately replies (msg 456) → detected
3. Parent processing not yet complete (no `target_message_id` yet)

**Solution**: Implement async wait with timeout

```python
async def wait_for_parent_posting(parent_msg_id, timeout=60):
    """Wait for parent signal to be posted"""
    start = time.time()

    while time.time() - start < timeout:
        parent = await db_find_signal_by_source_msg(SOURCE_GROUP_ID, parent_msg_id)

        if parent and parent['target_message_id']:
            return parent

        await asyncio.sleep(2)  # Poll every 2 seconds

    raise TimeoutError(f"Parent signal {parent_msg_id} not posted within {timeout}s")
```

---

## 6. Error Handling Strategy

### 6.1 Retry Strategy

**Exponential Backoff Implementation**:

```python
async def retry_with_backoff(func, max_retries=3, base_delay=1):
    """Retry function with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise  # Final attempt failed, propagate error

            delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
            logger.warning(f"Attempt {attempt+1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
```

**Usage**:
```python
# Telegram API calls
posted_msg = await retry_with_backoff(
    lambda: client_publisher.send_message(...),
    max_retries=3,
    base_delay=1
)

# Database operations
signal_id = await retry_with_backoff(
    lambda: db_insert_signal(signal_data),
    max_retries=3,
    base_delay=0.5
)
```

### 6.2 Graceful Degradation

**Translation Failures**:

```python
async def translate_with_graceful_degradation(text: str):
    """Try translation with fallback chain"""
    try:
        # Attempt 1: Gemini API
        return await gemini_translate(text)
    except Exception as e1:
        logger.warning(f"Gemini failed: {e1}, trying Google Translate")

        try:
            # Attempt 2: Google Translate
            return await google_translate(text)
        except Exception as e2:
            logger.error(f"All translation services failed: {e2}")

            # Attempt 3: Post original text with warning
            return f"⚠️ Translation unavailable\n\n{text}"
```

**OCR Failures**:

```python
async def process_image_with_degradation(image_path: str):
    """Try OCR, skip if fails"""
    try:
        return await translate_image_ocr(image_path)
    except Exception as e:
        logger.warning(f"OCR failed: {e}, posting without chart text")
        return None  # Continue without OCR
```

**Posting Failures**:

```python
async def post_with_degradation(message_text, image_path=None):
    """Try posting with media, fallback to text-only"""
    try:
        # Attempt with media
        return await client_publisher.send_message(
            entity=TARGET_GROUP_ID,
            message=message_text,
            file=image_path
        )
    except Exception as e:
        logger.warning(f"Posting with media failed: {e}, trying text-only")

        # Fallback: text-only
        return await client_publisher.send_message(
            entity=TARGET_GROUP_ID,
            message=message_text
        )
```

### 6.3 Health Checks

**Database Health Check** (every 5 minutes):

```python
async def check_db_health():
    """Verify database connection is alive"""
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        logger.info("Database health check: OK")
        return True
    except Exception as e:
        logger.error(f"Database health check FAILED: {e}")
        # Attempt reconnection
        await reconnect_db()
        return False

# Schedule periodic health check
async def db_health_monitor():
    while True:
        await asyncio.sleep(300)  # 5 minutes
        await check_db_health()
```

**Telethon Client Health Check** (every 10 minutes):

```python
async def check_client_health(client, client_name):
    """Verify Telethon client is connected"""
    try:
        if not client.is_connected():
            logger.warning(f"{client_name} disconnected, reconnecting...")
            await client.connect()

        # Verify can access entity
        await client.get_entity("me")
        logger.info(f"{client_name} health check: OK")
        return True
    except Exception as e:
        logger.error(f"{client_name} health check FAILED: {e}")
        await reconnect_client(client, client_name)
        return False

# Schedule periodic health checks
async def client_health_monitor():
    while True:
        await asyncio.sleep(600)  # 10 minutes
        await check_client_health(client_reader, "Reader")
        await check_client_health(client_publisher, "Publisher")
```

**Reconnection Strategy**:

```python
async def reconnect_client(client, client_name, max_attempts=5):
    """Reconnect Telegram client with exponential backoff"""
    for attempt in range(max_attempts):
        try:
            await client.disconnect()
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s, 8s, 16s
            await client.connect()
            logger.info(f"{client_name} reconnected successfully")
            return True
        except Exception as e:
            logger.warning(f"{client_name} reconnection attempt {attempt+1} failed: {e}")

    # All attempts failed
    logger.critical(f"{client_name} reconnection FAILED after {max_attempts} attempts")
    raise ConnectionError(f"Cannot reconnect {client_name}")
```

### 6.4 Error Status Tracking

**Database Error States**:

```python
# Mark signal as failed with error details
await db_update_signal(signal_id, {
    'status': 'ERROR_TRANSLATION_FAILED',
    'error_message': str(exception),
    'processed_at': datetime.utcnow()
})

# Query failed signals for manual review
failed_signals = await db.fetch(
    """SELECT * FROM signals
       WHERE status LIKE 'ERROR_%'
       ORDER BY created_at DESC
       LIMIT 50"""
)
```

**Error Metrics**:

```python
# Track error rates for monitoring
error_counts = {
    'translation_failures': 0,
    'posting_failures': 0,
    'ocr_failures': 0,
    'db_failures': 0
}

def increment_error_metric(error_type: str):
    error_counts[error_type] += 1
    logger.info(f"Error metrics: {error_counts}")
```

### 6.5 Circuit Breaker Pattern

**Prevent cascading failures**:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.opened_at = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func):
        # If circuit is OPEN, reject immediately
        if self.state == 'OPEN':
            if time.time() - self.opened_at > self.timeout:
                self.state = 'HALF_OPEN'
                logger.info("Circuit breaker: HALF_OPEN (testing)")
            else:
                raise Exception("Circuit breaker OPEN")

        try:
            result = await func()

            # Success: reset failure count
            self.failure_count = 0
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                logger.info("Circuit breaker: CLOSED (recovered)")

            return result
        except Exception as e:
            self.failure_count += 1

            # Open circuit if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                self.opened_at = time.time()
                logger.error(f"Circuit breaker: OPEN (too many failures)")

            raise e

# Usage
gemini_circuit = CircuitBreaker(failure_threshold=5, timeout=60)

async def call_gemini_with_circuit(text):
    return await gemini_circuit.call(lambda: gemini_translate(text))
```

---

## 7. Performance

### 7.1 Latency Target

**Goal**: <60 seconds end-to-end (source message posted → target message posted)

**Actual Performance**: 6-12 seconds (well under target)

### 7.2 Latency Breakdown

**Detailed Timeline**:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                       PERFORMANCE BREAKDOWN                                │
└────────────────────────────────────────────────────────────────────────────┘

Operation                          | Typical Time  | Notes
───────────────────────────────────|───────────────|────────────────────────
1. Event Detection                 | 50-100ms      | Telethon event listener
2. DB Insert (initial record)      | 20-50ms       | asyncpg INSERT
3. Parse Signal (regex)            | 100-200ms     | Regex extraction
4. DB Update (parsed fields)       | 20-50ms       | asyncpg UPDATE
5. Media Download                  | 500ms-2s      | Depends on file size
6. DB Update (media path)          | 20-50ms       | asyncpg UPDATE
────────────────────────────────────────────────────────────────────────────
7. PARALLEL OPERATIONS:
   ├─ Text Translation (Gemini)    | 3-8s          | API latency
   └─ Image OCR (Gemini Vision)    | 2-5s          | Runs concurrently
────────────────────────────────────────────────────────────────────────────
8. Message Formatting              | 5-10ms        | String concatenation
9. Post to Target (Publisher)      | 500ms-1s      | Telethon send_message
10. DB Update (mapping + status)   | 30-60ms       | asyncpg UPDATE
11. Cleanup (delete local file)    | 10-20ms       | os.remove()
────────────────────────────────────────────────────────────────────────────
TOTAL (typical):                   | 6-12 seconds  | ✅ Well under target
TOTAL (worst case):                | 15-20 seconds | Network delays
────────────────────────────────────────────────────────────────────────────
```

### 7.3 Performance Optimizations

**1. Parallel API Calls**:

```python
# Run translation + OCR concurrently
results = await asyncio.gather(
    translate_text_with_fallback(text),     # 3-8s
    translate_image_ocr(image_path),        # 2-5s
    return_exceptions=True
)
# Total time: max(3-8s, 2-5s) = 3-8s (NOT 5-13s sequential)
```

**Benefit**: Saves 2-5 seconds per signal

**2. Translation Cache**:

```python
# Check cache before API call
cached = await get_cached_translation(text)
if cached:
    return cached  # ~20ms (DB query)
else:
    translated = await gemini_translate(text)  # ~3-8s
    await store_translation(text, translated)
    return translated
```

**Benefit**: 99% latency reduction for repeated signals (20ms vs 3-8s)

**3. Async Database Pool**:

```python
# Connection pool prevents connection overhead
pool = await asyncpg.create_pool(
    min_size=2,   # Keep 2 connections warm
    max_size=10   # Scale up to 10 concurrent operations
)
```

**Benefit**: No connection setup latency (~50-100ms saved per operation)

**4. Non-Blocking Event Handlers**:

```python
# Create task instead of blocking
asyncio.create_task(handle_new_signal(message))
# Listener immediately returns, processes signal in background
```

**Benefit**: Multiple signals can be processed concurrently

### 7.4 Throughput Capacity

**Current Architecture**:
- Expected load: <100 signals/day
- Peak capacity: ~500 signals/hour (with async queue)

**Bottlenecks**:
1. Gemini API rate limits (60 requests/minute)
2. Telegram rate limits (20 messages/minute per account)
3. Database write throughput (not a bottleneck at this scale)

**If scaling needed**:
- Add more Publisher accounts (distribute posting)
- Implement queue system (Redis Queue, Celery)
- Cache aggressively (reduce API calls)

### 7.5 Resource Usage

**Memory**:
- Base process: ~100-150 MB
- Per signal in processing: ~5-10 MB (media + buffers)
- Peak memory (10 concurrent signals): ~250 MB

**CPU**:
- Idle: <5% (event listener)
- Processing: 10-30% (regex parsing, JSON serialization)
- API calls: <5% (I/O bound, not CPU bound)

**Disk**:
- Session files: ~100 KB each (2 accounts = 200 KB)
- Temporary media: 5-50 MB per signal (deleted after posting)
- Database: ~500 KB per 1000 signals (with indexes)

**Network**:
- Telethon: <1 KB/s idle, ~100 KB/s when downloading media
- Gemini API: ~10-50 KB per request
- Database: <10 KB/s (asyncpg binary protocol)

### 7.6 Performance Monitoring

**Key Metrics to Track**:

```python
import time
from collections import defaultdict

metrics = {
    'signal_count': 0,
    'avg_latency': 0,
    'latencies': [],
    'translation_hits': 0,
    'translation_misses': 0,
    'errors': defaultdict(int)
}

async def handle_new_signal_with_metrics(message, event):
    start_time = time.time()

    try:
        # Process signal
        await handle_new_signal(message, event)

        # Record success
        latency = time.time() - start_time
        metrics['signal_count'] += 1
        metrics['latencies'].append(latency)
        metrics['avg_latency'] = sum(metrics['latencies']) / len(metrics['latencies'])

        logger.info(f"Signal processed in {latency:.2f}s (avg: {metrics['avg_latency']:.2f}s)")
    except Exception as e:
        metrics['errors'][type(e).__name__] += 1
        raise

# Periodic metrics report
async def report_metrics():
    while True:
        await asyncio.sleep(3600)  # Every hour
        logger.info(f"Performance metrics: {metrics}")
```

**Logged Metrics**:
- `signals_processed_total`: Total signals successfully posted
- `avg_latency_seconds`: Average end-to-end processing time
- `translation_cache_hit_rate`: Cache hits / (hits + misses)
- `gemini_api_calls`: Total Gemini API requests
- `google_translate_fallbacks`: Fallback count (indicates Gemini issues)
- `posting_retries`: Number of retry attempts (indicates network issues)

---

## Appendix A: Configuration Summary

**Environment Variables** (`.env`):

```ini
# === Telegram Accounts ===
READER_API_ID=1234567
READER_API_HASH=abcdef123456789abcdef123456789ab
READER_PHONE=+1234567890
READER_SESSION_FILE=reader.session

PUBLISHER_API_ID=9876543
PUBLISHER_API_HASH=zyxwvu987654321zyxwvu987654321zy
PUBLISHER_PHONE=+0987654321
PUBLISHER_SESSION_FILE=publisher.session

# === Group IDs ===
SOURCE_GROUP_ID=-100123456789
TARGET_GROUP_ID=-100987654321

# === Gemini API ===
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.0-flash

# === Database ===
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=signal_bot
POSTGRES_HOST=db
POSTGRES_PORT=5432

# === Application ===
LOG_LEVEL=INFO
MAX_RETRIES=3
TIMEOUT_GEMINI_SEC=30
MEDIA_DOWNLOAD_DIR=/tmp/signals
MAX_IMAGE_SIZE_MB=50
```

---

## Appendix B: Deployment Checklist

**Pre-Production**:
- [ ] Both Telegram accounts have API credentials
- [ ] Both accounts joined SOURCE_GROUP and TARGET_GROUP
- [ ] Gemini API key is valid with quota
- [ ] PostgreSQL database created
- [ ] Redis running (optional but recommended)
- [ ] Session files authenticated (run locally first)
- [ ] `.env` file configured correctly
- [ ] Docker Compose tested locally

**Production Deployment**:
```bash
# 1. Clone repository
git clone https://github.com/user/telegram-signals-parisng.git
cd telegram-signals-parisng

# 2. Configure environment
cp .env.example .env
nano .env  # Fill in credentials

# 3. Start services
docker-compose up -d

# 4. Verify logs
docker-compose logs -f app

# 5. Test with sample signal
# Post test message in SOURCE_GROUP with #Идея hashtag

# 6. Monitor database
docker-compose exec db psql -U postgres signal_bot
SELECT * FROM signals ORDER BY created_at DESC LIMIT 10;
```

**Health Verification**:
- [ ] Reader client connected (check logs)
- [ ] Publisher client connected (check logs)
- [ ] Database accepting connections
- [ ] Test signal translated and posted successfully
- [ ] Reply threading works correctly
- [ ] Translation cache populated
- [ ] No errors in logs

---

## Appendix C: Troubleshooting Guide

**Issue**: Signals not detected
- Check: `SOURCE_GROUP_ID` matches actual group
- Check: Reader account has read permission
- Check: Message contains exact hashtag `#Идея` (case-sensitive)
- Check: Logs show event listener registered

**Issue**: Translation fails
- Check: Gemini API key is valid
- Check: API quota not exceeded (Google AI Studio dashboard)
- Check: Fallback to Google Translate working (check logs)
- Test: Send simple text to Gemini API manually

**Issue**: Posting fails
- Check: Publisher account in TARGET_GROUP
- Check: Account has write permissions (not restricted)
- Check: Rate limits not exceeded (check FloodWait errors)
- Check: Session file valid (re-authenticate if needed)

**Issue**: Reply threading broken
- Check: `signals` table has `target_message_id` populated
- Check: `signal_updates` table has `signal_id` foreign key
- Query: `SELECT * FROM signals WHERE source_message_id = <parent_id>`
- Verify: Parent signal was posted before reply

**Issue**: Database connection errors
- Check: PostgreSQL running (`docker-compose ps db`)
- Check: Credentials in `.env` match database
- Test: `psql -U postgres -h localhost signal_bot`
- Check: Network connectivity (firewall rules)

---

**Document Version**: 1.0
**Last Updated**: 2025-12-01
**Project**: Telegram Signal Translator Bot
**Repository**: https://github.com/liker/telegram-signals-parisng
