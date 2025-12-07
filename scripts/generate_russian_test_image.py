#!/usr/bin/env python3
"""Generate a test image with ONLY Russian text for Nano Banana Pro testing."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import os

OUTPUT_PATH = Path(__file__).parent.parent / "tests" / "data" / "mock_images" / "signal_russian_only.png"
IMAGE_SIZE = (800, 600)
BG_COLOR = (20, 25, 35)
TEXT_COLOR = (220, 220, 220)
GREEN_COLOR = (46, 204, 113)
RED_COLOR = (231, 76, 60)
YELLOW_COLOR = (241, 196, 15)

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def load_font(size: int = 20):
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def main():
    img = Image.new("RGB", IMAGE_SIZE, color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_large = load_font(40)
    font_medium = load_font(28)
    font_small = load_font(20)

    width, height = IMAGE_SIZE

    # Grid
    grid_color = (35, 40, 50)
    for y in range(0, height, 60):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)
    for x in range(0, width, 80):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)

    # Header - ALL RUSSIAN
    draw.text((20, 20), "БАЙБИТ", fill=TEXT_COLOR, font=font_medium)

    pair_text = "БТК/ЮСДТ"
    pair_bbox = draw.textbbox((0, 0), pair_text, font=font_large)
    pair_x = (width - (pair_bbox[2] - pair_bbox[0])) // 2
    draw.text((pair_x, 60), pair_text, fill=TEXT_COLOR, font=font_large)

    direction_text = "ЛОНГ 20x"
    dir_bbox = draw.textbbox((0, 0), direction_text, font=font_large)
    dir_x = (width - (dir_bbox[2] - dir_bbox[0])) // 2
    draw.text((dir_x, 120), direction_text, fill=GREEN_COLOR, font=font_large)

    # Body - ALL RUSSIAN
    y_start = 220
    line_spacing = 50

    draw.text((50, y_start), "Вход: 65500 - 66000", fill=TEXT_COLOR, font=font_medium)
    draw.text((50, y_start + line_spacing), "Тейк 1: 68000", fill=GREEN_COLOR, font=font_medium)
    draw.text((50, y_start + line_spacing * 2), "Тейк 2: 70000", fill=GREEN_COLOR, font=font_medium)
    draw.text((50, y_start + line_spacing * 3), "Стоп: 64000", fill=RED_COLOR, font=font_medium)

    # ROI
    roi_text = "Прибыль: +5.2%"
    roi_bbox = draw.textbbox((0, 0), roi_text, font=font_medium)
    roi_x = width - (roi_bbox[2] - roi_bbox[0]) - 50
    draw.text((roi_x, y_start + line_spacing), roi_text, fill=GREEN_COLOR, font=font_medium)

    # Footer - ALL RUSSIAN
    y_footer = height - 100

    status_text = "Сигнал активен"
    status_bbox = draw.textbbox((0, 0), status_text, font=font_medium)
    status_x = (width - (status_bbox[2] - status_bbox[0])) // 2
    draw.text((status_x, y_footer), status_text, fill=YELLOW_COLOR, font=font_medium)

    risk_text = "Риск: 2% от депозита"
    risk_bbox = draw.textbbox((0, 0), risk_text, font=font_small)
    risk_x = (width - (risk_bbox[2] - risk_bbox[0])) // 2
    draw.text((risk_x, y_footer + 40), risk_text, fill=TEXT_COLOR, font=font_small)

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT_PATH)
    print(f"Generated: {OUTPUT_PATH}")
    print(f"Size: {OUTPUT_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
