#!/usr/bin/env python3
"""Test PaddleOCR detection on Russian trading signal images.

Usage:
    python scripts/test_paddleocr.py

    or with venv:
    venv/bin/python scripts/test_paddleocr.py
"""

from pathlib import Path
from paddleocr import PaddleOCR
import json

def main():
    # Initialize PaddleOCR with Russian support
    # Note: use_textline_orientation replaces deprecated use_angle_cls
    ocr = PaddleOCR(use_textline_orientation=True, lang='ru')

    # Test image path
    test_image = Path(__file__).parent.parent / "tests/data/mock_images/signal_russian_only.png"

    if not test_image.exists():
        print(f"ERROR: Test image not found: {test_image}")
        return 1

    print(f"Testing PaddleOCR on: {test_image}")
    print("-" * 60)

    # Run OCR
    # Note: predict() replaces deprecated ocr() method
    result = ocr.predict(str(test_image))

    if not result or not result[0]:
        print("ERROR: No text detected!")
        return 1

    # Get OCRResult object
    ocr_result = result[0]

    # Extract results from OCRResult object
    texts = ocr_result['rec_texts']
    scores = ocr_result['rec_scores']
    det_polys = ocr_result['rec_polys']

    if not texts:
        print("ERROR: No text detected!")
        return 1

    # Print results
    print(f"Detected {len(texts)} text elements:\n")

    for i, (text, confidence, bbox) in enumerate(zip(texts, scores, det_polys)):
        # bbox is a 4-point polygon [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        # Convert to rect format (x1, y1, x2, y2)
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        rect = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))

        print(f"{i+1:2}. [{confidence:.2f}] '{text}'")
        print(f"    BBox: {rect}")
        print()

    print("-" * 60)
    print(f"SUCCESS: Detected {len(texts)} text elements")
    return 0

if __name__ == "__main__":
    exit(main())
