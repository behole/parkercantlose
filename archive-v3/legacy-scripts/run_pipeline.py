#!/usr/bin/env python3
"""Pipeline runner - single command to ingest, structure, store, and export.

Usage:
    python3 run_pipeline.py <video_url_or_id>
    python3 run_pipeline.py --batch urls.txt
    python3 run_pipeline.py --reprocess  (re-structure and re-store all raw files)
"""

import argparse
import sys
import os

# Add project dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_transcript import extract_video_id, fetch_transcript, save_record
from structure_transcript import structure_transcript
from store import init_db, load_structured, DB_PATH
from obsidian_export import generate_note, VAULT_PATH


def process_video(url_or_id, raw_dir="./data/raw", struct_dir="./data/structured",
                  db_path=DB_PATH, vault_path=VAULT_PATH):
    """Run full pipeline for a single video."""
    vid = extract_video_id(url_or_id)
    print("\n" + "=" * 60)
    print("Processing: %s" % vid)
    print("=" * 60)

    # Phase 1: Ingest
    raw_path = os.path.join(raw_dir, "%s.json" % vid)
    if os.path.exists(raw_path):
        print("\n[Phase 1] Raw transcript already exists, skipping fetch")
    else:
        print("\n[Phase 1] Fetching transcript...")
        record = fetch_transcript(vid)
        if not record:
            print("FAILED: Could not fetch transcript for %s" % vid)
            return False
        save_record(record, raw_dir)

    # Phase 2: Structure
    struct_path = os.path.join(struct_dir, "%s.structured.json" % vid)
    print("\n[Phase 2] Structuring transcript...")
    structure_transcript(raw_path, struct_dir)

    # Phase 3: Store
    print("\n[Phase 3] Loading into database...")
    conn = init_db(db_path)
    load_structured(conn, struct_path)

    # Phase 5: Obsidian
    print("\n[Phase 5] Generating Obsidian note...")
    generate_note(conn, vid, vault_path)

    conn.close()
    print("\nDone: %s" % vid)
    return True


def main():
    parser = argparse.ArgumentParser(description="Run full Parker pipeline")
    parser.add_argument("video", nargs="?", help="Video URL or ID")
    parser.add_argument("--batch", help="File with one URL/ID per line")
    parser.add_argument("--vault", default=VAULT_PATH, help="Obsidian vault path")
    parser.add_argument("--db", default=DB_PATH, help="Database path")
    args = parser.parse_args()

    if not args.video and not args.batch:
        parser.print_help()
        sys.exit(1)

    videos = []
    if args.batch:
        with open(args.batch) as f:
            videos = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        videos = [args.video]

    success = 0
    failed = 0
    for v in videos:
        try:
            if process_video(v, vault_path=args.vault, db_path=args.db):
                success += 1
            else:
                failed += 1
        except Exception as e:
            print("ERROR processing %s: %s" % (v, e))
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print("Pipeline complete: %d success, %d failed" % (success, failed))


if __name__ == "__main__":
    main()
