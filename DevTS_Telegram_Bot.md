# Technical Specification for Developer
## Telegram Signal Translator Bot with Dual-Account Architecture

---

## 1. EXECUTIVE SUMMARY

Build an asynchronous backend service that:
- **Reads** trading signals from a Russian Telegram group using Account A (Reader)
- **Translates** text & OCR image content to English using Gemini API
- **Posts** translated signals to an English Telegram group using Account B (Publisher)
- **Maintains** message threading (replies chain) between source and target groups
- Achieves **<60 second latency** from source post to target post

**Core Constraint:** Two separate Telegram user accounts work in parallel via MTProto Client API (Telethon), NOT Bot API.

---

## 2. ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SYSTEM ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────┘

Account A (Reader)                  Core Logic                Account B (Publisher)
Telethon Client 1               PostgreSQL + Redis            Telethon Client 2
     ↓                              ↓                              ↑
Listen to                      process_signal()              Send to
SOURCE_GROUP_ID              translate_text()            TARGET_GROUP_ID
                             handle_replies()
                             map_message_ids()
                                  
Events received:             Pipeline:
- new_message                1. Parse signal (#Идея)
- message_edited            2. Download media
- reply detected            3. Gemini: translate + OCR (parallel)
     ↓                       4. Cache translations
Async queue                  5. Publish to target group
(asyncio.Queue)              6. Store mapping in DB
                             7. Handle replies with threading
```

---

## 3. DETAILED REQUIREMENTS

### 3.1 Signal Detection & Parsing

**Trigger:** Message text contains `#Идея` (exact substring match, case-sensitive).

**Data to extract from source message:**
- Full message text (preserve formatting, emojis)
- All attached media (typically 1 TradingView chart screenshot)
- Message ID (for reply chain mapping)
- Sender ID (track author)
- Timestamp

**Structured field extraction (regex parsing):**
```
Pair:       r'([A-Z][A-Z0-9]*\/[A-Z][A-Z0-9]*)'     # e.g., BTC/USDT, XION/USDT
Timeframe:  r'(\d+\s*[мм][и]?[н]?|1[Hh]|4[Hh]|[Dd]|[Ww])'  # 15мин, 1H, 4H, D, W
Direction:  r'\b(LONG|SHORT)\b'                      # case-insensitive
Entry:      r'[Вв]ход[а]?:?\s*(\d+\.?\d*[-–]\d+\.?\d*)'
TP1:        r'TP1:?\s*\$?(\d+\.?\d*)'
TP2:        r'TP2:?\s*\$?(\d+\.?\d*)'
TP3:        r'TP3:?\s*\$?(\d+\.?\d*)'
SL:         r'(?:SL|Стоп):?\s*\$?(\d+\.?\d*)'
Risk:       r'[Рр]иск:?\s*(\d+)%?'
```

**Do NOT fail if structured fields are missing.** Simply mark them as NULL in DB.

### 3.2 Translation & OCR Requirements

**Text Translation:**
- Language: Russian → English
- **CRITICAL:** Preserve trading terminology exactly:
  - `TP1, TP2, TP3, SL, LONG, SHORT` — **DO NOT TRANSLATE**
  - Numbers, currency symbols (`$`, `€`), tickers — **PRESERVE EXACTLY**
  - Emojis — **PRESERVE**
  - Line breaks and text structure — **PRESERVE**

**Image OCR:**
- If message has attachments (photos), download and save locally
- Send to Gemini Vision API with prompt: *"Extract all visible text from this trading chart image. Preserve numbers, pairs (e.g., BTC/USDT), and technical terms. Translate any descriptive text to English. Return in format: ORIGINAL: [text]\nTRANSLATED: [english]"*
- If OCR finds no text or fails, proceed without image text (attach original image anyway)

**API Choice:** Use **Google Gemini 2.0 Flash** (or 1.5 Pro if Flash unavailable).

**Timeout & Fallback:**
- Gemini timeout: 30 seconds max per request
- If Gemini times out or errors → fallback to **Google Translate API** (free tier acceptable)
- If both fail → log error, post signal without translation (status: `ERROR_TRANSLATION_FAILED`)

### 3.3 Message Threading (Reply Handling)

**Detection:**
When Telethon receives `new_message` event, check `event.message.is_reply`:
- If `True` → extract `event.message.reply_to_msg_id`
- Query DB: find record in `signals` table where `source_message_id == reply_to_msg_id`
- **If found:** This is an update to an existing signal → proceed to step 3.3.2
- **If NOT found:** Ignore (noise in chat)

**Handling Reply on Existing Signal:**
1. Fetch parent signal from DB (get `target_message_id`)
2. Parse and translate reply text + OCR (same as original signal)
3. **Post as reply:** Use Telethon's `client_target.send_message(..., reply_to=target_message_id, ...)`
4. Store in `signal_updates` table with link to parent `signal_id`

**Important:** Maintain clean reply chains. Each reply in target group must reference the correct parent message.

### 3.4 Database Schema

**Table: `signals`**
```sql
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    
    -- Source group tracking
    source_chat_id BIGINT NOT NULL,          -- SOURCE_GROUP_ID
    source_message_id BIGINT NOT NULL,       -- Unique per group
    source_user_id BIGINT NOT NULL,          -- Author ID
    
    -- Target group tracking
    target_chat_id BIGINT,                   -- TARGET_GROUP_ID
    target_message_id BIGINT,                -- Populated after posting
    
    -- Extracted signal fields (nullable)
    pair VARCHAR(20),                        -- e.g., "BTC/USDT"
    direction VARCHAR(10),                   -- "LONG" or "SHORT"
    timeframe VARCHAR(20),                   -- e.g., "15мин", "1H"
    entry_range VARCHAR(50),                 -- e.g., "0.98-0.9283"
    tp1 NUMERIC(20,10),
    tp2 NUMERIC(20,10),
    tp3 NUMERIC(20,10),
    sl NUMERIC(20,10),
    risk_percent FLOAT,
    
    -- Content
    original_text TEXT NOT NULL,             -- Full Russian text
    translated_text TEXT,                    -- Full English translation
    image_source_url TEXT,                   -- Original image URL (from Telegram)
    image_local_path TEXT,                   -- Local path after download
    image_ocr_text TEXT,                     -- Extracted text from image
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(30) DEFAULT 'PENDING',
    -- Status values: PENDING, PROCESSING, POSTED, ERROR_TRANSLATION_FAILED, 
    --                ERROR_POSTING_FAILED, ERROR_OCR_FAILED
    error_message TEXT,
    
    CONSTRAINT unique_source_msg UNIQUE (source_chat_id, source_message_id),
    CONSTRAINT check_status CHECK (status IN ('PENDING', 'PROCESSING', 'POSTED', 
                                              'ERROR_TRANSLATION_FAILED', 
                                              'ERROR_POSTING_FAILED', 
                                              'ERROR_OCR_FAILED'))
);

CREATE INDEX idx_source_msg ON signals(source_chat_id, source_message_id);
CREATE INDEX idx_target_msg ON signals(target_message_id);
CREATE INDEX idx_status ON signals(status);
```

**Table: `signal_updates`** (for reply tracking)
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
    CONSTRAINT check_status CHECK (status IN ('PENDING', 'PROCESSING', 'POSTED',
                                              'ERROR_TRANSLATION_FAILED',
                                              'ERROR_POSTING_FAILED',
                                              'ERROR_OCR_FAILED'))
);

CREATE INDEX idx_signal_updates_parent ON signal_updates(signal_id);
CREATE INDEX idx_source_reply ON signal_updates(source_chat_id, source_message_id);
```

**Table: `translation_cache`** (optional, but recommended)
```sql
CREATE TABLE translation_cache (
    id SERIAL PRIMARY KEY,
    source_text_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA256 of source_text
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    language_pair VARCHAR(10) DEFAULT 'ru_en',
    model VARCHAR(50),                             -- 'gemini', 'google_translate'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    usage_count INT DEFAULT 1
);

CREATE INDEX idx_source_hash ON translation_cache(source_text_hash);
```

---

## 4. TECHNICAL STACK

| Component | Technology | Reason |
| --- | --- | --- |
| **Language** | Python 3.11+ | Async support (asyncio), fast dev cycle |
| **Telegram** | **Telethon 1.36+** | MTProto Client API for user accounts |
| **Translation/OCR** | Google Gemini API (2.0 Flash) | Best quality/speed ratio, built-in OCR |
| **Fallback Translation** | Google Translate API (free tier OK) | Fast, handles <1000 char texts |
| **Database** | PostgreSQL 15+ | ACID, async driver (asyncpg) |
| **Cache** | Redis 7+ (optional) | Session persistence, translation cache |
| **HTTP Client** | aiohttp | Async HTTP for API calls |
| **Task Queue** | asyncio.Queue (built-in) | No external queue needed for <100 signals/day |
| **Containerization** | Docker + Docker Compose | Single command deployment |
| **Logging** | Python logging + structlog | Structured JSON logs |

---

## 5. CONFIGURATION (.env)

```ini
# ============ TELEGRAM ACCOUNTS ============

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

# ============ GROUP IDs ============
SOURCE_GROUP_ID=-100123456789      # Starts with -100 for groups
TARGET_GROUP_ID=-100987654321      # Starts with -100 for groups
SOURCE_ALLOWED_USERS=123456789,987654321,555666777  # CSV of user IDs (optional)

# ============ GEMINI API ============
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.0-flash      # or gemini-1.5-pro

# ============ GOOGLE TRANSLATE (Fallback) ============
GOOGLE_TRANSLATE_API_KEY=...       # Optional, only if using paid tier

# ============ DATABASE ============
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=signal_bot
POSTGRES_HOST=db
POSTGRES_PORT=5432

SQLALCHEMY_ECHO=False              # Set to True for SQL debug logs

# ============ REDIS (Optional) ============
REDIS_URL=redis://redis:6379/0

# ============ APPLICATION ============
LOG_LEVEL=INFO                     # DEBUG, INFO, WARNING, ERROR
ENVIRONMENT=production             # development, staging, production
MAX_RETRIES=3
TIMEOUT_GEMINI_SEC=30
TIMEOUT_TELEGRAM_SEC=15

# ============ MEDIA ============
MEDIA_DOWNLOAD_DIR=/tmp/signals    # Local directory to store downloaded images
MAX_IMAGE_SIZE_MB=50               # Max file size to process
```

---

## 6. EXECUTION FLOW (DETAILED PSEUDOCODE)

### 6.1 Initialization Phase

```python
# === STARTUP ===
async def main():
    # 1. Load config from .env
    config = load_dotenv()
    
    # 2. Initialize PostgreSQL connection pool
    await init_db(config)
    
    # 3. Initialize Reader Client (Account A)
    client_reader = TelegramClient(
        session=config.READER_SESSION_FILE,
        api_id=config.READER_API_ID,
        api_hash=config.READER_API_HASH
    )
    await client_reader.start(phone=config.READER_PHONE)
    
    # 4. Initialize Publisher Client (Account B)
    client_publisher = TelegramClient(
        session=config.PUBLISHER_SESSION_FILE,
        api_id=config.PUBLISHER_API_ID,
        api_hash=config.PUBLISHER_API_HASH
    )
    await client_publisher.start(phone=config.PUBLISHER_PHONE)
    
    # 5. Verify both clients have access
    try:
        source_entity = await client_reader.get_entity(config.SOURCE_GROUP_ID)
        target_entity = await client_publisher.get_entity(config.TARGET_GROUP_ID)
        logger.info(f"Reader has access to: {source_entity.title}")
        logger.info(f"Publisher has access to: {target_entity.title}")
    except Exception as e:
        logger.error(f"Access verification failed: {e}")
        raise
    
    # 6. Register event handlers
    register_handlers(client_reader)
    
    # 7. Keep clients alive
    await client_reader.run_until_disconnected()
    await client_publisher.run_until_disconnected()
```

### 6.2 Event Listener (Reader Client)

```python
# === READER CLIENT LISTENER ===
@client_reader.on(events.NewMessage(chats=[config.SOURCE_GROUP_ID]))
async def on_new_message(event):
    """
    Triggered when ANY message appears in SOURCE_GROUP_ID.
    """
    try:
        message = event.message
        
        # Skip if not a signal
        if '#Идея' not in (message.text or ''):
            return  # Silently ignore
        
        # Check if it's a reply (update to existing signal)
        if message.is_reply:
            asyncio.create_task(
                handle_signal_update(message, event)
            )
            return
        
        # Otherwise, it's a new signal
        if message.sender:
            sender_id = message.sender.id
            # Optional: check if sender is in ALLOWED_USERS
            allowed = config.SOURCE_ALLOWED_USERS.split(',')
            if allowed and str(sender_id) not in allowed:
                logger.warning(f"Signal from unauthorized user {sender_id}")
                return
        
        # Create task for processing (don't block listener)
        asyncio.create_task(
            handle_new_signal(message, event)
        )
        
    except Exception as e:
        logger.error(f"Error in listener: {e}", exc_info=True)
```

### 6.3 New Signal Handler

```python
# === NEW SIGNAL HANDLER ===
async def handle_new_signal(message, event):
    """
    Process a new #Идея signal from start to finish.
    """
    signal_id = None
    
    try:
        # 1. Create initial DB record (PENDING status)
        signal_data = {
            'source_chat_id': message.chat_id,
            'source_message_id': message.id,
            'source_user_id': message.sender_id if message.sender else None,
            'original_text': message.text,
            'status': 'PENDING',
            'created_at': message.date
        }
        signal_id = await db_insert_signal(signal_data)
        logger.info(f"Created signal record {signal_id} from msg {message.id}")
        
        # 2. Update status to PROCESSING
        await db_update_signal(signal_id, {'status': 'PROCESSING'})
        
        # 3. Extract structured fields (regex parsing)
        parsed_fields = parse_trading_signal(message.text)
        await db_update_signal(signal_id, parsed_fields)
        
        # 4. Download and process media (if present)
        media_info = None
        if message.photo or message.document:
            media_info = await download_and_process_media(
                client_reader, message, signal_id
            )
        
        # 5. Translate text + OCR in parallel
        translation_result = await asyncio.gather(
            translate_text_with_fallback(message.text),
            translate_image_ocr(media_info['local_path']) 
                if media_info else asyncio.sleep(0),
            return_exceptions=True
        )
        
        translated_text = translation_result[0]
        image_ocr = translation_result[1] if len(translation_result) > 1 else None
        
        if isinstance(translated_text, Exception):
            logger.error(f"Translation failed: {translated_text}")
            translated_text = message.text  # Fallback to original
        
        # 6. Build final message for posting
        final_message = build_final_message(
            translated_text,
            image_ocr,
            parsed_fields
        )
        
        # 7. Post to target group
        posted_msg = await client_publisher.send_message(
            entity=config.TARGET_GROUP_ID,
            message=final_message,
            file=media_info['local_path'] if media_info else None
        )
        target_msg_id = posted_msg.id
        
        logger.info(f"Posted signal to target group: {target_msg_id}")
        
        # 8. Update DB with posting info
        await db_update_signal(signal_id, {
            'target_message_id': target_msg_id,
            'target_chat_id': config.TARGET_GROUP_ID,
            'translated_text': translated_text,
            'image_ocr_text': image_ocr,
            'status': 'POSTED',
            'processed_at': datetime.utcnow()
        })
        
        # 9. Cleanup downloaded media
        if media_info:
            os.remove(media_info['local_path'])
        
    except Exception as e:
        logger.error(f"Error processing signal {signal_id}: {e}", exc_info=True)
        if signal_id:
            await db_update_signal(signal_id, {
                'status': 'ERROR_POSTING_FAILED',
                'error_message': str(e)
            })
```

### 6.4 Signal Update (Reply) Handler

```python
# === SIGNAL UPDATE HANDLER (for replies) ===
async def handle_signal_update(message, event):
    """
    Process a reply to an existing #Идея signal.
    """
    update_id = None
    
    try:
        # 1. Find parent signal in DB
        parent_msg_id = message.reply_to_msg_id
        parent_signal = await db_find_signal_by_source_msg(
            config.SOURCE_GROUP_ID,
            parent_msg_id
        )
        
        if not parent_signal:
            logger.warning(f"Reply to unknown signal {parent_msg_id}")
            return  # Ignore orphan replies
        
        # 2. Create update record (linked to parent signal)
        update_data = {
            'signal_id': parent_signal['id'],
            'source_chat_id': message.chat_id,
            'source_message_id': message.id,
            'source_user_id': message.sender_id if message.sender else None,
            'original_text': message.text,
            'status': 'PROCESSING',
            'created_at': message.date
        }
        update_id = await db_insert_signal_update(update_data)
        logger.info(f"Created update record {update_id} for signal {parent_signal['id']}")
        
        # 3. Process similarly to new signal
        media_info = None
        if message.photo or message.document:
            media_info = await download_and_process_media(
                client_reader, message, update_id, is_update=True
            )
        
        # 4. Translate
        translated_text = await translate_text_with_fallback(message.text)
        image_ocr = (
            await translate_image_ocr(media_info['local_path'])
            if media_info else None
        )
        
        # 5. Build final message
        final_message = build_final_message(
            translated_text,
            image_ocr,
            {}  # No structured fields for updates
        )
        
        # 6. Post as reply to target signal
        posted_msg = await client_publisher.send_message(
            entity=config.TARGET_GROUP_ID,
            message=final_message,
            file=media_info['local_path'] if media_info else None,
            reply_to=parent_signal['target_message_id']  # KEY: reply to mapped target msg
        )
        
        target_update_msg_id = posted_msg.id
        logger.info(f"Posted update to target: {target_update_msg_id}")
        
        # 7. Update DB
        await db_update_signal_update(update_id, {
            'target_message_id': target_update_msg_id,
            'target_chat_id': config.TARGET_GROUP_ID,
            'translated_text': translated_text,
            'image_ocr_text': image_ocr,
            'status': 'POSTED',
            'processed_at': datetime.utcnow()
        })
        
        # 8. Cleanup
        if media_info:
            os.remove(media_info['local_path'])
        
    except Exception as e:
        logger.error(f"Error processing update {update_id}: {e}", exc_info=True)
        if update_id:
            await db_update_signal_update(update_id, {
                'status': 'ERROR_POSTING_FAILED',
                'error_message': str(e)
            })
```

### 6.5 Helper Functions

```python
# === TRANSLATION WITH FALLBACK ===
async def translate_text_with_fallback(text: str, timeout: int = 30) -> str:
    """
    Try Gemini first, fallback to Google Translate.
    """
    try:
        # Try Gemini with timeout
        result = await asyncio.wait_for(
            gemini_translate(text),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        logger.warning(f"Gemini timeout, falling back to Google Translate")
        return await google_translate(text)
    except Exception as e:
        logger.warning(f"Gemini error: {e}, falling back")
        return await google_translate(text)

async def gemini_translate(text: str) -> str:
    """
    Call Gemini API for translation.
    """
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

async def google_translate(text: str) -> str:
    """
    Fallback: Google Translate (free or paid).
    """
    from google.cloud import translate_v2
    
    client = translate_v2.Client()
    result = client.translate_text(text, target_language='en')
    # Post-process: restore trading terms if accidentally changed
    result_text = result['translatedText']
    result_text = restore_trading_terms(result_text)
    return result_text

async def translate_image_ocr(image_path: str) -> str:
    """
    Extract text from image and translate it.
    """
    import google.generativeai as genai
    
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    
    # Upload file to Gemini
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
    
    # Parse response
    text = response.text
    lines = text.split('\n')
    
    extracted = None
    translated = None
    for line in lines:
        if line.startswith('EXTRACTED:'):
            extracted = line.replace('EXTRACTED:', '').strip()
        elif line.startswith('TRANSLATED:'):
            translated = line.replace('TRANSLATED:', '').strip()
    
    if extracted == '(none)':
        return None
    
    return f"[On chart]: {translated}" if translated else None

async def download_and_process_media(client, message, entity_id, is_update=False):
    """
    Download media from Telegram message.
    """
    import os
    
    if not message.photo and not message.document:
        return None
    
    # Create media directory
    os.makedirs(config.MEDIA_DOWNLOAD_DIR, exist_ok=True)
    
    # Download
    file_path = await message.download_media(
        file=config.MEDIA_DOWNLOAD_DIR
    )
    
    if os.path.getsize(file_path) > config.MAX_IMAGE_SIZE_MB * 1024 * 1024:
        logger.warning(f"Image too large: {file_path}")
        os.remove(file_path)
        return None
    
    # Save metadata
    file_record = {
        'local_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'downloaded_at': datetime.utcnow()
    }
    
    if is_update:
        await db.execute(
            f"UPDATE signal_updates SET image_local_path = %s WHERE id = %s",
            (file_path, entity_id)
        )
    else:
        await db.execute(
            f"UPDATE signals SET image_local_path = %s WHERE id = %s",
            (file_path, entity_id)
        )
    
    return file_record

def parse_trading_signal(text: str) -> dict:
    """
    Extract structured trading fields from text.
    All fields are optional.
    """
    import re
    
    fields = {}
    
    # Pair
    match = re.search(r'\b([A-Z][A-Z0-9]*\/[A-Z][A-Z0-9]*)\b', text)
    fields['pair'] = match.group(1) if match else None
    
    # Direction
    match = re.search(r'\b(LONG|SHORT)\b', text, re.IGNORECASE)
    fields['direction'] = match.group(1).upper() if match else None
    
    # Timeframe
    match = re.search(r'(\d+\s*[мм][и]?[н]?|1[Hh]|4[Hh]|[Dd]|[Ww])', text)
    fields['timeframe'] = match.group(1).strip() if match else None
    
    # Entry
    match = re.search(r'[Вв]ход[а]?:?\s*(\d+\.?\d*[-–]\d+\.?\d*)', text)
    fields['entry_range'] = match.group(1) if match else None
    
    # TPs and SL
    for i, label in enumerate(['TP1', 'TP2', 'TP3', 'SL'], 1):
        match = re.search(rf'{label}:?\s*\$?(\d+\.?\d*)', text)
        if match:
            if label.startswith('TP'):
                fields[f'tp{i}'] = float(match.group(1))
            else:
                fields['sl'] = float(match.group(1))
    
    # Risk
    match = re.search(r'[Рр]иск:?\s*(\d+)%?', text)
    fields['risk_percent'] = float(match.group(1)) if match else None
    
    return fields

def build_final_message(translated_text: str, image_ocr: str, parsed_fields: dict) -> str:
    """
    Construct final English message to post.
    """
    parts = [translated_text]
    
    if image_ocr:
        parts.append(f"\n\n_Chart OCR:_\n{image_ocr}")
    
    return '\n'.join(parts)

def restore_trading_terms(text: str) -> str:
    """
    Post-process translation to ensure trading terms are preserved.
    """
    replacements = {
        'tp 1': 'TP1',
        'tp 2': 'TP2',
        'tp 3': 'TP3',
        'sl ': 'SL ',
        'long': 'LONG',
        'short': 'SHORT',
    }
    
    for original, replacement in replacements.items():
        text = text.replace(original.lower(), replacement)
    
    return text
```

---

## 7. ERROR HANDLING & RESILIENCE

### Retry Strategy
- **Telegram errors:** Retry up to 3 times with exponential backoff (1s, 2s, 4s)
- **API errors (Gemini):** Fallback to Google Translate (already implemented)
- **DB errors:** Log and skip signal (mark as ERROR_*), don't crash service

### Graceful Degradation
- **If translation fails:** Post original Russian text with status note
- **If image OCR fails:** Post without OCR text
- **If posting fails:** Mark in DB as ERROR, alert logs, do NOT re-post later (prevent duplicates)

### Health Checks
- Every 5 minutes: Verify DB connection
- Every 10 minutes: Verify both Telethon clients are connected
- If client disconnects: Attempt reconnect with exponential backoff

---

## 8. PERFORMANCE & LATENCY

**Target: <60 seconds from source post to target post**

Typical breakdown:
- Event detection: <100ms
- Parse + regex: <200ms
- Media download: 500ms – 2s
- Gemini API (parallel): 3–8s
- Posting: 500ms – 1s
- **Total: ~6–12 seconds** ✅

---

## 9. DEPLOYMENT

### Docker Compose Setup

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: signal_bot
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build: .
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - READER_API_ID=${READER_API_ID}
      - READER_API_HASH=${READER_API_HASH}
      - READER_PHONE=${READER_PHONE}
      - PUBLISHER_API_ID=${PUBLISHER_API_ID}
      - PUBLISHER_API_HASH=${PUBLISHER_API_HASH}
      - PUBLISHER_PHONE=${PUBLISHER_PHONE}
      - SOURCE_GROUP_ID=${SOURCE_GROUP_ID}
      - TARGET_GROUP_ID=${TARGET_GROUP_ID}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    volumes:
      - ./logs:/app/logs
      - /tmp/signals:/tmp/signals
    ports:
      - "8000:8000"
    restart: unless-stopped

volumes:
  postgres_data:
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY migrations/ ./migrations/

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.main"]
```

### requirements.txt

```
telethon==1.36.0
google-generativeai==0.8.0
aiohttp==3.10.0
psycopg2-binary==2.9.9
asyncpg==0.30.0
sqlalchemy==2.0.23
python-dotenv==1.0.0
structlog==24.1.0
pydantic==2.5.0
```

---

## 10. PROJECT STRUCTURE

```
telegram-signal-bot/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point, initialize clients
│   ├── config.py                  # Config loading from .env
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py          # PostgreSQL connection pool
│   │   └── queries.py             # DB helper functions (insert, update, find)
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── signal_handler.py      # handle_new_signal()
│   │   └── update_handler.py      # handle_signal_update()
│   ├── translators/
│   │   ├── __init__.py
│   │   ├── gemini.py              # gemini_translate()
│   │   ├── google.py              # google_translate()
│   │   └── fallback.py            # translate_text_with_fallback()
│   ├── ocr/
│   │   ├── __init__.py
│   │   └── gemini_ocr.py          # translate_image_ocr()
│   ├── media/
│   │   ├── __init__.py
│   │   └── downloader.py          # download_and_process_media()
│   ├── parsers/
│   │   ├── __init__.py
│   │   └── signal_parser.py       # parse_trading_signal()
│   ├── formatters/
│   │   ├── __init__.py
│   │   └── message.py             # build_final_message(), restore_trading_terms()
│   ├── utils/
│   │   ├── __init__.py
│   │   └── logger.py              # Structured logging setup
│   └── telethon_setup.py          # Telethon client initialization
├── migrations/
│   └── 001_init_schema.sql        # DB schema (create tables)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## 11. TESTING CHECKLIST

Before going to production, verify:

- [ ] Reader client connects and can read SOURCE_GROUP
- [ ] Publisher client connects and can write to TARGET_GROUP
- [ ] Signal detection: Post message with `#Идея` → appears in target within 60s
- [ ] Reply handling: Reply to signal in source → appears as reply in target
- [ ] Translation quality: Russian text translates correctly with terms preserved
- [ ] Image OCR: Chart image text extracted and translated
- [ ] Fallback: Disable Gemini key, verify Google Translate fallback works
- [ ] Media handling: Photos are downloaded and re-posted
- [ ] DB: Check `signals` and `signal_updates` tables populate correctly
- [ ] Logs: Verify structured JSON logs appear
- [ ] Restart: Docker container restarts successfully after crash

---

## 12. MONITORING & LOGGING

**Log every:**
- Signal received (source_msg_id, pair, direction)
- Translation start/end (duration)
- API calls (Gemini, Google, Telegram)
- DB operations
- Errors with full stack trace

**Metrics to track:**
- avg_latency_seconds (target: <60)
- signals_processed_total
- signals_failed_total
- translation_fallback_count
- image_ocr_success_rate

---

## 13. KNOWN LIMITATIONS & FUTURE IMPROVEMENTS

**Current Limitations:**
- Supports only one source and one target group (could extend to multiple)
- No manual intervention UI
- Session files stored locally (could use encrypted remote storage)

**Future Enhancements:**
- Web dashboard to view signal history
- Admin panel to retry failed translations
- Support for multiple source/target pairs
- Telegram webhook mode (instead of listener)
- PostgreSQL change streams for real-time updates

---

## 14. SUPPORT & CONTACTS

This is a self-contained service. For issues:
1. Check logs: `docker-compose logs app`
2. Verify DB: `docker-compose exec db psql -U postgres signal_bot`
3. Check Telethon session files: Do sessions exist? Are they valid?
4. Restart: `docker-compose restart app`

No external support required once deployed.