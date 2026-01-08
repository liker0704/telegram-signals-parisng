#!/usr/bin/env python3
"""Extract production data from Supabase for analysis."""

import psycopg2
import json
from datetime import datetime

DATABASE_URL = "postgresql://postgres.iqpxsucflhyhkkjupuiq:4KyDJdPdD.Egssu@aws-1-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require"


def main():
    print("=" * 60)
    print("SUPABASE PRODUCTION DATA EXTRACTION")
    print("=" * 60)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Get table list
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [t[0] for t in cur.fetchall()]

    print("\n=== TABLES ===")
    for t in tables:
        print("  -", t)

    # Count records
    print("\n=== RECORD COUNTS ===")
    for t in tables:
        try:
            cur.execute("SELECT COUNT(*) FROM " + t)
            count = cur.fetchone()[0]
            print("  {}: {} records".format(t, count))
        except Exception as e:
            print("  {}: ERROR - {}".format(t, e))

    # Extract signals data
    print("\n=== SIGNALS DATA ===")
    cur.execute("""
        SELECT
            id,
            source_message_id,
            pair,
            direction,
            status,
            created_at,
            processed_at,
            error_message,
            LENGTH(original_text) as original_len,
            LENGTH(translated_text) as translated_len,
            image_local_path IS NOT NULL as has_image,
            image_ocr_text IS NOT NULL as has_ocr
        FROM signals
        ORDER BY created_at DESC
        LIMIT 50
    """)

    columns = [desc[0] for desc in cur.description]
    signals = cur.fetchall()

    print("Found {} signals (showing last 50)".format(len(signals)))
    print("\nColumns:", columns)
    print("\n--- SIGNALS LIST ---")

    for s in signals:
        signal_dict = dict(zip(columns, s))
        print("\nSignal ID: {}".format(signal_dict['id']))
        print("  Status: {}".format(signal_dict['status']))
        print("  Pair: {}".format(signal_dict['pair']))
        print("  Direction: {}".format(signal_dict['direction']))
        print("  Created: {}".format(signal_dict['created_at']))
        print("  Processed: {}".format(signal_dict['processed_at']))
        print("  Has Image: {}".format(signal_dict['has_image']))
        print("  Has OCR: {}".format(signal_dict['has_ocr']))
        print("  Original text len: {}".format(signal_dict['original_len']))
        print("  Translated text len: {}".format(signal_dict['translated_len']))
        if signal_dict['error_message']:
            print("  ERROR: {}".format(signal_dict['error_message'][:100]))

    # Extract signal_updates data
    print("\n=== SIGNAL UPDATES ===")
    cur.execute("""
        SELECT
            id,
            signal_id,
            status,
            created_at,
            processed_at,
            error_message,
            LENGTH(original_text) as original_len,
            LENGTH(translated_text) as translated_len,
            image_local_path IS NOT NULL as has_image
        FROM signal_updates
        ORDER BY created_at DESC
        LIMIT 30
    """)

    columns = [desc[0] for desc in cur.description]
    updates = cur.fetchall()

    print("Found {} updates (showing last 30)".format(len(updates)))

    for u in updates:
        update_dict = dict(zip(columns, u))
        print("\nUpdate ID: {} (Signal: {})".format(update_dict['id'], update_dict['signal_id']))
        print("  Status: {}".format(update_dict['status']))
        print("  Created: {}".format(update_dict['created_at']))
        print("  Has Image: {}".format(update_dict['has_image']))
        if update_dict['error_message']:
            print("  ERROR: {}".format(update_dict['error_message'][:100]))

    # Statistics
    print("\n" + "=" * 60)
    print("STATISTICS")
    print("=" * 60)

    # Status breakdown
    cur.execute("""
        SELECT status, COUNT(*)
        FROM signals
        GROUP BY status
    """)
    print("\nSignals by status:")
    for row in cur.fetchall():
        print("  {}: {}".format(row[0], row[1]))

    # Image processing stats
    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN image_local_path IS NOT NULL THEN 1 ELSE 0 END) as with_image,
            SUM(CASE WHEN image_ocr_text IS NOT NULL THEN 1 ELSE 0 END) as with_ocr
        FROM signals
    """)
    row = cur.fetchone()
    print("\nImage processing:")
    print("  Total signals: {}".format(row[0]))
    print("  With images: {}".format(row[1]))
    print("  With OCR text: {}".format(row[2]))

    # Error analysis
    cur.execute("""
        SELECT error_message, COUNT(*)
        FROM signals
        WHERE error_message IS NOT NULL
        GROUP BY error_message
    """)
    errors = cur.fetchall()
    if errors:
        print("\nErrors breakdown:")
        for row in errors:
            print("  {} - count: {}".format(row[0][:80] if row[0] else 'NULL', row[1]))

    # Export full data to JSON
    print("\n=== EXPORTING FULL DATA TO JSON ===")
    from decimal import Decimal

    def serialize(val):
        if isinstance(val, datetime):
            return val.isoformat()
        if isinstance(val, Decimal):
            return float(val)
        return val

    cur.execute("SELECT * FROM signals ORDER BY created_at DESC")
    columns = [desc[0] for desc in cur.description]
    signals_full = []
    for row in cur.fetchall():
        d = {}
        for i, col in enumerate(columns):
            d[col] = serialize(row[i])
        signals_full.append(d)

    cur.execute("SELECT * FROM signal_updates ORDER BY created_at DESC")
    columns = [desc[0] for desc in cur.description]
    updates_full = []
    for row in cur.fetchall():
        d = {}
        for i, col in enumerate(columns):
            d[col] = serialize(row[i])
        updates_full.append(d)

    cur.execute("SELECT * FROM translation_cache ORDER BY created_at DESC")
    columns = [desc[0] for desc in cur.description]
    cache_full = []
    for row in cur.fetchall():
        d = {}
        for i, col in enumerate(columns):
            d[col] = serialize(row[i])
        cache_full.append(d)

    export_data = {
        "exported_at": datetime.now().isoformat(),
        "signals": signals_full,
        "signal_updates": updates_full,
        "translation_cache": cache_full
    }

    with open("data/production_export.json", "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print("Exported to data/production_export.json")
    print("  Signals: {}".format(len(signals_full)))
    print("  Updates: {}".format(len(updates_full)))
    print("  Cache entries: {}".format(len(cache_full)))

    # Show sample translations
    print("\n=== SAMPLE TRANSLATIONS ===")
    for s in signals_full[:3]:
        print("\n--- Signal {} ({}) ---".format(s['id'], s['pair']))
        print("ORIGINAL:")
        print(s.get('original_text', 'N/A')[:500])
        print("\nTRANSLATED:")
        print(s.get('translated_text', 'N/A')[:500])

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
