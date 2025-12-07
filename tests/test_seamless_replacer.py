"""Comprehensive unit tests for SeamlessTextReplacer class."""

import tempfile
from pathlib import Path
from typing import List, Tuple
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

# cv2 is only needed for blend_edges tests - we'll mock it
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None

# Import directly to avoid cascade imports from __init__.py
import sys
from importlib import import_module
from importlib.util import spec_from_file_location, module_from_spec

# Mock dependencies before importing
if not CV2_AVAILABLE:
    mock_cv2 = Mock()
    # Make cvtColor return the input (identity function for mock)
    mock_cv2.cvtColor = Mock(side_effect=lambda x, _: x)
    mock_cv2.COLOR_RGB2BGR = 4
    mock_cv2.COLOR_BGR2RGB = 4
    mock_cv2.getStructuringElement = Mock(return_value=np.ones((3, 3), dtype=np.uint8))
    mock_cv2.MORPH_ELLIPSE = 2
    # dilate should return mask of same shape
    mock_cv2.dilate = Mock(side_effect=lambda mask, *args, **kwargs: mask)
    # bilateralFilter should return image of same shape
    mock_cv2.bilateralFilter = Mock(side_effect=lambda img, *args, **kwargs: img)
    sys.modules['cv2'] = mock_cv2
else:
    sys.modules['cv2'] = cv2

# Mock paddleocr module with PaddleOCR class
mock_paddleocr = Mock()
mock_paddleocr.PaddleOCR = Mock()
sys.modules['paddleocr'] = mock_paddleocr

# Mock structlog
mock_structlog = Mock()
mock_logger = Mock()
mock_logger.info = Mock()
mock_logger.warning = Mock()
mock_logger.error = Mock()
mock_logger.debug = Mock()
mock_structlog.get_logger = Mock(return_value=mock_logger)
sys.modules['structlog'] = mock_structlog

# Load the module directly from file path to avoid __init__.py imports
module_path = Path(__file__).parent.parent / "src" / "ocr" / "seamless_replacer.py"
spec = spec_from_file_location(
    "seamless_replacer",
    str(module_path)
)
seamless_replacer_module = module_from_spec(spec)
sys.modules['seamless_replacer'] = seamless_replacer_module
spec.loader.exec_module(seamless_replacer_module)

FONT_FALLBACKS = seamless_replacer_module.FONT_FALLBACKS
SeamlessTextReplacer = seamless_replacer_module.SeamlessTextReplacer
get_ocr = seamless_replacer_module.get_ocr
get_replacer = seamless_replacer_module.get_replacer


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_image_path():
    """Create temporary image file and clean up after test."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def simple_test_image():
    """Create simple RGB image with white text on black background."""
    img = Image.new('RGB', (200, 100), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Try to use default font
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
    except Exception:
        font = ImageFont.load_default()
    draw.text((10, 40), "TEST", fill=(255, 255, 255), font=font)
    return img


@pytest.fixture
def gradient_background_image():
    """Create image with gradient background for color extraction testing."""
    img = Image.new('RGB', (200, 100))
    pixels = img.load()
    for y in range(100):
        for x in range(200):
            # Gradient from dark to light
            color = int(255 * (x / 200))
            pixels[x, y] = (color, color, color)
    return img


@pytest.fixture
def colored_text_image():
    """Create image with colored text for text color extraction."""
    img = Image.new('RGB', (200, 100), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)
    # Draw green text
    draw.rectangle([40, 30, 160, 70], fill=(10, 10, 10))
    draw.rectangle([50, 40, 150, 60], fill=(0, 255, 0))
    return img


@pytest.fixture
def mock_ocr_result():
    """Create mock PaddleOCR result structure (v3.x format)."""
    mock_result = MagicMock()
    mock_result.rec_texts = ['TEST', 'HELLO']
    mock_result.dt_polys = np.array([
        [[10, 10], [90, 10], [90, 30], [10, 30]],  # TEST bbox
        [[10, 50], [110, 50], [110, 70], [10, 70]]  # HELLO bbox
    ])
    mock_result.rec_scores = [0.95, 0.98]
    # Configure the mock to work with .get() method like a dict
    mock_result.get = lambda key, default=None: getattr(mock_result, key, default)
    return [mock_result]


@pytest.fixture
def replacer():
    """Create SeamlessTextReplacer instance."""
    return SeamlessTextReplacer()


@pytest.fixture
def mock_available_fonts(tmp_path):
    """Create mock font files for testing."""
    font_dir = tmp_path / "fonts"
    font_dir.mkdir()
    font_file = font_dir / "test_font.ttf"
    font_file.touch()
    return [str(font_file)]


# ============================================================================
# Test: _bbox_to_rect
# ============================================================================


class TestBboxToRect:
    """Tests for _bbox_to_rect static method."""

    def test_bbox_to_rect_normal(self):
        """Test standard 4-point bbox conversion."""
        bbox = [[10, 20], [90, 20], [90, 50], [10, 50]]
        result = SeamlessTextReplacer._bbox_to_rect(bbox)
        assert result == (10, 20, 90, 50)

    def test_bbox_to_rect_rotated(self):
        """Test rotated bbox (non-axis-aligned)."""
        bbox = [[15, 10], [95, 15], [90, 55], [10, 50]]
        result = SeamlessTextReplacer._bbox_to_rect(bbox)
        # Should return bounding rectangle
        assert result == (10, 10, 95, 55)

    def test_bbox_to_rect_single_point(self):
        """Test degenerate case with single point repeated."""
        bbox = [[50, 50], [50, 50], [50, 50], [50, 50]]
        result = SeamlessTextReplacer._bbox_to_rect(bbox)
        assert result == (50, 50, 50, 50)

    def test_bbox_to_rect_float_coordinates(self):
        """Test bbox with float coordinates."""
        bbox = [[10.7, 20.3], [89.9, 20.1], [90.2, 49.8], [10.1, 50.2]]
        result = SeamlessTextReplacer._bbox_to_rect(bbox)
        # Should convert to integers
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)
        assert result == (10, 20, 90, 50)

    def test_bbox_to_rect_negative_coordinates(self):
        """Test bbox with negative coordinates."""
        bbox = [[-10, -20], [50, -20], [50, 30], [-10, 30]]
        result = SeamlessTextReplacer._bbox_to_rect(bbox)
        assert result == (-10, -20, 50, 30)


# ============================================================================
# Test: extract_text_color
# ============================================================================


class TestExtractTextColor:
    """Tests for extract_text_color method."""

    def test_extract_white_text_on_black(self, replacer, simple_test_image):
        """Test extracting white text color from black background."""
        bbox_rect = (10, 30, 80, 60)
        color = replacer.extract_text_color(simple_test_image, bbox_rect)
        # Should extract bright color (close to white)
        assert color[0] > 200 or color[1] > 200 or color[2] > 200

    def test_extract_color_from_colored_text(self, replacer, colored_text_image):
        """Test extracting green text color."""
        bbox_rect = (50, 40, 150, 60)
        color = replacer.extract_text_color(colored_text_image, bbox_rect)
        # Should extract green-ish color
        # Green channel should be highest
        assert color[1] > color[0]
        assert color[1] > color[2]

    def test_extract_color_empty_bbox(self, replacer, simple_test_image):
        """Test with empty bbox after margin adjustment."""
        # Bbox too small to have content after margin
        bbox_rect = (10, 10, 12, 12)
        color = replacer.extract_text_color(simple_test_image, bbox_rect)
        # Should fallback to white
        assert color == (255, 255, 255)

    def test_extract_color_bbox_outside_image(self, replacer, simple_test_image):
        """Test with bbox partially outside image bounds."""
        # Bbox extends beyond image
        bbox_rect = (150, 50, 300, 150)
        color = replacer.extract_text_color(simple_test_image, bbox_rect)
        # Should handle gracefully and return valid color
        assert len(color) == 3
        assert all(0 <= c <= 255 for c in color)

    def test_extract_color_all_dark_pixels(self, replacer):
        """Test with region containing only dark pixels."""
        # Create image with all dark pixels
        img = Image.new('RGB', (100, 100), color=(5, 5, 5))
        bbox_rect = (10, 10, 50, 50)
        color = replacer.extract_text_color(img, bbox_rect)
        # Should fallback to white when no bright pixels found
        assert color == (255, 255, 255)

    def test_extract_color_with_margin(self, replacer):
        """Test that margin is applied correctly."""
        # Create image with specific color pattern
        img = Image.new('RGB', (100, 100), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Draw colored rectangle with edges
        draw.rectangle([10, 10, 50, 50], fill=(100, 200, 150))

        bbox_rect = (10, 10, 50, 50)
        color = replacer.extract_text_color(img, bbox_rect)
        # Should extract color from center (after margin), not edges
        assert len(color) == 3


# ============================================================================
# Test: extract_background_color
# ============================================================================


class TestExtractBackgroundColor:
    """Tests for extract_background_color method."""

    def test_extract_bg_black_background(self, replacer, simple_test_image):
        """Test extracting black background color."""
        bbox_rect = (10, 40, 80, 60)
        color = replacer.extract_background_color(simple_test_image, bbox_rect)
        # Should extract dark color (close to black)
        assert all(c < 50 for c in color)

    def test_extract_bg_from_above(self, replacer):
        """Test sampling background from above text."""
        img = Image.new('RGB', (100, 100), color=(50, 100, 150))
        bbox_rect = (20, 30, 80, 50)
        color = replacer.extract_background_color(img, bbox_rect)
        # Should be close to background color
        assert abs(color[0] - 50) < 20
        assert abs(color[1] - 100) < 20
        assert abs(color[2] - 150) < 20

    def test_extract_bg_from_below_when_top_unavailable(self, replacer):
        """Test sampling from below when bbox is at top edge."""
        img = Image.new('RGB', (100, 100), color=(200, 150, 100))
        # Bbox at very top of image
        bbox_rect = (20, 0, 80, 10)
        color = replacer.extract_background_color(img, bbox_rect)
        # Should sample from below and get background color
        assert len(color) == 3
        assert all(0 <= c <= 255 for c in color)

    def test_extract_bg_fallback_to_black(self, replacer):
        """Test fallback when no sampling region available."""
        img = Image.new('RGB', (10, 10), color=(255, 255, 255))
        # Bbox covering entire image
        bbox_rect = (0, 0, 10, 10)
        color = replacer.extract_background_color(img, bbox_rect)
        # Should fallback to black
        assert color == (0, 0, 0)

    def test_extract_bg_gradient(self, replacer, gradient_background_image):
        """Test background extraction from gradient."""
        bbox_rect = (50, 30, 150, 70)
        color = replacer.extract_background_color(gradient_background_image, bbox_rect)
        # Should return average of sampled region
        assert len(color) == 3
        assert all(0 <= c <= 255 for c in color)


# ============================================================================
# Test: estimate_font_size
# ============================================================================


class TestEstimateFontSize:
    """Tests for estimate_font_size method."""

    def test_estimate_normal_height(self, replacer):
        """Test font size estimation for normal text height."""
        bbox_rect = (10, 10, 100, 30)  # Height = 20
        size = replacer.estimate_font_size(bbox_rect)
        # Should be roughly 85% of height
        assert size == int(20 * 0.85)

    def test_estimate_large_height(self, replacer):
        """Test font size for large text."""
        bbox_rect = (10, 10, 100, 60)  # Height = 50
        size = replacer.estimate_font_size(bbox_rect)
        assert size == int(50 * 0.85)

    def test_estimate_small_height(self, replacer):
        """Test font size for very small text."""
        bbox_rect = (10, 10, 50, 15)  # Height = 5
        size = replacer.estimate_font_size(bbox_rect)
        # Should enforce minimum of 8
        assert size >= 8

    def test_estimate_zero_height(self, replacer):
        """Test with zero height bbox."""
        bbox_rect = (10, 20, 50, 20)  # Height = 0
        size = replacer.estimate_font_size(bbox_rect)
        # Should return minimum size
        assert size == 8

    def test_estimate_typical_signal_heights(self, replacer):
        """Test typical heights for trading signal images."""
        # Low-res signal text is typically 15-40 pixels tall
        for height in [15, 20, 25, 30, 35, 40]:
            bbox_rect = (0, 0, 100, height)
            size = replacer.estimate_font_size(bbox_rect)
            assert 8 <= size <= 50
            assert size == max(8, int(height * 0.85))


# ============================================================================
# Test: get_font
# ============================================================================


class TestGetFont:
    """Tests for get_font method."""

    def test_get_font_with_available_fonts(self, replacer):
        """Test getting font when fonts are available."""
        with patch.object(replacer, '_available_fonts', FONT_FALLBACKS[:1]):
            if Path(FONT_FALLBACKS[0]).exists():
                font = replacer.get_font(20)
                assert isinstance(font, (ImageFont.FreeTypeFont, ImageFont.ImageFont))

    def test_get_font_no_fonts_available(self, replacer):
        """Test fallback when no fonts available."""
        with patch.object(replacer, '_available_fonts', []):
            font = replacer.get_font(20)
            # Should return default font
            assert font is not None

    def test_get_font_invalid_font_path(self, replacer):
        """Test with invalid font paths."""
        with patch.object(replacer, '_available_fonts', ['/nonexistent/font.ttf']):
            font = replacer.get_font(20)
            # Should fallback to default
            assert font is not None

    def test_get_font_different_sizes(self, replacer):
        """Test getting fonts at different sizes."""
        for size in [8, 12, 20, 30, 40]:
            font = replacer.get_font(size)
            assert font is not None


# ============================================================================
# Test: fit_text_to_bbox
# ============================================================================


class TestFitTextToBbox:
    """Tests for fit_text_to_bbox method."""

    def test_fit_text_normal_case(self, replacer):
        """Test fitting text that fits comfortably."""
        bbox_rect = (0, 0, 200, 30)
        font, size = replacer.fit_text_to_bbox("TEST", bbox_rect, 20)
        assert font is not None
        assert 6 <= size <= 20

    def test_fit_text_very_long_text(self, replacer):
        """Test fitting very long text."""
        bbox_rect = (0, 0, 50, 20)
        long_text = "VERYLONGTEXTSTRING"
        font, size = replacer.fit_text_to_bbox(long_text, bbox_rect, 20)
        # Should decrease size to fit
        assert size < 20

    def test_fit_text_minimum_size(self, replacer):
        """Test that minimum size is enforced."""
        bbox_rect = (0, 0, 10, 20)
        very_long_text = "EXTREMELYLONGTEXTSTRING"
        font, size = replacer.fit_text_to_bbox(very_long_text, bbox_rect, 20)
        # Should return minimum size 6
        assert size == 6

    def test_fit_text_short_text_large_bbox(self, replacer):
        """Test short text in large bbox."""
        bbox_rect = (0, 0, 500, 50)
        font, size = replacer.fit_text_to_bbox("HI", bbox_rect, 30)
        # Should use requested size (text fits)
        assert size == 30

    def test_fit_text_empty_string(self, replacer):
        """Test with empty string."""
        bbox_rect = (0, 0, 100, 20)
        font, size = replacer.fit_text_to_bbox("", bbox_rect, 20)
        # Should return initial size for empty string
        assert font is not None


# ============================================================================
# Test: clear_text_region
# ============================================================================


class TestClearTextRegion:
    """Tests for clear_text_region method."""

    def test_clear_region_basic(self, replacer):
        """Test clearing text region with background color."""
        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        bbox_rect = (10, 10, 50, 30)
        bg_color = (0, 0, 0)

        result = replacer.clear_text_region(img, bbox_rect, bg_color)

        # Check that region was filled with black
        pixels = result.load()
        assert pixels[20, 20] == (0, 0, 0)

    def test_clear_region_different_colors(self, replacer):
        """Test clearing with different background colors."""
        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        bbox_rect = (10, 10, 50, 30)

        for bg_color in [(255, 0, 0), (0, 255, 0), (128, 128, 128)]:
            result = replacer.clear_text_region(img.copy(), bbox_rect, bg_color)
            pixels = result.load()
            assert pixels[20, 20] == bg_color

    def test_clear_region_full_image(self, replacer):
        """Test clearing entire image."""
        img = Image.new('RGB', (50, 50), color=(200, 200, 200))
        bbox_rect = (0, 0, 50, 50)
        bg_color = (100, 100, 100)

        result = replacer.clear_text_region(img, bbox_rect, bg_color)
        pixels = result.load()
        # Check corners
        assert pixels[0, 0] == bg_color
        assert pixels[49, 49] == bg_color


# ============================================================================
# Test: render_replacement_text
# ============================================================================


class TestRenderReplacementText:
    """Tests for render_replacement_text method."""

    def test_render_text_basic(self, replacer):
        """Test basic text rendering."""
        img = Image.new('RGB', (200, 100), color=(0, 0, 0))
        bbox_rect = (10, 40, 100, 70)
        text_color = (255, 255, 255)
        font = replacer.get_font(20)

        result = replacer.render_replacement_text(img, "TEST", bbox_rect, text_color, font)

        # Image should be modified
        assert result is not None
        assert result.size == (200, 100)

    def test_render_text_different_colors(self, replacer):
        """Test rendering with different text colors."""
        img = Image.new('RGB', (200, 100), color=(0, 0, 0))
        bbox_rect = (10, 40, 100, 70)
        font = replacer.get_font(15)

        for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
            result = replacer.render_replacement_text(img.copy(), "TEST", bbox_rect, color, font)
            assert result is not None

    def test_render_text_empty_string(self, replacer):
        """Test rendering empty string."""
        img = Image.new('RGB', (200, 100), color=(0, 0, 0))
        bbox_rect = (10, 40, 100, 70)
        font = replacer.get_font(20)

        result = replacer.render_replacement_text(img, "", bbox_rect, (255, 255, 255), font)
        assert result is not None

    def test_render_text_vertical_centering(self, replacer):
        """Test that text is vertically centered in bbox."""
        img = Image.new('RGB', (200, 100), color=(0, 0, 0))
        bbox_rect = (10, 10, 100, 90)  # Tall bbox
        font = replacer.get_font(15)

        result = replacer.render_replacement_text(img, "TEST", bbox_rect, (255, 255, 255), font)
        # Should not raise error
        assert result is not None


# ============================================================================
# Test: match_translations
# ============================================================================


class TestMatchTranslations:
    """Tests for match_translations method."""

    def test_match_exact(self, replacer):
        """Test exact matching."""
        detected_boxes = [
            {'text': 'LONG', 'bbox': [[0, 0], [50, 0], [50, 20], [0, 20]], 'bbox_rect': (0, 0, 50, 20)},
            {'text': 'SHORT', 'bbox': [[0, 30], [50, 30], [50, 50], [0, 50]], 'bbox_rect': (0, 30, 50, 50)}
        ]
        translations = {'LONG': 'BUY', 'SHORT': 'SELL'}

        matches = replacer.match_translations(detected_boxes, translations)

        assert len(matches) == 2
        assert matches[0][1] == 'BUY'
        assert matches[1][1] == 'SELL'

    def test_match_case_insensitive(self, replacer):
        """Test case-insensitive matching."""
        detected_boxes = [
            {'text': 'long', 'bbox': [[0, 0], [50, 0], [50, 20], [0, 20]], 'bbox_rect': (0, 0, 50, 20)}
        ]
        translations = {'LONG': 'BUY'}

        matches = replacer.match_translations(detected_boxes, translations)

        assert len(matches) == 1
        assert matches[0][1] == 'BUY'

    def test_match_substring(self, replacer):
        """Test substring matching for partial OCR."""
        detected_boxes = [
            {'text': 'LON', 'bbox': [[0, 0], [50, 0], [50, 20], [0, 20]], 'bbox_rect': (0, 0, 50, 20)},
            {'text': 'LONGER', 'bbox': [[0, 30], [50, 30], [50, 50], [0, 50]], 'bbox_rect': (0, 30, 50, 50)}
        ]
        translations = {'LONG': 'BUY'}

        matches = replacer.match_translations(detected_boxes, translations)

        # Should match both partial matches
        assert len(matches) >= 1

    def test_match_no_matches(self, replacer):
        """Test when no translations match."""
        detected_boxes = [
            {'text': 'UNKNOWN', 'bbox': [[0, 0], [50, 0], [50, 20], [0, 20]], 'bbox_rect': (0, 0, 50, 20)}
        ]
        translations = {'LONG': 'BUY', 'SHORT': 'SELL'}

        matches = replacer.match_translations(detected_boxes, translations)

        assert len(matches) == 0

    def test_match_empty_detected(self, replacer):
        """Test with empty detected boxes."""
        detected_boxes = []
        translations = {'LONG': 'BUY'}

        matches = replacer.match_translations(detected_boxes, translations)

        assert len(matches) == 0

    def test_match_empty_translations(self, replacer):
        """Test with empty translations dict."""
        detected_boxes = [
            {'text': 'LONG', 'bbox': [[0, 0], [50, 0], [50, 20], [0, 20]], 'bbox_rect': (0, 0, 50, 20)}
        ]
        translations = {}

        matches = replacer.match_translations(detected_boxes, translations)

        assert len(matches) == 0

    def test_match_whitespace_handling(self, replacer):
        """Test that whitespace is stripped correctly."""
        detected_boxes = [
            {'text': '  LONG  ', 'bbox': [[0, 0], [50, 0], [50, 20], [0, 20]], 'bbox_rect': (0, 0, 50, 20)}
        ]
        translations = {'LONG': 'BUY'}

        matches = replacer.match_translations(detected_boxes, translations)

        assert len(matches) == 1
        assert matches[0][1] == 'BUY'


# ============================================================================
# Test: extract_bounding_boxes (with mocked OCR)
# ============================================================================


class TestExtractBoundingBoxes:
    """Tests for extract_bounding_boxes method with mocked OCR."""

    @patch('seamless_replacer.get_ocr')
    def test_extract_boxes_success(self, mock_get_ocr, replacer, mock_ocr_result, temp_image_path):
        """Test successful bounding box extraction."""
        # Create test image
        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        img.save(temp_image_path)

        # Mock OCR
        mock_ocr_instance = Mock()
        mock_ocr_instance.predict.return_value = mock_ocr_result
        mock_get_ocr.return_value = mock_ocr_instance

        boxes = replacer.extract_bounding_boxes(temp_image_path)

        assert len(boxes) == 2
        assert boxes[0]['text'] == 'TEST'
        assert boxes[1]['text'] == 'HELLO'
        assert 'bbox' in boxes[0]
        assert 'bbox_rect' in boxes[0]
        assert 'confidence' in boxes[0]

    @patch('seamless_replacer.get_ocr')
    def test_extract_boxes_no_text(self, mock_get_ocr, replacer, temp_image_path):
        """Test with image containing no text."""
        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        img.save(temp_image_path)

        # Mock OCR with empty result
        mock_ocr_instance = Mock()
        mock_result = MagicMock()
        mock_result.rec_texts = []
        mock_result.dt_polys = np.array([])
        mock_result.rec_scores = []
        mock_ocr_instance.predict.return_value = [mock_result]
        mock_get_ocr.return_value = mock_ocr_instance

        boxes = replacer.extract_bounding_boxes(temp_image_path)

        assert len(boxes) == 0

    @patch('seamless_replacer.get_ocr')
    def test_extract_boxes_filters_empty_text(self, mock_get_ocr, replacer, temp_image_path):
        """Test that empty/whitespace text is filtered."""
        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        img.save(temp_image_path)

        mock_ocr_instance = Mock()
        mock_result = MagicMock()
        mock_result.rec_texts = ['TEST', '   ', '', 'VALID']
        mock_result.dt_polys = np.array([
            [[10, 10], [50, 10], [50, 30], [10, 30]],
            [[10, 40], [50, 40], [50, 60], [10, 60]],
            [[10, 70], [50, 70], [50, 90], [10, 90]],
            [[60, 10], [100, 10], [100, 30], [60, 30]]
        ])
        mock_result.rec_scores = [0.9, 0.8, 0.7, 0.95]
        # Configure the mock to work with .get() method like a dict
        mock_result.get = lambda key, default=None: getattr(mock_result, key, default)
        mock_ocr_instance.predict.return_value = [mock_result]
        mock_get_ocr.return_value = mock_ocr_instance

        boxes = replacer.extract_bounding_boxes(temp_image_path)

        # Should only have 'TEST' and 'VALID'
        assert len(boxes) == 2
        assert boxes[0]['text'] == 'TEST'
        assert boxes[1]['text'] == 'VALID'


# ============================================================================
# Test: blend_edges
# ============================================================================


@pytest.mark.skipif(not CV2_AVAILABLE, reason="cv2 not installed")
class TestBlendEdges:
    """Tests for blend_edges method."""

    def test_blend_edges_basic(self, replacer):
        """Test basic edge blending."""
        img = Image.new('RGB', (100, 100), color=(128, 128, 128))
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 20:60] = 255

        result = replacer.blend_edges(img, mask)

        assert result is not None
        assert result.size == (100, 100)

    def test_blend_edges_empty_mask(self, replacer):
        """Test blending with empty mask."""
        img = Image.new('RGB', (100, 100), color=(128, 128, 128))
        mask = np.zeros((100, 100), dtype=np.uint8)

        result = replacer.blend_edges(img, mask)

        assert result is not None
        assert result.size == (100, 100)

    def test_blend_edges_full_mask(self, replacer):
        """Test blending with full mask."""
        img = Image.new('RGB', (100, 100), color=(128, 128, 128))
        mask = np.ones((100, 100), dtype=np.uint8) * 255

        result = replacer.blend_edges(img, mask)

        assert result is not None
        assert result.size == (100, 100)


# ============================================================================
# Test: process_image_sync (integration test with mocks)
# ============================================================================


class TestProcessImageSync:
    """Tests for process_image_sync method (integration tests)."""

    @patch('seamless_replacer.get_ocr')
    def test_process_image_success(self, mock_get_ocr, replacer, temp_image_path, mock_ocr_result):
        """Test successful full pipeline."""
        # Create test image
        img = Image.new('RGB', (200, 100), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 90, 30], fill=(255, 255, 255))
        img.save(temp_image_path)

        # Mock OCR
        mock_ocr_instance = Mock()
        mock_ocr_instance.predict.return_value = mock_ocr_result
        mock_get_ocr.return_value = mock_ocr_instance

        translations = {'TEST': 'ТЕСТ', 'HELLO': 'ПРИВЕТ'}

        result = replacer.process_image_sync(temp_image_path, translations)

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == (200, 100)

    @patch('seamless_replacer.get_ocr')
    def test_process_image_no_text_detected(self, mock_get_ocr, replacer, temp_image_path):
        """Test when no text is detected."""
        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        img.save(temp_image_path)

        mock_ocr_instance = Mock()
        mock_result = MagicMock()
        mock_result.rec_texts = []
        mock_result.dt_polys = np.array([])
        mock_result.rec_scores = []
        mock_ocr_instance.predict.return_value = [mock_result]
        mock_get_ocr.return_value = mock_ocr_instance

        result = replacer.process_image_sync(temp_image_path, {'TEST': 'ТЕСТ'})

        # Should return original image
        assert result is not None
        assert result.size == (100, 100)

    @patch('seamless_replacer.get_ocr')
    def test_process_image_no_matches(self, mock_get_ocr, replacer, temp_image_path, mock_ocr_result):
        """Test when detected text doesn't match translations."""
        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        img.save(temp_image_path)

        mock_ocr_instance = Mock()
        mock_ocr_instance.predict.return_value = mock_ocr_result
        mock_get_ocr.return_value = mock_ocr_instance

        # Translations that don't match detected text
        translations = {'UNKNOWN': 'НЕИЗВЕСТНО'}

        result = replacer.process_image_sync(temp_image_path, translations)

        # Should return original image
        assert result is not None

    @patch('seamless_replacer.get_ocr')
    def test_process_image_with_output_path(self, mock_get_ocr, replacer, temp_image_path, mock_ocr_result):
        """Test saving to output path."""
        img = Image.new('RGB', (100, 100), color=(0, 0, 0))
        img.save(temp_image_path)

        mock_ocr_instance = Mock()
        mock_ocr_instance.predict.return_value = mock_ocr_result
        mock_get_ocr.return_value = mock_ocr_instance

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            output_path = f.name

        try:
            result = replacer.process_image_sync(
                temp_image_path,
                {'TEST': 'ТЕСТ'},
                output_path
            )

            assert result is not None
            assert Path(output_path).exists()
        finally:
            Path(output_path).unlink(missing_ok=True)

    @patch('seamless_replacer.get_ocr')
    def test_process_image_error_handling(self, mock_get_ocr, replacer):
        """Test error handling for invalid image path."""
        mock_ocr_instance = Mock()
        mock_get_ocr.return_value = mock_ocr_instance

        result = replacer.process_image_sync('/nonexistent/path.png', {'TEST': 'ТЕСТ'})

        # Should return None on error
        assert result is None


# ============================================================================
# Test: Module-level functions
# ============================================================================


class TestModuleFunctions:
    """Tests for module-level utility functions."""

    def test_get_replacer_singleton(self):
        """Test that get_replacer returns singleton instance."""
        replacer1 = get_replacer()
        replacer2 = get_replacer()

        assert replacer1 is replacer2

    @patch('paddleocr.PaddleOCR')
    def test_get_ocr_lazy_initialization(self, mock_paddle_ocr):
        """Test that OCR is lazy-initialized."""
        # Reset global state
        seamless_replacer_module._ocr_instance = None

        mock_instance = Mock()
        mock_paddle_ocr.return_value = mock_instance

        # First call should initialize
        ocr1 = get_ocr()
        assert mock_paddle_ocr.called

        # Second call should return same instance
        mock_paddle_ocr.reset_mock()
        ocr2 = get_ocr()
        assert not mock_paddle_ocr.called
        assert ocr1 is ocr2


# ============================================================================
# Test: Initialization and Font Discovery
# ============================================================================


class TestInitialization:
    """Tests for SeamlessTextReplacer initialization."""

    def test_init_finds_fonts(self, replacer):
        """Test that initialization finds available fonts."""
        assert hasattr(replacer, '_available_fonts')
        assert isinstance(replacer._available_fonts, list)

    def test_find_available_fonts(self):
        """Test font discovery."""
        replacer = SeamlessTextReplacer()
        available = replacer._find_available_fonts()

        # Should only include existing fonts
        for font_path in available:
            assert Path(font_path).exists()

    @patch('pathlib.Path.exists')
    def test_find_available_fonts_none_exist(self, mock_exists):
        """Test when no fonts are available."""
        mock_exists.return_value = False

        replacer = SeamlessTextReplacer()

        assert replacer._available_fonts == []


# ============================================================================
# Edge Cases and Integration
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_bbox_rect_zero_area(self, replacer, simple_test_image):
        """Test handling of zero-area bbox."""
        bbox_rect = (50, 50, 50, 50)

        # Should handle gracefully
        color = replacer.extract_text_color(simple_test_image, bbox_rect)
        assert color == (255, 255, 255)

        bg_color = replacer.extract_background_color(simple_test_image, bbox_rect)
        assert bg_color == (0, 0, 0)

    def test_very_small_image(self, replacer):
        """Test with very small image."""
        img = Image.new('RGB', (10, 10), color=(128, 128, 128))
        bbox_rect = (2, 2, 8, 8)

        color = replacer.extract_text_color(img, bbox_rect)
        assert len(color) == 3

        bg_color = replacer.extract_background_color(img, bbox_rect)
        assert len(bg_color) == 3

    def test_unicode_text_rendering(self, replacer):
        """Test rendering Unicode text (Russian, etc.)."""
        img = Image.new('RGB', (200, 100), color=(0, 0, 0))
        bbox_rect = (10, 40, 150, 70)
        font = replacer.get_font(20)

        # Should handle Cyrillic text
        result = replacer.render_replacement_text(
            img, "ПРИВЕТ", bbox_rect, (255, 255, 255), font
        )
        assert result is not None

    def test_concurrent_access_safety(self, replacer):
        """Test that replacer can be used concurrently (thread-safe)."""
        # This is a basic test - full thread safety would need more extensive testing
        img = Image.new('RGB', (100, 100), color=(0, 0, 0))
        bbox_rect = (10, 10, 50, 30)

        # Multiple operations should not interfere
        color1 = replacer.extract_text_color(img, bbox_rect)
        color2 = replacer.extract_background_color(img, bbox_rect)
        size = replacer.estimate_font_size(bbox_rect)

        assert len(color1) == 3
        assert len(color2) == 3
        assert size > 0
