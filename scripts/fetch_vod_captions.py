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
YTDLP = Path.home() / ".hermes/hermes-agent/venv/bin/yt-dlp"


def fetch_via_ytdlp(vid: str) -> dict:
    """Fallback: pull auto-subs via yt-dlp (works for age-restricted when
    Firefox is signed into YouTube, and rides different endpoints than
    youtube-transcript-api)."""
    import subprocess

    outtmpl = OUT_DIR / "_ytdlp_tmp"
    cookie_file = OUT_DIR / "cookies.txt"
    cookie_args = (
        ["--cookies", str(cookie_file)]
        if cookie_file.exists()
        else ["--cookies-from-browser", "firefox"]
    )
    cmd = [
        str(YTDLP), "--js-runtimes", "node", *cookie_args,
        "--skip-download", "--write-auto-subs", "--sub-langs", "en",
        "--sub-format", "json3", "-o", str(outtmpl) + ".%(ext)s",
        f"https://www.youtube.com/watch?v={vid}",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    sub = OUT_DIR / f"_ytdlp_tmp.en.json3"
    if not sub.exists():
        raise RuntimeError(f"yt-dlp no subs: {(r.stderr or r.stdout).strip()[-180:]}")
    data = json.loads(sub.read_text())
    segs = []
    for ev in data.get("events", []):
        segs_list = ev.get("segs")
        if not segs_list:
            continue
        text = "".join(s.get("utf8", "") for s in segs_list).replace("\n", " ").strip()
        if not text:
            continue
        start = (ev.get("tStartMs") or 0) / 1000
        dur = (ev.get("dDurationMs") or 0) / 1000
        segs.append({"start": round(start, 2), "end": round(start + dur, 2), "text": text})
    sub.unlink()
    return {
        "video_id": vid,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_auto_generated": True,
        "segment_count": len(segs),
        "segments": segs,
        "via": "ytdlp",
    }


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


def classify(err: str) -> str:
    low = err.lower()
    if "age-restricted" in low or "age restricted" in low:
        return "age_restricted"
    if "429" in low or "too many requests" in low or "blocking requests from your ip" in low:
        return "rate_limited"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="max videos this run")
    ap.add_argument("--only-failed", action="store_true", help="retry logged failures")
    ap.add_argument("--delay", type=float, default=15.0, help="base seconds between fetches")
    ap.add_argument("--jitter", type=float, default=6.0, help="random extra seconds 0..N")
    ap.add_argument("--block-sleep", type=float, default=600.0, help="seconds to sleep on IP block")
    args = ap.parse_args()

    import random

    inventory = json.loads(Path("data/derived/vod_inventory.json").read_text())
    fails = load_failures()

    if args.only_failed:
        targets = [(e["id"], e.get("title")) for e in inventory if e["id"] in fails]
    else:
        targets = [(e["id"], e.get("title")) for e in inventory]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = skipped = err = 0
    consecutive_blocks = 0
    for i, (vid, title) in enumerate(targets):
        out = OUT_DIR / f"{vid}.json"
        if out.exists():
            skipped += 1
            continue
        if args.limit and done >= args.limit:
            break
        try:
            try:
                dump = fetch_one(vid, None)
            except Exception as primary_err:  # noqa: BLE001
                kind0 = classify(str(primary_err))
                if kind0 in ("age_restricted", "rate_limited"):
                    # second path: yt-dlp with Firefox cookies (different endpoints)
                    dump = fetch_via_ytdlp(vid)
                    dump["title"] = title
                    out.write_text(json.dumps(dump))
                    fails.pop(vid, None)
                    consecutive_blocks = 0
                    done += 1
                    if done % 10 == 0:
                        save_failures(fails)
                        print(f"[{i + 1}/{len(targets)}] ok={done} skip={skipped} err={err}", flush=True)
                    time.sleep(args.delay + random.uniform(0, args.jitter))
                    continue
                raise
            dump["title"] = title
            out.write_text(json.dumps(dump))
            fails.pop(vid, None)
            consecutive_blocks = 0
            done += 1
            if done % 10 == 0:
                save_failures(fails)
                print(f"[{i + 1}/{len(targets)}] ok={done} skip={skipped} err={err}", flush=True)
            time.sleep(args.delay + random.uniform(0, args.jitter))
        except Exception as e:  # noqa: BLE001 - log every failure type
            msg = str(e)[:200]
            kind = classify(msg)
            err += 1
            fails[vid] = {
                "error": msg,
                "kind": kind,
                "at": datetime.now(timezone.utc).isoformat(),
            }
            print(f"ERR[{kind}] {vid}: {msg[:90]}", flush=True)
            if kind == "rate_limited":
                consecutive_blocks += 1
                if consecutive_blocks >= 4:
                    print("IP still blocked after 4 backoffs — aborting run (resume later).", flush=True)
                    break
                nap = args.block_sleep * consecutive_blocks
                print(f"blocked: sleeping {nap / 60:.0f} min", flush=True)
                time.sleep(nap)
            elif kind == "age_restricted":
                time.sleep(2)  # no backoff needed; needs cookies, not patience
            else:
                time.sleep(args.delay + random.uniform(0, args.jitter))

    save_failures(fails)
    by_kind: dict[str, int] = {}
    for v in fails.values():
        by_kind[v.get("kind", "other")] = by_kind.get(v.get("kind", "other"), 0) + 1
    print(f"\nDONE: fetched={done} skipped(existing)={skipped} errors={err}")
    print(f"failure log: {FAIL_LOG} pending={len(fails)} by_kind={by_kind}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
