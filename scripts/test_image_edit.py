#!/usr/bin/env python3
"""
Test image editing with updated prompts.

Usage:
    python scripts/test_image_edit.py [--provider openai|gemini]
"""
import asyncio
import os
import sys
from pathlib import Path
from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def main():
    provider = "openai"
    if "--provider" in sys.argv:
        idx = sys.argv.index("--provider")
        if len(sys.argv) > idx + 1:
            provider = sys.argv[idx + 1]

    print(f"Testing {provider} image editor with new prompts\n")

    # Test image must be in /tmp/signals (MEDIA_DOWNLOAD_DIR)
    original_path = Path("/tmp/signals/original_8775.jpg")
    if not original_path.exists():
        print("ERROR: Test image not found at /tmp/signals/original_8775.jpg")
        print("Copy a test image first: cp data/image_comparison/.../*.jpg /tmp/signals/")
        return
    print(f"Original image: {original_path}")

    # Check original size
    with Image.open(original_path) as img:
        orig_size = img.size
        print(f"Original size: {orig_size[0]}x{orig_size[1]}")

    # Sample translations for testing
    translations = {
        "Продать": "Sell",
        "Покупать": "Buy",
    }
    print(f"Translations: {translations}")

    # Create editor
    if provider == "openai":
        from src.image_editing.openai_editor import OpenAIImageEditor
        editor = OpenAIImageEditor()
    else:
        from src.image_editing.gemini_editor import GeminiImageEditor
        editor = GeminiImageEditor()

    # Show prompt
    prompt = editor._build_prompt(translations)
    print(f"\nGenerated prompt ({len(prompt)} chars):")
    print("-" * 40)
    print(prompt)
    print("-" * 40)

    # Setup output
    output_dir = Path("data/test_output")
    output_dir.mkdir(exist_ok=True)
    result_file = output_dir / f"edited_{provider}_{original_path.stem}.png"

    # Edit image - uses file path, not bytes (must be absolute)
    print(f"\nCalling {provider} API...")
    try:
        result = editor.edit_image(str(original_path.resolve()), translations, str(result_file.resolve()))
        if result.success and result.edited_image:
            print(f"Result saved to: {result_file}")

            # Check result size
            with Image.open(result_file) as img:
                result_size = img.size
                print(f"Result size: {result_size[0]}x{result_size[1]}")

            # Compare
            if orig_size == result_size:
                print("\n✅ SIZE PRESERVED - aspect ratio maintained!")
            else:
                ratio_orig = orig_size[0] / orig_size[1]
                ratio_result = result_size[0] / result_size[1]
                print(f"\n⚠️  Size changed: {orig_size} -> {result_size}")
                print(f"   Aspect ratio: {ratio_orig:.3f} -> {ratio_result:.3f}")
                if abs(ratio_orig - ratio_result) < 0.05:
                    print("   Aspect ratio approximately preserved")
                else:
                    print("   ❌ ASPECT RATIO CHANGED!")
        else:
            print(f"Edit failed: {result.error}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
