"""Batch-fetch YouTube caption dumps for a channel's VODs.

Reads data/derived/vod_inventory.json (from yt-dlp --flat-playlist -J),
fetches captions for each video via youtube-transcript-api, and writes
data/raw/captions/{vid}.json in the same schema as the existing data/raw
dumps (video_id, title, author, is_auto_generated, segments[...]) so
scripts/extract_ages.py can consume them unchanged.

Resume-aware: skips videos already fetched. Failures are logged to
data/raw/captions/_failures.json so a re-run can retry just those.

Usage:
    python scripts/fetch_vod_captions.py [--limit N] [--only-failed] [--delay 1.5]
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

OUT_DIR = Path("data/raw/captions")
FAIL_LOG = OUT_DIR / "_failures.json"


def load_failures() -> dict:
    if FAIL_LOG.exists():
        return json.loads(FAIL_LOG.read_text())
    return {}


def save_failures(fails: dict) -> None:
    FAIL_LOG.write_text(json.dumps(fails, indent=1))


def fetch_one(vid: str, api) -> dict:
    from youtube_transcript_api import YouTubeTranscriptApi

    if api is None:
        api = YouTubeTranscriptApi()
    t = api.fetch(vid, languages=["en"])
    segs = [
        {"start": s.start, "end": s.start + getattr(s, "duration", 0) or 0, "text": s.text}
        for s in t.snippets
    ]
    return {
        "video_id": vid,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_auto_generated": True,
        "segment_count": len(segs),
        "segments": segs,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="max videos this run")
    ap.add_argument("--only-failed", action="store_true", help="retry logged failures")
    ap.add_argument("--delay", type=float, default=1.5)
    args = ap.parse_args()

    inventory = json.loads(Path("data/derived/vod_inventory.json").read_text())
    fails = load_failures()

    if args.only_failed:
        targets = [(e["id"], e.get("title")) for e in inventory if e["id"] in fails]
    else:
        targets = [(e["id"], e.get("title")) for e in inventory]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = skipped = err = 0
    for i, (vid, title) in enumerate(targets):
        out = OUT_DIR / f"{vid}.json"
        if out.exists():
            skipped += 1
            continue
        if args.limit and done >= args.limit:
            break
        try:
            dump = fetch_one(vid, None)
            dump["title"] = title
            out.write_text(json.dumps(dump))
            fails.pop(vid, None)
            done += 1
            if done % 25 == 0:
                save_failures(fails)
                print(f"[{i + 1}/{len(targets)}] ok={done} skip={skipped} err={err}", flush=True)
            time.sleep(args.delay)
        except Exception as e:  # noqa: BLE001 - log every failure type
            err += 1
            fails[vid] = {"error": str(e)[:200], "at": datetime.now(timezone.utc).isoformat()}
            print(f"ERR {vid}: {str(e)[:100]}", flush=True)
            time.sleep(max(args.delay, 4.0))  # back off harder after errors

    save_failures(fails)
    print(f"\nDONE: fetched={done} skipped(existing)={skipped} errors={err}")
    print(f"failure log: {FAIL_LOG} ({len(fails)} pending)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
