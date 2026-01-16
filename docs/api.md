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
| `src/ocr/gemini_ocr.py` | Main image processing entry point (orchestrates vision + editing) | `vision`, `image_editing` |
| `src/ocr/image_editor.py` | Two-stage pipeline: vision extraction + image editing | `vision`, `image_editing`, `PIL` |
| `src/vision/base.py` | Abstract base class and data models for vision providers | `PIL`, `abc` |
| `src/vision/fallback.py` | Multi-provider fallback chain for vision operations | `vision.base` |
| `src/image_editing/base.py` | Abstract base class and data models for image editors | `PIL`, `abc` |
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

### 2.3 Image Processing (OCR + Editing)

#### `src/ocr/gemini_ocr.py`

```python
async def process_image(image_path: str) -> Optional[str]:
    """
    Process image: edit Russian text to English using multi-provider vision + image editing.

    This is the main entry point for image processing. It orchestrates a two-stage pipeline:
    - Stage 1: Vision provider extracts and translates text (with fallback chain)
    - Stage 2: Image editor generates new image with English text

    Replaces the old OCR-only approach. Now we regenerate the image with translated text
    instead of just extracting it.

    Args:
        image_path: Path to the original image

    Returns:
        Path to edited image with English text, or None if editing failed
        (caller should use original image as fallback)

    Raises:
        Does not raise. Returns None on errors.

    Side Effects:
        - Creates edited image file with "_edited" suffix
        - Original file is preserved

    Example:
        >>> edited_path = await process_image("/tmp/signals/chart123.jpg")
        >>> if edited_path:
        ...     print(f"Edited image: {edited_path}")
        ...     # Returns: "/tmp/signals/chart123_edited.jpg"
        ... else:
        ...     print("Editing failed, use original")
    """
```

---

#### `src/ocr/image_editor.py`

```python
async def edit_image_text(image_path: str, output_path: str) -> Optional[str]:
    """
    Edit image: translate Russian text to English using vision + image editing.

    Two-stage pipeline:
    - Stage 1: Vision provider extracts and translates text (with fallback chain)
    - Stage 2: Image editor generates new image with translations

    Args:
        image_path: Path to original image
        output_path: Path to save edited image

    Returns:
        Path to edited image, or None if editing failed

    Raises:
        Does not raise. Returns None on errors.

    Side Effects:
        - Validates image file (security check)
        - Upscales small images (<1024px) for better OCR accuracy
        - Saves edited image to output_path

    Example:
        >>> edited = await edit_image_text(
        ...     "/tmp/chart.jpg",
        ...     "/tmp/chart_edited.jpg"
        ... )
        >>> if edited:
        ...     print("Success!")
    """

async def extract_text_from_image(image: Image.Image) -> List[Dict[str, str]]:
    """
    Extract and translate text from image using vision fallback chain.

    Uses multi-provider vision system (Gemini, OpenAI, etc.) with automatic
    fallback if primary provider fails.

    Args:
        image: PIL Image object

    Returns:
        List of dicts with 'russian' and 'english' keys
        Example: [{'russian': 'Вход', 'english': 'Entry'}]

    Raises:
        Does not raise. Returns empty list on errors.

    Example:
        >>> from PIL import Image
        >>> img = Image.open("/tmp/chart.jpg")
        >>> translations = await extract_text_from_image(img)
        >>> for t in translations:
        ...     print(f"{t['russian']} -> {t['english']}")
    """
```

---

### 2.4 Vision Providers

#### `src/vision/base.py`

```python
class VisionProvider(ABC):
    """
    Abstract base class for vision/OCR providers.

    All vision providers (Gemini, OpenAI, Tesseract) must implement this interface.
    """

    @abstractmethod
    async def extract_text(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """
        Extract and optionally translate text from an image (async).

        Args:
            image: PIL Image object to extract text from
            prompt: Optional custom prompt for the vision model

        Returns:
            VisionResult containing:
                - extractions: List[TextExtraction] with original/translated text
                - provider_name: Name of provider used
                - latency_ms: Processing time
                - raw_response: Optional raw API response

        Raises:
            VisionProviderError: If extraction fails

        Example:
            >>> from PIL import Image
            >>> provider = VisionProviderFactory.get_provider('gemini')
            >>> img = Image.open("chart.jpg")
            >>> result = await provider.extract_text(img)
            >>> print(result.extractions[0].translated)
            "Entry: 0.98-0.9283"
        """
        pass

    def extract_text_sync(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """
        Synchronous wrapper for extract_text.

        Runs async extract_text in a new event loop. Useful for sync contexts.

        Args:
            image: PIL Image object to extract text from
            prompt: Optional custom prompt for the vision model

        Returns:
            VisionResult (same as async version)

        Raises:
            VisionProviderError: If extraction fails
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of this vision provider (e.g., 'gemini', 'openai')."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available and configured."""
        pass
```

---

#### `src/vision/base.py` - Data Classes

```python
@dataclass
class TextExtraction:
    """
    Represents a single text extraction from an image.

    Attributes:
        original: The original text extracted from the image
        translated: The translated version of the text
        confidence: Confidence score (0.0 to 1.0), defaults to 1.0
    """
    original: str
    translated: str
    confidence: float = 1.0

@dataclass
class VisionResult:
    """
    Result from a vision provider's text extraction operation.

    Attributes:
        extractions: List[TextExtraction] with original/translated text pairs
        provider_name: Name of the vision provider that generated this result
        raw_response: Optional raw response from provider API (for debugging)
        latency_ms: Time taken for extraction in milliseconds
    """
    extractions: List[TextExtraction]
    provider_name: str
    raw_response: Optional[str] = None
    latency_ms: float = 0.0

    @property
    def has_text(self) -> bool:
        """Check if any text was extracted."""
        pass

    @property
    def combined_translated(self) -> str:
        """Get all translated texts combined with newlines."""
        pass

    @property
    def average_confidence(self) -> float:
        """Calculate average confidence across all extractions."""
        pass
```

---

#### `src/vision/fallback.py`

```python
class FallbackChain:
    """
    Orchestrates fallback between multiple vision providers.

    Tries providers in order until one succeeds. Supports retries per provider
    and timeout configuration.
    """

    def __init__(
        self,
        providers: List[VisionProvider],
        timeout_sec: float = 30.0,
        max_retries: int = 1
    ):
        """
        Initialize FallbackChain.

        Args:
            providers: List of vision providers to try in order
            timeout_sec: Timeout for each provider attempt (default: 30s)
            max_retries: Max retries per provider before trying next (default: 1)
        """
        pass

    async def extract_text(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """
        Try providers in order until one succeeds.

        Workflow:
        1. For each provider in chain:
           a. Try max_retries + 1 times
           b. If timeout → log warning, try next
           c. If error → log warning, try next
           d. If success → return result
        2. If all providers fail → raise VisionProviderError

        Args:
            image: PIL Image to process
            prompt: Optional custom prompt

        Returns:
            VisionResult from first successful provider

        Raises:
            VisionProviderError: If all providers fail

        Example:
            >>> chain = FallbackChain(
            ...     [gemini_provider, openai_provider],
            ...     timeout_sec=30,
            ...     max_retries=2
            ... )
            >>> result = await chain.extract_text(image)
            >>> print(f"Provider used: {result.provider_name}")
        """
        pass
```

---

### 2.5 Image Editors

#### `src/image_editing/base.py`

```python
class ImageEditor(ABC):
    """
    Abstract base class for image editors.

    All image editor implementations (Gemini, Imagen, PIL-based) must extend this class.
    """

    @abstractmethod
    def edit_image(
        self,
        image_path: str,
        translations: Dict[str, str],
        output_path: Optional[str] = None
    ) -> EditResult:
        """
        Edit an image by replacing text according to translations.

        Synchronous version - runs in thread pool when called from async context.

        Args:
            image_path: Path to the input image file
            translations: Dictionary mapping Russian text to English text
                Example: {'Вход': 'Entry', 'Стоп': 'Stop Loss'}
            output_path: Optional path to save the edited image

        Returns:
            EditResult with:
                - success: bool (True if editing succeeded)
                - edited_image: PIL Image object (or None if failed)
                - error: Error message if failed
                - method: Name of editing method/backend used
                - metadata: Additional metadata

        Example:
            >>> editor = ImageEditorFactory.get_editor('gemini')
            >>> translations = {'Вход': 'Entry', 'TP1': 'TP1'}
            >>> result = editor.edit_image(
            ...     "/tmp/chart.jpg",
            ...     translations,
            ...     "/tmp/chart_edited.jpg"
            ... )
            >>> if result.success:
            ...     print(f"Edited with {result.method}")
        """
        pass

    @abstractmethod
    async def edit_image_async(
        self,
        image_path: str,
        translations: Dict[str, str],
        output_path: Optional[str] = None
    ) -> EditResult:
        """
        Async version of edit_image.

        Args:
            image_path: Path to the input image file
            translations: Dictionary mapping original text to replacement text
            output_path: Optional path to save the edited image

        Returns:
            EditResult (same as sync version)
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of this editor (e.g., 'gemini', 'pil')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this editor is available for use."""
        pass
```

---

#### `src/image_editing/base.py` - Data Classes

```python
@dataclass
class EditResult:
    """
    Result of an image editing operation.

    Attributes:
        success: Whether the edit operation succeeded
        edited_image: The edited PIL Image (None if failed)
        error: Error message if operation failed
        method: Name of the editing method/backend used
        metadata: Additional metadata about the operation
    """
    success: bool
    edited_image: Optional[Image.Image] = None
    error: Optional[str] = None
    method: str = "unknown"
    metadata: Optional[Dict] = None
```

---

### 2.6 Media

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

### 2.7 Parsers

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

### 2.8 Formatters

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

### 2.9 Database Queries

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

### 2.10 Telethon Setup

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