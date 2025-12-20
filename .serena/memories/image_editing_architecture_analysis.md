# Image Editing Architecture Analysis Report

## Current Architecture Overview

### 1. Image Editors in `src/image_editing/`

**Files:**
- `base.py` - Abstract base class and result dataclass
- `openai_editor.py` - OpenAI-based editor (gpt-image-1)
- `gemini_editor.py` - Gemini-based editor (gemini-2.5-flash-image)
- `paddleocr_editor.py` - PaddleOCR+PIL hybrid editor
- `__init__.py` - Conditional imports

**Architecture:**
- All editors implement `ImageEditor` ABC with:
  - `is_available()` - Check if editor can be used
  - `edit_image()` - Synchronous image editing
  - `edit_image_async()` - Async wrapper
  - `name` property - Editor identifier
- All return `EditResult` dataclass with success/error/metadata

### 2. Config & Editor Selection

**Configuration (src/config.py):**
```
IMAGE_EDITOR: str = Field(default="openai", allowed: {"paddleocr", "gemini", "openai"})
IMAGE_EDITOR_FALLBACK: Optional[str] = Field(default="gemini")
OPENAI_IMAGE_MODEL: str = Field(default="gpt-image-1")
GEMINI_IMAGE_MODEL: str = Field(default="gemini-2.5-flash-image")
```

**CRITICAL ISSUE:**
- Config variables `IMAGE_EDITOR` and `IMAGE_EDITOR_FALLBACK` are **DEFINED BUT NOT USED**
- No factory/selector implementation exists in codebase
- Editors are instantiated manually but never selected via config

### 3. Current Image Editing Flow (HYBRID APPROACH)

**Entry Point:** `src/handlers/signal_handler.py::handle_new_signal()`
- Calls `process_image()` from `src.ocr.gemini_ocr`

**Pipeline:**
```
process_image() [gemini_ocr.py:123]
  ├─→ calls edit_image_text() [ocr/image_editor.py:286]
       ├─ Stage 1: Gemini OCR extraction (vision chain with fallback)
       │  - Detects and translates Russian → English
       │  - Returns: Dict[russian_text → english_text]
       │
       └─ Stage 2: PaddleOCR + PIL replacement [seamless_replacer.py]
          - Uses PaddleOCR to detect bounding boxes
          - Extracts text color/background from image
          - Clears original text area
          - Renders replacement text with PIL
          - Blends edges with bilateral filter
```

**Current Implementation:** `src/ocr/image_editor.py` (NOT in src/image_editing/)
- Hardcoded hybrid: Gemini translation + PaddleOCR replacement
- Does NOT use ImageEditor abstraction or config
- Comments state: "95%+ reliability vs <40% with pure Gemini Image"

### 4. Generative Image Editors Available

**OpenAI (openai_editor.py):**
- Uses OpenAI API `images.edit()` endpoint
- Creates white mask (entire image editable)
- Prompt-based: "Replace text X with Y"
- Currently NOT used in flow

**Gemini (gemini_editor.py):**
- Uses Gemini `models.generate_content()` API
- Sends image + prompt to Gemini model
- Model returns edited image with text replaced
- Currently NOT used in flow

### 5. Key Files in Current Flow

**Hybrid Approach Files:**
- `src/ocr/image_editor.py` - Main hybrid implementation
- `src/ocr/seamless_replacer.py` - PaddleOCR + PIL text replacement
- `src/ocr/paddleocr_worker.py` - Subprocess runner for PaddleOCR

**Vision/Translation Files:**
- `src/ocr/gemini_ocr.py` - Gemini OCR extraction
- `src/vision/` - Multi-provider vision chain for OCR extraction

**Unused ImageEditor Framework:**
- `src/image_editing/` - Complete framework NOT integrated into flow

## Analysis: Why Users Need Clean OpenAI Approach

### Problems with Current Hybrid Approach:

1. **Dependency Hell**
   - Requires PaddleOCR + PIL + OpenCV + Tessdata models
   - Gemini extraction + PaddleOCR replacement = 2 API calls + local processing
   - Heavy system dependencies

2. **Complexity**
   - 2-stage pipeline with fallbacks
   - PaddleOCR subprocess isolation (spawn context) due to asyncio issues
   - Color extraction, font matching, edge blending = complex heuristics

3. **Latency**
   - Gemini API call → Parse translations → PaddleOCR detection → PIL rendering → Edge blending
   - 2-4 seconds typical per image

4. **No Framework Usage**
   - Perfect `ImageEditor` framework exists but unused
   - `IMAGE_EDITOR` config ignored
   - Tight coupling to hybrid approach

### Benefits of Pure Generative Approach (OpenAI/Gemini):

1. **Simplicity**
   - Single API call
   - Model handles all text detection, replacement, formatting
   - No local processing needed

2. **Reliability**
   - LLM understands context: "keep formatting, colors, fonts"
   - No hallucinations about what text exists
   - Deterministic for given prompt

3. **No Dependencies**
   - Drop PaddleOCR, OpenCV, PIL text rendering
   - Just OpenAI API

4. **Use Existing Framework**
   - ImageEditor abstraction ready to use
   - Factory pattern can select editor via config
   - Fallback mechanism built in
