#!/usr/bin/env python3
"""Phase 1: Ingest - Fetch YouTube transcript and video metadata to raw JSON.

Usage:
    python3 fetch_transcript.py <video_url_or_id> [--output DIR]
    python3 fetch_transcript.py --batch <file_with_urls> [--output DIR]
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(url_or_id):
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for pat in patterns:
        m = re.search(pat, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url_or_id}")


def fetch_video_metadata(video_id):
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return {
                "title": data.get("title", ""),
                "author": data.get("author_name", ""),
                "author_url": data.get("author_url", ""),
            }
    except Exception as e:
        print(f"  Warning: could not fetch metadata: {e}", file=sys.stderr)
        return {"title": "", "author": "", "author_url": ""}


def fetch_transcript(video_id):
    print(f"Fetching transcript for {video_id}...")
    meta = fetch_video_metadata(video_id)

    try:
        api = YouTubeTranscriptApi()
        result = api.fetch(video_id)
        raw_segments = result.to_raw_data()
        is_generated = result.is_generated
    except Exception as e:
        print(f"  Error fetching transcript: {e}", file=sys.stderr)
        return None

    record = {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": meta["title"],
        "author": meta["author"],
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "is_auto_generated": is_generated,
        "segment_count": len(raw_segments),
        "total_duration_sec": round(raw_segments[-1]["start"] + raw_segments[-1]["duration"]) if raw_segments else 0,
        "segments": raw_segments,
    }

    total_mins = record["total_duration_sec"] // 60
    print(f"  Got {len(raw_segments)} segments, ~{total_mins} min, auto_generated={is_generated}")
    return record


def save_record(record, output_dir):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{record['video_id']}.json"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube transcripts")
    parser.add_argument("video", nargs="?", help="Video URL or ID")
    parser.add_argument("--batch", help="File with one URL/ID per line")
    parser.add_argument("--output", default="./data/raw", help="Output directory")
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
            vid = extract_video_id(v)
            record = fetch_transcript(vid)
            if record:
                save_record(record, args.output)
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  FAILED {v}: {e}", file=sys.stderr)
            failed += 1

    print(f"\nDone: {success} fetched, {failed} failed")


if __name__ == "__main__":
    main()
