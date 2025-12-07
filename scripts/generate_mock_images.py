#!/usr/bin/env python3
"""
Generate mock trading chart images for OCR testing.

This script creates realistic-looking trading signal images with:
- Dark background (trading chart style)
- Text overlays with trading information
- Both Russian and English text for OCR verification
- Different trading scenarios (Long/Short, various pairs)

Usage:
    python scripts/generate_mock_images.py

Output:
    Creates images in tests/data/mock_images/
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Tuple, Optional


# Configuration
OUTPUT_DIR = Path(__file__).parent.parent / "tests" / "data" / "mock_images"
IMAGE_SIZE = (800, 600)
BG_COLOR = (20, 25, 35)  # Dark background (trading chart style)
TEXT_COLOR = (220, 220, 220)  # Light text
GREEN_COLOR = (46, 204, 113)  # Profit/Long
RED_COLOR = (231, 76, 60)  # Loss/Short
YELLOW_COLOR = (241, 196, 15)  # Warning/Info

# Font paths to try (in order of preference)
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

# Trading signal configurations
SIGNALS = [
    {
        "filename": "signal_ocr_1.png",
        "exchange": "BYBIT",
        "pair": "SOLUSDT",
        "direction": "Long",
        "leverage": "20x",
        "entry": "148.50",
        "tp": "155.00",
        "sl": "145.00",
        "roi": "+4.38%",
        "status_ru": "Позиция активна",
        "status_en": "Position Active",
    },
    {
        "filename": "signal_ocr_2.png",
        "exchange": "BYBIT",
        "pair": "BTCUSDT",
        "direction": "Short",
        "leverage": "10x",
        "entry": "63500",
        "tp": "61000",
        "sl": "65000",
        "roi": "+3.15%",
        "status_ru": "Прибыль зафиксирована",
        "status_en": "Profit Taken",
    },
    {
        "filename": "signal_ocr_3.png",
        "exchange": "BYBIT",
        "pair": "ETHUSDT",
        "direction": "Long",
        "leverage": "15x",
        "entry": "2450",
        "tp": "2600",
        "sl": "2380",
        "roi": None,
        "status_ru": "Сигнал открыт",
        "status_en": "Signal Open",
    },
]


def load_font(size: int = 20) -> ImageFont.ImageFont:
    """
    Load a TrueType font with fallback to default font.

    Args:
        size: Font size in points

    Returns:
        ImageFont object
    """
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                print(f"Warning: Could not load font {font_path}: {e}")
                continue

    # Fallback to default font
    print("Warning: Using default font (no TrueType fonts found)")
    return ImageFont.load_default()


def draw_grid(draw: ImageDraw.ImageDraw, width: int, height: int):
    """
    Draw a decorative grid pattern to simulate a trading chart.

    Args:
        draw: ImageDraw object
        width: Image width
        height: Image height
    """
    grid_color = (35, 40, 50)  # Slightly lighter than background

    # Horizontal lines
    for y in range(0, height, 60):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # Vertical lines
    for x in range(0, width, 80):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)


def draw_signal_header(
    draw: ImageDraw.ImageDraw,
    font_large: ImageFont.ImageFont,
    font_medium: ImageFont.ImageFont,
    signal: Dict,
    width: int
):
    """
    Draw the header section with exchange, pair, direction, and leverage.

    Args:
        draw: ImageDraw object
        font_large: Large font for pair
        font_medium: Medium font for other text
        signal: Signal configuration dictionary
        width: Image width
    """
    y_offset = 20

    # Exchange name (top left)
    draw.text((20, y_offset), signal["exchange"], fill=TEXT_COLOR, font=font_medium)

    # Pair (center, large)
    pair_bbox = draw.textbbox((0, 0), signal["pair"], font=font_large)
    pair_width = pair_bbox[2] - pair_bbox[0]
    pair_x = (width - pair_width) // 2
    draw.text((pair_x, y_offset + 40), signal["pair"], fill=TEXT_COLOR, font=font_large)

    # Direction (with color)
    direction_color = GREEN_COLOR if signal["direction"] == "Long" else RED_COLOR
    direction_text = f"{signal['direction']} {signal['leverage']}"
    dir_bbox = draw.textbbox((0, 0), direction_text, font=font_large)
    dir_width = dir_bbox[2] - dir_bbox[0]
    dir_x = (width - dir_width) // 2
    draw.text((dir_x, y_offset + 90), direction_text, fill=direction_color, font=font_large)


def draw_signal_body(
    draw: ImageDraw.ImageDraw,
    font_medium: ImageFont.ImageFont,
    signal: Dict,
    width: int,
    height: int
):
    """
    Draw the body section with entry, TP, SL, and ROI.

    Args:
        draw: ImageDraw object
        font_medium: Medium font
        signal: Signal configuration dictionary
        width: Image width
        height: Image height
    """
    y_start = height // 2 + 20
    line_spacing = 50

    # Entry price
    entry_text = f"Entry: {signal['entry']}"
    draw.text((50, y_start), entry_text, fill=TEXT_COLOR, font=font_medium)

    # Take Profit
    tp_text = f"TP: {signal['tp']}"
    draw.text((50, y_start + line_spacing), tp_text, fill=GREEN_COLOR, font=font_medium)

    # Stop Loss
    sl_text = f"SL: {signal['sl']}"
    draw.text((50, y_start + line_spacing * 2), sl_text, fill=RED_COLOR, font=font_medium)

    # ROI (if available)
    if signal["roi"]:
        roi_color = GREEN_COLOR if "+" in signal["roi"] else RED_COLOR
        roi_text = f"ROI: {signal['roi']}"
        roi_bbox = draw.textbbox((0, 0), roi_text, font=font_medium)
        roi_width = roi_bbox[2] - roi_bbox[0]
        roi_x = width - roi_width - 50
        draw.text((roi_x, y_start + line_spacing), roi_text, fill=roi_color, font=font_medium)


def draw_signal_footer(
    draw: ImageDraw.ImageDraw,
    font_medium: ImageFont.ImageFont,
    font_small: ImageFont.ImageFont,
    signal: Dict,
    width: int,
    height: int
):
    """
    Draw the footer section with status in Russian and English.

    Args:
        draw: ImageDraw object
        font_medium: Medium font
        font_small: Small font
        signal: Signal configuration dictionary
        width: Image width
        height: Image height
    """
    y_footer = height - 100

    # Russian status
    ru_text = signal["status_ru"]
    ru_bbox = draw.textbbox((0, 0), ru_text, font=font_medium)
    ru_width = ru_bbox[2] - ru_bbox[0]
    ru_x = (width - ru_width) // 2
    draw.text((ru_x, y_footer), ru_text, fill=YELLOW_COLOR, font=font_medium)

    # English status
    en_text = signal["status_en"]
    en_bbox = draw.textbbox((0, 0), en_text, font=font_small)
    en_width = en_bbox[2] - en_bbox[0]
    en_x = (width - en_width) // 2
    draw.text((en_x, y_footer + 35), en_text, fill=TEXT_COLOR, font=font_small)


def generate_signal_image(signal: Dict, output_path: Path):
    """
    Generate a single mock trading signal image.

    Args:
        signal: Signal configuration dictionary
        output_path: Path where the image will be saved
    """
    width, height = IMAGE_SIZE

    # Create image with dark background
    img = Image.new("RGB", IMAGE_SIZE, color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Load fonts
    font_large = load_font(48)
    font_medium = load_font(24)
    font_small = load_font(18)

    # Draw components
    draw_grid(draw, width, height)
    draw_signal_header(draw, font_large, font_medium, signal, width)
    draw_signal_body(draw, font_medium, signal, width, height)
    draw_signal_footer(draw, font_medium, font_small, signal, width, height)

    # Save image
    img.save(output_path)
    print(f"✓ Generated: {output_path}")


def main():
    """
    Main function to generate all mock trading signal images.
    """
    print("=" * 80)
    print("Generating Mock Trading Chart Images for OCR Testing")
    print("=" * 80)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {OUTPUT_DIR.absolute()}")

    # Generate each signal image
    print(f"\nGenerating {len(SIGNALS)} images...\n")

    for signal in SIGNALS:
        output_path = OUTPUT_DIR / signal["filename"]
        try:
            generate_signal_image(signal, output_path)
        except Exception as e:
            print(f"✗ Error generating {signal['filename']}: {e}")
            sys.exit(1)

    print("\n" + "=" * 80)
    print("✓ All images generated successfully!")
    print("=" * 80)
    print(f"\nImages saved to: {OUTPUT_DIR.absolute()}")
    print("\nGenerated files:")
    for signal in SIGNALS:
        filepath = OUTPUT_DIR / signal["filename"]
        if filepath.exists():
            size_kb = filepath.stat().st_size / 1024
            print(f"  - {signal['filename']} ({size_kb:.1f} KB)")
    print("\nYou can now use these images for OCR testing.")


if __name__ == "__main__":
    main()
