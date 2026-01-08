#!/usr/bin/env python3
"""
Download and compare original vs translated images for last N signals.

Usage:
    python scripts/compare_images.py [--limit 20]
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    limit = 20
    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        if len(sys.argv) > idx + 1:
            limit = int(sys.argv[idx + 1])

    # Create output directory
    output_dir = Path("data/image_comparison")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = output_dir / timestamp
    session_dir.mkdir(exist_ok=True)

    print(f"Output directory: {session_dir}")
    print(f"Fetching last {limit} translated signals...\n")

    # Load from JSON export (faster than DB connection)
    import json
    json_path = Path("data/production_export.json")
    if not json_path.exists():
        print("ERROR: data/production_export.json not found!")
        print("Run: python scripts/extract_production_data.py first")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loaded export from: {data.get('exported_at', 'unknown')}")

    # Filter and sort signals
    all_signals = data.get('signals', [])
    signals = [
        s for s in all_signals
        if s.get('status') == 'POSTED' and s.get('target_message_id')
    ]
    signals = sorted(signals, key=lambda x: x.get('created_at', ''), reverse=True)[:limit]

    print(f"Found {len(signals)} posted signals\n")

    if not signals:
        print("No signals found!")
        conn.close()
        return

    # Connect Telegram clients
    reader = TelegramClient(
        StringSession(os.getenv('READER_SESSION_STRING')),
        int(os.getenv('READER_API_ID')),
        os.getenv('READER_API_HASH')
    )
    await reader.start()
    print("Reader client connected")

    publisher = TelegramClient(
        StringSession(os.getenv('PUBLISHER_SESSION_STRING')),
        int(os.getenv('PUBLISHER_API_ID')),
        os.getenv('PUBLISHER_API_HASH')
    )
    await publisher.start()
    print("Publisher client connected\n")

    source_group = int(os.getenv('SOURCE_GROUP_ID'))
    target_group = int(os.getenv('TARGET_GROUP_ID'))

    # Create index file
    index_lines = ["# Image Comparison Report", f"Generated: {timestamp}", f"Total signals: {len(signals)}", ""]

    downloaded = 0
    skipped = 0
    errors = []

    for i, signal in enumerate(signals):
        sig_id = signal['id']
        src_msg_id = signal['source_message_id']
        tgt_msg_id = signal['target_message_id']
        pair = signal.get('pair') or 'UNKNOWN'
        direction = signal.get('direction') or ''

        print(f"[{i+1}/{len(signals)}] Signal {sig_id}: {pair} {direction}")
        print(f"  Source msg: {src_msg_id} -> Target msg: {tgt_msg_id}")

        # Create signal directory (sanitize pair name - remove slashes)
        safe_pair = pair.replace('/', '-')
        sig_dir = session_dir / f"{i+1:02d}_{sig_id}_{safe_pair}_{direction}"
        sig_dir.mkdir(exist_ok=True)

        original_path = None
        translated_path = None

        # Download original image from source group
        try:
            src_msg = await reader.get_messages(source_group, ids=src_msg_id)
            if src_msg and src_msg.media:
                original_path = sig_dir / f"original_{src_msg_id}.jpg"
                await reader.download_media(src_msg, file=str(original_path))
                print(f"  Downloaded original: {original_path.name}")
            else:
                print(f"  No media in source message")
        except Exception as e:
            print(f"  ERROR downloading original: {e}")
            errors.append(f"Signal {sig_id}: original download failed - {e}")

        # Download translated image from target group
        try:
            tgt_msg = await publisher.get_messages(target_group, ids=tgt_msg_id)
            if tgt_msg and tgt_msg.media:
                translated_path = sig_dir / f"translated_{tgt_msg_id}.jpg"
                await publisher.download_media(tgt_msg, file=str(translated_path))
                print(f"  Downloaded translated: {translated_path.name}")
            else:
                print(f"  No media in target message")
        except Exception as e:
            print(f"  ERROR downloading translated: {e}")
            errors.append(f"Signal {sig_id}: translated download failed - {e}")

        # Save signal metadata
        meta_path = sig_dir / "metadata.txt"
        with open(meta_path, 'w', encoding='utf-8') as f:
            f.write(f"Signal ID: {sig_id}\n")
            f.write(f"Pair: {pair}\n")
            f.write(f"Direction: {direction}\n")
            f.write(f"Created: {signal['created_at']}\n")
            f.write(f"Source message ID: {src_msg_id}\n")
            f.write(f"Target message ID: {tgt_msg_id}\n")
            f.write(f"\n--- ORIGINAL TEXT ---\n{signal.get('original_text', 'N/A')}\n")
            f.write(f"\n--- TRANSLATED TEXT ---\n{signal.get('translated_text', 'N/A')}\n")

        # Update index
        orig_status = "OK" if original_path and original_path.exists() else "MISSING"
        trans_status = "OK" if translated_path and translated_path.exists() else "MISSING"
        index_lines.append(f"## {i+1}. Signal {sig_id} - {pair} {direction}")
        index_lines.append(f"- Original: {orig_status}")
        index_lines.append(f"- Translated: {trans_status}")

        # Check image dimensions if both exist
        if original_path and original_path.exists() and translated_path and translated_path.exists():
            from PIL import Image
            try:
                orig_img = Image.open(original_path)
                trans_img = Image.open(translated_path)
                orig_size = orig_img.size
                trans_size = trans_img.size
                index_lines.append(f"- Original size: {orig_size[0]}x{orig_size[1]}")
                index_lines.append(f"- Translated size: {trans_size[0]}x{trans_size[1]}")
                if orig_size != trans_size:
                    index_lines.append(f"- **SIZE MISMATCH!**")
                    print(f"  SIZE MISMATCH: {orig_size} -> {trans_size}")
                orig_img.close()
                trans_img.close()
            except Exception as e:
                index_lines.append(f"- Size check error: {e}")

        index_lines.append("")

        if original_path or translated_path:
            downloaded += 1
        else:
            skipped += 1

        print()

    # Write index file
    index_path = session_dir / "README.md"
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(index_lines))

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total signals: {len(signals)}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (no media): {skipped}")
    print(f"Errors: {len(errors)}")
    print(f"\nOutput: {session_dir}")
    print(f"Index: {index_path}")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e}")

    # Disconnect
    await reader.disconnect()
    await publisher.disconnect()

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
