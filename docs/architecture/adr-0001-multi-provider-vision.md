# ADR-0001: Multi-Provider Vision Architecture with LangChain

**Status**: Proposed

**Date**: 2025-12-12

**Deciders**: Development Team

---

## Context

The telegram-signals-parsing project currently uses direct Google Gemini SDK for OCR text extraction from trading chart images. The existing hybrid pipeline achieves 95%+ reliability:

1. **Stage 1**: Gemini OCR extracts Russian text and provides English translations
2. **Stage 2**: PaddleOCR + PIL performs deterministic text replacement on the image

**Current limitations:**
- Single provider dependency (Gemini) creates a single point of failure
- No fallback mechanism if Gemini API is unavailable or rate-limited
- Vendor lock-in with direct SDK usage
- Cannot easily switch providers or compare performance

**User requirements:**
1. Configure vision provider via environment variable (`VISION_PROVIDER=gemini/openai/anthropic`)
2. Use LangChain for unified interface across providers
3. Keep existing PaddleOCR + PIL pipeline for image editing (preserves chart grids)
4. Support fallback chain: primary -> secondary -> tertiary provider

**Research findings:**
- LangChain supports unified `HumanMessage` format with content blocks for vision
- All 3 providers (OpenAI GPT-4o, Gemini 2.5 Flash, Claude 3.5/4) support image-to-text OCR
- Image generation/editing is NOT unified in LangChain (requires direct SDKs)
- For trading charts, hybrid deterministic pipeline remains the best approach

---

## Decision

Implement a **multi-provider vision architecture** using LangChain with the following design:

### 1. Create `src/vision/` Module

New module structure for provider-agnostic vision operations:

```
src/vision/
|-- __init__.py                 # Public API exports
|-- base.py                     # Abstract VisionProvider interface
|-- factory.py                  # Provider factory with env config
|-- fallback.py                 # Fallback chain orchestrator
|-- providers/
|   |-- __init__.py
|   |-- gemini.py               # LangChain Gemini provider
|   |-- openai.py               # LangChain OpenAI provider
|   |-- anthropic.py            # LangChain Anthropic provider
|-- prompts/
|   |-- __init__.py
|   |-- ocr_extraction.py       # OCR prompt templates
```

### 2. Use LangChain for Unified Interface

LangChain provides a consistent interface for all vision LLMs:

```python
from langchain_core.messages import HumanMessage

# Same message format works for all providers
message = HumanMessage(
    content=[
        {"type": "text", "text": "Extract text from this image..."},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
    ]
)
```

### 3. Keep Existing Image Editing Pipeline

The existing `src/ocr/` pipeline remains unchanged:
- `seamless_replacer.py`: PaddleOCR + PIL for deterministic text replacement
- `image_editor.py`: Orchestrates the hybrid pipeline

Only the OCR extraction step (`extract_text_from_image`) will use the new vision module.

### 4. Implement Fallback Chain

Configurable fallback with exponential backoff:

```
Primary (Gemini) -> Secondary (OpenAI) -> Tertiary (Anthropic)
```

---

## Architecture

### Component Diagram

```
+------------------------------------------------------------------+
|                        src/vision/                                |
+------------------------------------------------------------------+
|                                                                   |
|  +---------------------+     +-----------------------------+      |
|  |    VisionProvider   |     |      VisionProviderFactory  |      |
|  |    (Abstract Base)  |     |                             |      |
|  +---------------------+     |  - get_provider(name)       |      |
|  | + extract_text()    |     |  - get_primary_provider()   |      |
|  | + supports_image()  |     |  - from_env_config()        |      |
|  +----------^----------+     +-----------------------------+      |
|             |                                                     |
|  +----------+------------+------------+                           |
|  |          |            |            |                           |
|  v          v            v            v                           |
| +--------+ +--------+ +--------+ +-------------+                  |
| |Gemini  | |OpenAI  | |Anthropic| |FallbackChain|                 |
| |Provider| |Provider| |Provider | |             |                 |
| +--------+ +--------+ +--------+ | - providers[]|                 |
|  (LangChain wrappers)            | - timeouts{} |                 |
|                                  | - try_next() |                 |
|                                  +-------------+                  |
+------------------------------------------------------------------+
                           |
                           | extract_text()
                           v
+------------------------------------------------------------------+
|                        src/ocr/                                   |
+------------------------------------------------------------------+
|                                                                   |
|  +---------------------+      +---------------------------+       |
|  |    image_editor.py  |----->|   seamless_replacer.py    |       |
|  |                     |      |                           |       |
|  | edit_image_text()   |      | - PaddleOCR detection     |       |
|  |  1. Vision OCR -----|      | - Color extraction        |       |
|  |  2. PaddleOCR match |      | - Font matching           |       |
|  |  3. PIL render      |      | - cv2.inpaint removal     |       |
|  +---------------------+      | - PIL text rendering      |       |
|                               +---------------------------+       |
+------------------------------------------------------------------+
```

### Data Flow

```
[Trading Chart Image]
         |
         v
+------------------+
| VisionProvider   |  <-- LangChain unified interface
| (Gemini/OpenAI/  |      (configurable via VISION_PROVIDER)
|  Anthropic)      |
+------------------+
         |
         | List[{russian: str, english: str}]
         v
+------------------+
| PaddleOCR        |  <-- Detect bounding boxes
| (text detection) |
+------------------+
         |
         | List[{text, bbox, confidence}]
         v
+------------------+
| Translation      |  <-- Match OCR boxes to Vision translations
| Matcher          |
+------------------+
         |
         | List[(bbox, translated_text)]
         v
+------------------+
| PIL Renderer     |  <-- Deterministic text replacement
| + cv2.inpaint    |
+------------------+
         |
         v
[Edited Image with English Text]
```

### Sequence Diagram

```
User Request          VisionFactory        FallbackChain         Provider
     |                     |                    |                    |
     |  extract_text()     |                    |                    |
     |-------------------->|                    |                    |
     |                     |  get_chain()       |                    |
     |                     |------------------->|                    |
     |                     |                    |                    |
     |                     |                    |  try primary       |
     |                     |                    |------------------->|
     |                     |                    |                    |
     |                     |                    |<-- success/fail ---|
     |                     |                    |                    |
     |                     |                    |  [if fail]         |
     |                     |                    |  try secondary     |
     |                     |                    |------------------->|
     |                     |                    |                    |
     |<--------------------|--------------------|--- translations ---|
     |                     |                    |                    |
```

---

## File Structure

```
src/
|-- vision/
|   |-- __init__.py              # Public exports: get_vision_provider, extract_text
|   |-- base.py                  # VisionProvider ABC, VisionResult dataclass
|   |-- factory.py               # VisionProviderFactory, provider registration
|   |-- fallback.py              # FallbackChain with retry logic
|   |-- providers/
|   |   |-- __init__.py          # Provider exports
|   |   |-- gemini.py            # GeminiVisionProvider(VisionProvider)
|   |   |-- openai.py            # OpenAIVisionProvider(VisionProvider)
|   |   |-- anthropic.py         # AnthropicVisionProvider(VisionProvider)
|   |-- prompts/
|   |   |-- __init__.py
|   |   |-- ocr_extraction.py    # OCR_EXTRACTION_PROMPT constant
|-- ocr/
|   |-- __init__.py              # (unchanged)
|   |-- image_editor.py          # MODIFIED: use src.vision instead of direct Gemini
|   |-- seamless_replacer.py     # (unchanged)
|   |-- paddleocr_worker.py      # (unchanged)
|   |-- gemini_ocr.py            # DEPRECATED: replaced by src.vision
|-- config.py                    # ADD: Vision provider settings
```

---

## Interface Definitions

### VisionProvider (Abstract Base Class)

```python
# src/vision/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from PIL import Image

@dataclass
class TextExtraction:
    """Single text extraction result."""
    original: str      # Original text (e.g., Russian)
    translated: str    # Translated text (e.g., English)
    confidence: float = 1.0

@dataclass
class VisionResult:
    """Result from vision provider."""
    extractions: List[TextExtraction]
    provider_name: str
    raw_response: Optional[str] = None
    latency_ms: float = 0.0

class VisionProvider(ABC):
    """Abstract base class for vision providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        pass

    @abstractmethod
    async def extract_text(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """
        Extract and translate text from image.

        Args:
            image: PIL Image to process
            prompt: Optional custom prompt (uses default if None)

        Returns:
            VisionResult with extracted text translations

        Raises:
            VisionProviderError: If extraction fails
        """
        pass

    def extract_text_sync(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """Synchronous wrapper for extract_text."""
        import asyncio
        return asyncio.run(self.extract_text(image, prompt))
```

### VisionProviderFactory

```python
# src/vision/factory.py
from typing import Dict, Optional, Type
from src.vision.base import VisionProvider

class VisionProviderFactory:
    """Factory for creating vision providers from config."""

    _providers: Dict[str, Type[VisionProvider]] = {}
    _instances: Dict[str, VisionProvider] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[VisionProvider]) -> None:
        """Register a provider class."""
        cls._providers[name.lower()] = provider_class

    @classmethod
    def get_provider(cls, name: str) -> VisionProvider:
        """
        Get or create provider instance by name.

        Args:
            name: Provider name (gemini, openai, anthropic)

        Returns:
            VisionProvider instance

        Raises:
            ValueError: If provider not registered or not available
        """
        name_lower = name.lower()

        if name_lower not in cls._instances:
            if name_lower not in cls._providers:
                raise ValueError(f"Unknown provider: {name}")

            provider = cls._providers[name_lower]()
            if not provider.is_available:
                raise ValueError(f"Provider {name} is not available (missing API key?)")

            cls._instances[name_lower] = provider

        return cls._instances[name_lower]

    @classmethod
    def from_env_config(cls) -> VisionProvider:
        """Create provider from VISION_PROVIDER env var."""
        from src.config import config
        return cls.get_provider(config.VISION_PROVIDER)
```

### FallbackChain

```python
# src/vision/fallback.py
from typing import List, Optional
from src.vision.base import VisionProvider, VisionResult, VisionProviderError
from PIL import Image
import structlog

logger = structlog.get_logger(__name__)

class FallbackChain:
    """
    Orchestrates fallback between multiple vision providers.

    Tries providers in order until one succeeds.
    """

    def __init__(
        self,
        providers: List[VisionProvider],
        timeout_sec: float = 30.0,
        max_retries: int = 1
    ):
        self.providers = [p for p in providers if p.is_available]
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries

        if not self.providers:
            raise ValueError("No available providers in fallback chain")

        logger.info(
            "FallbackChain initialized",
            providers=[p.name for p in self.providers]
        )

    async def extract_text(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        """
        Try providers in order until success.

        Args:
            image: PIL Image to process
            prompt: Optional custom prompt

        Returns:
            VisionResult from first successful provider

        Raises:
            VisionProviderError: If all providers fail
        """
        last_error: Optional[Exception] = None

        for provider in self.providers:
            for attempt in range(self.max_retries + 1):
                try:
                    logger.info(
                        "Trying vision provider",
                        provider=provider.name,
                        attempt=attempt + 1
                    )

                    result = await asyncio.wait_for(
                        provider.extract_text(image, prompt),
                        timeout=self.timeout_sec
                    )

                    logger.info(
                        "Vision extraction successful",
                        provider=provider.name,
                        extractions=len(result.extractions),
                        latency_ms=result.latency_ms
                    )

                    return result

                except asyncio.TimeoutError:
                    logger.warning(
                        "Vision provider timeout",
                        provider=provider.name,
                        timeout_sec=self.timeout_sec
                    )
                    last_error = TimeoutError(f"{provider.name} timed out")

                except Exception as e:
                    logger.warning(
                        "Vision provider failed",
                        provider=provider.name,
                        error=str(e)
                    )
                    last_error = e

        raise VisionProviderError(
            f"All providers failed. Last error: {last_error}"
        )
```

### Gemini Provider (Example Implementation)

```python
# src/vision/providers/gemini.py
import base64
import time
from io import BytesIO
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from PIL import Image

from src.config import config
from src.vision.base import VisionProvider, VisionResult, TextExtraction
from src.vision.prompts.ocr_extraction import OCR_EXTRACTION_PROMPT

class GeminiVisionProvider(VisionProvider):
    """Gemini vision provider using LangChain."""

    def __init__(self):
        self._model: Optional[ChatGoogleGenerativeAI] = None

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def is_available(self) -> bool:
        return bool(config.GEMINI_API_KEY)

    def _get_model(self) -> ChatGoogleGenerativeAI:
        if self._model is None:
            self._model = ChatGoogleGenerativeAI(
                model=config.GEMINI_MODEL,
                google_api_key=config.GEMINI_API_KEY,
                temperature=0,
            )
        return self._model

    def _image_to_base64(self, image: Image.Image) -> str:
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=95)
        return base64.b64encode(buffer.getvalue()).decode()

    async def extract_text(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> VisionResult:
        start_time = time.time()

        model = self._get_model()
        base64_image = self._image_to_base64(image)

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt or OCR_EXTRACTION_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                }
            ]
        )

        response = await model.ainvoke([message])
        raw_text = response.content

        # Parse response into TextExtraction objects
        extractions = self._parse_response(raw_text)

        latency_ms = (time.time() - start_time) * 1000

        return VisionResult(
            extractions=extractions,
            provider_name=self.name,
            raw_response=raw_text,
            latency_ms=latency_ms
        )

    def _parse_response(self, raw_text: str) -> List[TextExtraction]:
        """Parse LLM response into structured extractions."""
        extractions = []

        for line in raw_text.split('\n'):
            line = line.strip()
            if not line or '->' not in line:
                continue

            # Format: "ORIGINAL: text -> ENGLISH: translation"
            if 'ORIGINAL:' in line and 'ENGLISH:' in line:
                try:
                    parts = line.split('->')
                    original = parts[0].replace('ORIGINAL:', '').strip()
                    english = parts[1].replace('ENGLISH:', '').strip() if len(parts) > 1 else original

                    if original and english and original != english:
                        extractions.append(TextExtraction(
                            original=original,
                            translated=english
                        ))
                except Exception:
                    continue

        return extractions
```

---

## Config Schema

### Updates to `src/config.py`

```python
# Add to Config class in src/config.py

class Config(BaseSettings):
    # ... existing fields ...

    # ============ VISION PROVIDERS ============
    VISION_PROVIDER: str = Field(
        default="gemini",
        description="Primary vision provider (gemini, openai, anthropic)"
    )
    VISION_FALLBACK_PROVIDERS: Optional[str] = Field(
        default="openai,anthropic",
        description="Comma-separated fallback providers"
    )
    VISION_TIMEOUT_SEC: int = Field(
        default=30,
        description="Timeout for vision API requests"
    )
    VISION_MAX_RETRIES: int = Field(
        default=1,
        description="Max retries per provider before fallback"
    )

    # OpenAI (for vision fallback)
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key for GPT-4o vision"
    )
    OPENAI_VISION_MODEL: str = Field(
        default="gpt-4o",
        description="OpenAI model for vision tasks"
    )

    # Anthropic (for vision fallback)
    ANTHROPIC_API_KEY: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude vision"
    )
    ANTHROPIC_VISION_MODEL: str = Field(
        default="claude-sonnet-4-20250514",
        description="Anthropic model for vision tasks"
    )

    # ============ VALIDATORS ============

    @field_validator("VISION_PROVIDER")
    @classmethod
    def validate_vision_provider(cls, v: str) -> str:
        """Validate vision provider is supported."""
        allowed = {"gemini", "openai", "anthropic"}
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"VISION_PROVIDER must be one of {allowed}, got {v}")
        return v_lower

    # ============ HELPER PROPERTIES ============

    @property
    def vision_fallback_list(self) -> List[str]:
        """Parse VISION_FALLBACK_PROVIDERS into list."""
        if not self.VISION_FALLBACK_PROVIDERS:
            return []
        return [p.strip().lower() for p in self.VISION_FALLBACK_PROVIDERS.split(",") if p.strip()]
```

### Updates to `.env.example`

```env
# ============ VISION PROVIDERS ============

# Primary vision provider for OCR (gemini, openai, anthropic)
VISION_PROVIDER=gemini

# Fallback providers (comma-separated, tried in order if primary fails)
VISION_FALLBACK_PROVIDERS=openai,anthropic

# Timeout for vision API requests (seconds)
VISION_TIMEOUT_SEC=30

# Max retries per provider before trying fallback
VISION_MAX_RETRIES=1

# OpenAI API key (required if using openai as provider or fallback)
# Get your API key at: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...

# OpenAI model for vision (default: gpt-4o)
OPENAI_VISION_MODEL=gpt-4o

# Anthropic API key (required if using anthropic as provider or fallback)
# Get your API key at: https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-...

# Anthropic model for vision (default: claude-sonnet-4-20250514)
ANTHROPIC_VISION_MODEL=claude-sonnet-4-20250514
```

---

## Rationale

### Why LangChain?

1. **Unified Interface**: Same message format for all providers
2. **Async Support**: Native `ainvoke()` for non-blocking operations
3. **Ecosystem**: Well-maintained packages for each provider
4. **Future-proof**: Easy to add new providers as they emerge

### Why Keep PaddleOCR + PIL?

1. **Grid Preservation**: Trading charts have precise grid lines that generative image editing destroys
2. **Deterministic**: Same input always produces same output
3. **Reliability**: 95%+ success rate vs <40% with pure generative approach
4. **Speed**: Local processing is faster than round-trip to image generation API

### Why Fallback Chain?

1. **Reliability**: No single point of failure
2. **Cost Optimization**: Can use cheaper providers as primary
3. **Rate Limits**: Automatic switching when one provider is rate-limited
4. **Flexibility**: Easy A/B testing of providers

---

## Alternatives Considered

### Alternative 1: Direct SDK for Each Provider

**Pros:**
- Full access to provider-specific features
- Potentially lower latency (no abstraction layer)

**Cons:**
- Different interfaces for each provider
- More code duplication
- Harder to add new providers

**Why rejected:** LangChain overhead is minimal, and unified interface is more valuable than marginal performance gains.

### Alternative 2: Single Provider (Gemini Only)

**Pros:**
- Simpler architecture
- Fewer dependencies
- Lower maintenance

**Cons:**
- Single point of failure
- Vendor lock-in
- No fallback for outages

**Why rejected:** User explicitly requested multi-provider support with fallback.

### Alternative 3: Replace PaddleOCR with LangChain Vision

**Pros:**
- Simpler pipeline (single tool for OCR + editing)
- Less dependencies

**Cons:**
- Generative image editing destroys chart grids
- Much lower reliability (<40%)
- Inconsistent results

**Why rejected:** Research showed hybrid pipeline is essential for trading chart quality.

---

## Consequences

### Positive

1. **Provider Flexibility**: Easy to switch between providers via config
2. **Improved Reliability**: Fallback chain handles provider failures
3. **Unified Interface**: Clean abstraction for vision operations
4. **Maintainability**: Clear separation between vision OCR and image editing
5. **Testability**: Easy to mock providers in tests

### Negative

1. **New Dependencies**: Adds langchain-openai, langchain-anthropic packages
2. **Complexity**: More files and abstraction layers
3. **API Key Management**: Need to manage multiple provider keys
4. **Cost**: Multiple providers may incur additional costs

### Neutral

1. **Migration Required**: `image_editor.py` needs update to use new vision module
2. **Configuration**: New env vars need documentation
3. **Testing**: Need integration tests for each provider

---

## Implementation Notes

### Phase 1: Core Module (2-3 hours)

1. Create `src/vision/` directory structure
2. Implement `VisionProvider` ABC and `VisionResult` dataclass
3. Implement `GeminiVisionProvider` with LangChain
4. Implement `VisionProviderFactory`
5. Unit tests for Gemini provider

### Phase 2: Fallback Chain (1-2 hours)

1. Implement `OpenAIVisionProvider`
2. Implement `AnthropicVisionProvider`
3. Implement `FallbackChain` orchestrator
4. Integration tests for fallback

### Phase 3: Integration (1-2 hours)

1. Update `src/config.py` with new settings
2. Update `.env.example` with new variables
3. Modify `src/ocr/image_editor.py` to use `src.vision`
4. Deprecation warning for `src/ocr/gemini_ocr.py`
5. End-to-end tests

### Phase 4: Documentation (30 min)

1. Update README with new configuration
2. Update `docs/architecture.md`
3. Add migration guide for existing users

---

## Dependencies to Add

```
# requirements.txt additions
langchain-core>=0.3.0
langchain-google-genai>=2.0.0
langchain-openai>=0.2.0
langchain-anthropic>=0.3.0
```

---

## References

- [LangChain Vision Documentation](https://python.langchain.com/docs/how_to/multimodal_inputs/)
- [OpenAI GPT-4o Vision](https://platform.openai.com/docs/guides/vision)
- [Gemini Vision API](https://ai.google.dev/gemini-api/docs/vision)
- [Anthropic Claude Vision](https://docs.anthropic.com/claude/docs/vision)
- Research: `docs/research/image-text-translation-analysis.md`
