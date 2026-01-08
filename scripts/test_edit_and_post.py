#!/usr/bin/env python3
"""
Test image editing and post to target group.

Usage:
    python scripts/test_edit_and_post.py
"""
import asyncio
import sys
from pathlib import Path
from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.config import config
from src.telethon_setup import get_publisher_client, init_clients


async def main():
    print("=== Test Image Edit & Post ===\n")

    # Source image (from our comparison data)
    source_image = Path("data/image_comparison/20260105_195510/13_6_B-USDT_SHORT/original_8775.jpg")
    if not source_image.exists():
        print(f"ERROR: Source image not found: {source_image}")
        return

    # Copy to media dir (security requirement)
    import shutil
    media_dir = Path(config.MEDIA_DOWNLOAD_DIR)
    media_dir.mkdir(parents=True, exist_ok=True)
    test_image = media_dir / "test_signal.jpg"
    shutil.copy(source_image, test_image)
    print(f"Source: {source_image}")
    print(f"Test image: {test_image}")

    # Check original size
    with Image.open(test_image) as img:
        orig_size = img.size
        print(f"Original size: {orig_size[0]}x{orig_size[1]}")

    # Sample translations
    translations = {
        "Идея": "Signal",
        "Продать": "Sell",
    }
    print(f"Translations: {translations}\n")

    # Initialize Telegram clients
    print("Initializing Telegram clients...")
    await init_clients()
    publisher = get_publisher_client()
    print(f"Target group: {config.TARGET_GROUP_ID}\n")

    # Edit image (use Gemini since OpenAI billing limit reached)
    print("Editing image with Gemini...")
    from src.image_editing.gemini_editor import GeminiImageEditor
    editor = GeminiImageEditor()

    output_path = media_dir / "test_signal_edited.png"
    result = editor.edit_image(str(test_image), translations, str(output_path))

    if not result.success:
        print(f"ERROR: Edit failed - {result.error}")
        return

    print(f"Edit successful!")
    print(f"Output: {output_path}")

    # Check result size
    with Image.open(output_path) as img:
        result_size = img.size
        print(f"Result size: {result_size[0]}x{result_size[1]}")

    if orig_size != result_size:
        print(f"⚠️  Size changed: {orig_size} → {result_size}")
    else:
        print("✅ Size preserved!")

    # Post to group
    print(f"\nPosting to target group...")
    test_caption = "🧪 TEST: Image editing quality check\n\nOriginal: {}x{}\nResult: {}x{}".format(
        orig_size[0], orig_size[1], result_size[0], result_size[1]
    )

    msg = await publisher.send_message(
        entity=config.TARGET_GROUP_ID,
        message=test_caption,
        file=str(output_path)
    )

    print(f"✅ Posted! Message ID: {msg.id}")

    # Cleanup
    test_image.unlink(missing_ok=True)
    output_path.unlink(missing_ok=True)
    print("\nCleanup done.")


if __name__ == "__main__":
    asyncio.run(main())
