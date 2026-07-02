#!/usr/bin/env python3
"""
Full pipeline: Ingest -> Structure -> Store for a video ID.
Usage: python pipeline.py <video_id> [video_id2 ...]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fetch_transcript import fetch_transcript
from structure_transcript import structure_transcript
from store_db import init_db, load_structured

def run_pipeline(video_id):
    print(f"\n{'='*50}")
    print(f"Processing: {video_id}")
    print(f"{'='*50}")
    
    # Phase 1: Ingest
    print("\n[Phase 1] Fetching transcript...")
    raw_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
    raw_path = os.path.join(raw_dir, f'{video_id}.json')
    
    if os.path.exists(raw_path):
        print(f"  Already fetched: {raw_path}")
    else:
        fetch_transcript(video_id)
    
    # Phase 2: Structure
    print("\n[Phase 2] Structuring transcript...")
    structured_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'structured')
    structured_path = os.path.join(structured_dir, f'{video_id}.json')
    
    # Add indices to raw data
    import json
    with open(raw_path) as f:
        d = json.load(f)
    for i, s in enumerate(d["segments"]):
        s["_idx"] = i
    with open(raw_path, 'w') as f:
        json.dump(d, f, indent=2)
    
    structure_transcript(raw_path, structured_path)
    
    # Phase 3: Store
    print("\n[Phase 3] Loading into database...")
    db_path = os.path.join(os.path.dirname(__file__), '..', 'db', 'parker.db')
    conn = init_db(db_path)
    load_structured(structured_path, conn)
    conn.close()
    
    print(f"\nDone! Search with: parker-search '<query>'")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <video_id> [video_id2 ...]")
        sys.exit(1)
    
    for vid in sys.argv[1:]:
        run_pipeline(vid)
