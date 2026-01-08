# Task 05: Manual Testing - COMPLETED

## Test Results

### Test Configuration
- Provider: OpenAI (gpt-image-1)
- Original image: 1280x723 (aspect ratio 1.77)
- Translations: {"Продать": "Sell", "Покупать": "Buy"}

### Results
- **Result size: 1536x1024** (aspect ratio 1.50)
- ⚠️ Aspect ratio changed: 1.77 → 1.50
- API call took ~3 minutes

### Root Cause Analysis

OpenAI Images Edit API supports only fixed sizes:
- 1024x1024 (square)
- 1536x1024 (landscape)
- 1024x1536 (portrait)

When `size` is omitted or set to `auto`:
- API chooses closest supported size
- For 1280x723 (1.77:1) → selected 1536x1024 (1.5:1)

**Before fix**: Always 1024x1024 (cropping + distortion)
**After fix**: 1536x1024 (better, but still not original proportions)

### Improvement

| Metric | Before | After |
|--------|--------|-------|
| Output size | 1024x1024 | 1536x1024 |
| Aspect ratio | 1.0 | 1.5 |
| Original ratio | 1.77 | 1.77 |
| Distortion | Severe (cropped) | Moderate (stretched) |

**Result: Significant improvement**. Images no longer cropped to square, but still not preserving exact proportions.

### Possible Further Improvements

1. **Padding approach**: Add letterbox/pillarbox padding to input image to match supported aspect ratios
2. **Post-processing**: Crop result back to original proportions
3. **Alternative API**: Use Gemini which may have better aspect ratio support

### Prompt Quality

New prompt (893 chars) is well-structured with:
- Context: "This is a trading signal image"
- PRESERVE section with 8 bullet points
- DO NOT section with 6 bullet points
- Clear formatting with quotes around text

### Status
PARTIAL SUCCESS - Size parameter fix improved output significantly, but API limitations prevent perfect aspect ratio preservation.

### Recommendation
Consider implementing padding approach for exact aspect ratio preservation, or document limitation for users.
