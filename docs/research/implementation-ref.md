# Supplementary Implementation Reference: Tools & Code Templates

## Quick Reference: Key Code Snippets

### 1. Fast Start - Minimal Implementation (Copy-Paste Ready)

```python
"""
Minimal working example: PaddleOCR + PIL replacement
No external dependencies beyond standard packages
"""

from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from paddleocr import PaddleOCR
import asyncio

class MinimalReplacer:
    def __init__(self):
        self.ocr = PaddleOCR(use_angle_cls=True, lang=['ru'])
        
    def replace_single_text(self, image_path, original, replacement):
        """Replace one text element in image."""
        # 1. Detect bounding box
        result = self.ocr.ocr(image_path)
        bbox_rect = None
        
        for line in result:
            for word in line:
                if word[1][0] == original:
                    bbox = word[0]
                    xs = [p[0] for p in bbox]
                    ys = [p[1] for p in bbox]
                    bbox_rect = (min(xs), min(ys), max(xs), max(ys))
                    break
        
        if not bbox_rect:
            return Image.open(image_path)
        
        # 2. Extract text color from region
        img = Image.open(image_path)
        x1, y1, x2, y2 = bbox_rect
        crop = img.crop((x1+2, y1+2, x2-2, y2-2))
        pixels = np.array(crop.convert('RGB'))
        
        # Most common non-dark color
        dark_mask = np.mean(pixels, axis=2) > 50
        if np.any(dark_mask):
            colors = pixels[dark_mask]
            color = tuple(colors[np.random.choice(len(colors))])
        else:
            color = (255, 255, 255)
        
        # 3. Render replacement
        font_size = int((y2 - y1) * 0.8)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        draw = ImageDraw.Draw(img)
        draw.text((x1, y1), replacement, font=font, fill=color)
        
        return img

# Usage
replacer = MinimalReplacer()
result = replacer.replace_single_text('trading_signal.jpg', 'Цена', 'Price')
result.save('output.jpg')
```

---

### 2. Color Extraction Strategies

```python
def extract_dominant_color_hsv(crop: Image.Image) -> Tuple[int, int, int]:
    """
    Extract text color using HSV space (more intuitive for colors).
    Better for colored text (green/red trading indicators).
    """
    hsv = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2HSV)
    
    # Find dominant hue (excluding grays)
    # Saturation > 50 = colored, < 50 = near grayscale
    colored_mask = hsv[:,:,1] > 50
    
    if np.any(colored_mask):
        colored_pixels = hsv[colored_mask]
        # Find most common hue
        hue_hist = np.histogram(colored_pixels[:, 0], bins=180)[0]
        dominant_hue = np.argmax(hue_hist)
        
        # Get sample pixel with that hue
        hue_mask = hsv[:,:,0] == dominant_hue
        if np.any(hue_mask):
            sample_pixel = np.array(crop)[hue_mask][0]
            return tuple(sample_pixel)
    
    # Fallback: average color
    return tuple(np.mean(np.array(crop), axis=(0, 1)).astype(int))

def extract_color_with_contrast_preservation(
    image: Image.Image,
    bbox_rect: Tuple
) -> Tuple[int, int, int]:
    """
    Extract text color while preserving contrast with background.
    Useful for trading signals where contrast matters.
    """
    x1, y1, x2, y2 = bbox_rect
    
    # Sample text interior (avoid edges)
    margin = 2
    interior = image.crop((x1+margin, y1+margin, x2-margin, y2-margin))
    
    # Sample background around text (just outside bbox)
    if y1 > 0:
        top_bg = image.crop((x1, max(0, y1-3), x2, y1))
    elif y2 < image.height:
        top_bg = image.crop((x1, y2, x2, min(image.height, y2+3)))
    else:
        top_bg = image.crop((max(0, x1-3), y1, x1, y2))
    
    text_avg = np.mean(np.array(interior), axis=(0, 1))
    bg_avg = np.mean(np.array(top_bg), axis=(0, 1))
    
    # Enhance contrast: amplify difference
    text_color = text_avg + 0.3 * (text_avg - bg_avg)
    text_color = np.clip(text_color, 0, 255)
    
    return tuple(text_color.astype(int))
```

---

### 3. Smart Font Size Adjustment

```python
def calculate_optimal_font_size(
    original_bbox: Tuple,
    translated_text: str,
    original_text: str,
    font_path: str
) -> int:
    """
    Calculate font size that fits translated text within bbox.
    """
    x1, y1, x2, y2 = original_bbox
    max_width = x2 - x1
    max_height = y2 - y1
    
    # Start with estimated size
    estimated = int(max_height * 0.8)
    
    # Check if text fits
    for size in range(estimated, 4, -1):
        try:
            font = ImageFont.truetype(font_path, size)
            draw = ImageDraw.Draw(Image.new('RGB', (100, 100)))
            
            bbox = draw.textbbox((0, 0), translated_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            if text_width <= max_width and text_height <= max_height:
                return size
        except:
            continue
    
    return 4  # Minimum readable size

def fit_text_with_wrapping(
    text: str,
    max_width: int,
    font: ImageFont
) -> List[str]:
    """
    Wrap text to fit width. Returns list of lines.
    """
    words = text.split()
    lines = []
    current_line = []
    
    draw = ImageDraw.Draw(Image.new('RGB', (200, 50)))
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]
        
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines
```

---

### 4. Edge Blending (Different Strategies)

```python
def blend_edges_gaussian(image: Image.Image, mask: np.ndarray) -> Image.Image:
    """
    Gaussian blur-based blending (smooth but may lose sharpness).
    Good for text on uniform backgrounds.
    """
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    
    # Expand mask for gradient blending
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_expanded = cv2.dilate(mask, kernel, iterations=2)
    
    # Blur entire image
    blurred = cv2.GaussianBlur(img_cv, (3, 3), 0)
    
    # Blend: use original for text area, blurred for edges
    alpha = mask_expanded.astype(float) / 255.0
    alpha = np.stack([alpha] * 3, axis=2)
    
    result = (img_cv * alpha + blurred * (1 - alpha)).astype(np.uint8)
    
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))

def blend_edges_bilateral(image: Image.Image, mask: np.ndarray) -> Image.Image:
    """
    Bilateral filter (preserves edges better, best for low-res).
    Recommended for trading signals with grid lines.
    """
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask_edges = cv2.dilate(mask, kernel, iterations=1)
    
    # Bilateral: smooths while preserving edges
    bilateral = cv2.bilateralFilter(img_cv, d=5, sigmaColor=50, sigmaSpace=50)
    
    # Only apply near edges
    result = np.where(mask_edges[:, :, None] == 255, img_cv, bilateral)
    
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))

def blend_edges_none(image: Image.Image, mask: np.ndarray) -> Image.Image:
    """
    No blending (fastest, good for already crisp text).
    Recommended for testing or when original has sharp edges.
    """
    return image  # Identity function
```

---

### 5. Production Error Handling

```python
class TextReplacementError(Exception):
    """Base exception for text replacement pipeline."""
    pass

class OCRError(TextReplacementError):
    """Raised when OCR fails or detects no text."""
    pass

class BoundingBoxError(TextReplacementError):
    """Raised when bounding box is invalid."""
    pass

def validate_bbox(bbox_rect: Tuple, image_size: Tuple) -> bool:
    """Validate bounding box is within image bounds."""
    x1, y1, x2, y2 = bbox_rect
    width, height = image_size
    
    # Check bounds
    if not (0 <= x1 < width and 0 <= x2 <= width):
        return False
    if not (0 <= y1 < height and 0 <= y2 <= height):
        return False
    
    # Check area is reasonable
    area = (x2 - x1) * (y2 - y1)
    if area < 9 or area > width * height:  # Min 3x3, max full image
        return False
    
    return True

def safe_process_image(
    image_path: str,
    translations: Dict[str, str],
    replacer: SeamlessTextReplacer,
    fallback_to_original: bool = True
) -> Image.Image:
    """Wrapper with error handling."""
    try:
        # Validate input
        if not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")
        
        img = Image.open(image_path)
        if img.mode not in ['RGB', 'RGBA']:
            img = img.convert('RGB')
        
        # Process
        result = asyncio.run(replacer.process_image_async(image_path, translations))
        
        # Validate output
        if result.size != img.size:
            raise TextReplacementError("Output size mismatch")
        
        return result
        
    except OCRError as e:
        logger.error(f"OCR failed: {e}")
        if fallback_to_original:
            logger.warning("Returning original image")
            return Image.open(image_path).convert('RGB')
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error in text replacement: {e}")
        if fallback_to_original:
            return Image.open(image_path).convert('RGB')
        raise
```

---

### 6. Testing Utilities

```python
def compare_replacements(original: Image.Image, modified: Image.Image) -> Dict:
    """
    Compare original and modified images to detect issues.
    Useful for quality assurance.
    """
    orig_arr = np.array(original)
    mod_arr = np.array(modified)
    
    # 1. Total pixel difference
    diff = np.abs(orig_arr.astype(float) - mod_arr.astype(float))
    mean_diff = np.mean(diff)
    
    # 2. Edge artifacts (high-frequency changes)
    sobelx_orig = cv2.Sobel(cv2.cvtColor(orig_arr, cv2.COLOR_RGB2GRAY), cv2.CV_64F, 1, 0, ksize=3)
    sobelx_mod = cv2.Sobel(cv2.cvtColor(mod_arr, cv2.COLOR_RGB2GRAY), cv2.CV_64F, 1, 0, ksize=3)
    edge_diff = np.mean(np.abs(sobelx_orig - sobelx_mod))
    
    # 3. Color shift (evaluate if colors changed outside text regions)
    # Sample corner regions (assumed to be background only)
    corner_size = 20
    corners = [
        orig_arr[0:corner_size, 0:corner_size],
        orig_arr[-corner_size:, 0:corner_size],
        orig_arr[0:corner_size, -corner_size:],
        orig_arr[-corner_size:, -corner_size:]
    ]
    
    color_shift = 0
    for i, corner in enumerate(corners):
        corner_mod = [
            mod_arr[0:corner_size, 0:corner_size],
            mod_arr[-corner_size:, 0:corner_size],
            mod_arr[0:corner_size, -corner_size:],
            mod_arr[-corner_size:, -corner_size:]
        ][i]
        color_shift += np.mean(np.abs(corner.astype(float) - corner_mod.astype(float)))
    
    color_shift /= 4
    
    return {
        'mean_pixel_diff': mean_diff,
        'edge_artifact_score': edge_diff,
        'background_color_shift': color_shift,
        'quality_rating': 'EXCELLENT' if mean_diff < 10 else 'GOOD' if mean_diff < 20 else 'FAIR' if mean_diff < 40 else 'POOR'
    }

def batch_test_ocr_accuracy(image_dir: str, ocr_engine: PaddleOCR) -> Dict:
    """
    Test OCR accuracy on all images in directory.
    Requires manual labeling of expected texts.
    """
    results = []
    
    for img_file in os.listdir(image_dir):
        if not img_file.lower().endswith(('.jpg', '.png')):
            continue
        
        result = ocr_engine.ocr(os.path.join(image_dir, img_file))
        detected_texts = [word[1][0] for line in result for word in line]
        
        results.append({
            'image': img_file,
            'detected_count': len(detected_texts),
            'texts': detected_texts
        })
    
    return {
        'total_images': len(results),
        'total_texts_detected': sum(r['detected_count'] for r in results),
        'results': results
    }
```

---

### 7. Async Optimization for Telegram

```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

class AsyncTextReplacer:
    def __init__(self, max_workers: int = 4):
        self.replacer = SeamlessTextReplacer()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def process_multiple(self, images_data: List[Tuple[str, Dict]]) -> List[Image.Image]:
        """
        Process multiple images concurrently (for batch operations).
        """
        tasks = [
            asyncio.to_thread(self._sync_process, path, translations)
            for path, translations in images_data
        ]
        
        return await asyncio.gather(*tasks)
    
    def _sync_process(self, path: str, translations: Dict) -> Image.Image:
        """Synchronous wrapper for thread pool."""
        return asyncio.run(self.replacer.process_image_async(path, translations))
    
    async def process_with_timeout(
        self,
        image_path: str,
        translations: Dict,
        timeout_seconds: int = 10
    ) -> Image.Image:
        """Process with timeout handling."""
        try:
            result = await asyncio.wait_for(
                self.replacer.process_image_async(image_path, translations),
                timeout=timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Processing timeout for {image_path}")
            # Return original image as fallback
            return Image.open(image_path).convert('RGB')

# Integration with aiogram (Telegram bot)
replacer_async = AsyncTextReplacer(max_workers=2)

@dp.message(lambda msg: msg.photo)
async def handle_photo(message: Message):
    file_info = await bot.get_file(message.photo[-1].file_id)
    file_path = f"/tmp/{file_info.file_unique_id}.jpg"
    
    await bot.download_file(file_info.file_path, file_path)
    
    # Get translations (async call to Gemini)
    translations = await get_translations_async(file_path)
    
    # Process image with timeout
    result = await replacer_async.process_with_timeout(file_path, translations, timeout_seconds=5)
    
    # Send result
    output_path = f"/tmp/result_{file_info.file_unique_id}.jpg"
    result.save(output_path, quality=95)
    
    with open(output_path, 'rb') as photo:
        await message.reply_photo(photo)
```

---

### 8. Fallback Strategies

```python
def process_with_fallback_chain(
    image_path: str,
    translations: Dict,
    ocr_engines: List = None
) -> Tuple[Image.Image, str]:
    """
    Try multiple OCR engines in sequence if primary fails.
    Returns (result_image, method_used).
    """
    if ocr_engines is None:
        ocr_engines = ['paddleocr', 'easyocr', 'tesseract']
    
    last_error = None
    
    for engine in ocr_engines:
        try:
            if engine == 'paddleocr':
                replacer = PaddleTextReplacer()
            elif engine == 'easyocr':
                replacer = EasyTextReplacer()
            elif engine == 'tesseract':
                replacer = TesseractTextReplacer()
            else:
                continue
            
            result = asyncio.run(replacer.process_image_async(image_path, translations))
            logger.info(f"Successfully processed using {engine}")
            
            return result, engine
        
        except Exception as e:
            logger.warning(f"{engine} failed: {e}")
            last_error = e
            continue
    
    # All engines failed, return original
    logger.error(f"All OCR engines failed. Last error: {last_error}")
    return Image.open(image_path).convert('RGB'), 'fallback_original'
```

---

## Deployment Configuration Files

### `.env` (Environment Variables)

```
# PaddleOCR Settings
PADDLE_OCR_LANG=ru
PADDLE_OCR_USE_GPU=false
PADDLE_MODEL_DIR=/app/models

# Telegram Bot
TELEGRAM_TOKEN=your_token_here
BOT_WEBHOOK_URL=https://yourdomain.com/webhook

# Processing
MAX_IMAGE_SIZE=800
PROCESSING_TIMEOUT_SECONDS=10
NUM_WORKERS=4

# Logging
LOG_LEVEL=INFO
```

### `docker-compose.yml` (For quick local testing)

```yaml
version: '3.8'

services:
  bot:
    build: .
    environment:
      - TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
      - LOG_LEVEL=INFO
    volumes:
      - ./models:/app/models
      - /tmp:/tmp
    restart: unless-stopped
    ports:
      - "8000:8000"
```

---

## Quick Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Text not detected at all" | PaddleOCR confidence too high | Lower `conf_threshold` in OCR config |
| "Replacement text too small/large" | Font size estimation off | Check `_estimate_font_size()` formula |
| "White halos around text" | Background color not extracted correctly | Use HSV color space (see Part 2) |
| "Blurry after blending" | Bilateral filter sigma too high | Reduce `sigmaColor` to 30 (from 50) |
| "Slow processing (>5s)" | Model loading on each request | Cache OCR model in `__init__` |
| "Memory error on 4GB RAM" | PaddleOCR models too large | Use `lite_config=True` for lighter models |
