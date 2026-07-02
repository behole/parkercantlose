"""Phase 1: Fetch YouTube transcript and video metadata."""
import json
import re
import sys
import urllib.request
from . import RAW_DIR
from .state import set_phase

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None


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
    import ssl
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(url, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            return {
                "title": data.get("title", ""),
                "author": data.get("author_name", ""),
                "author_url": data.get("author_url", ""),
            }
    except Exception as e:
        print(f"  Warning: could not fetch metadata: {e}", file=sys.stderr)
        return {"title": "", "author": "", "author_url": ""}


def run(conn, video_id, url):
    """Execute fetch phase. Returns record dict or raises."""
    if YouTubeTranscriptApi is None:
        raise RuntimeError("youtube-transcript-api not installed. Run: pip install youtube-transcript-api")

    set_phase(conn, video_id, "fetch", "running")

    print(f"Fetching transcript for {video_id}...")
    meta = fetch_video_metadata(video_id)

    try:
        raw_transcript = YouTubeTranscriptApi().fetch(video_id)
        # Convert FetchedTranscript object to list of dicts
        transcript = [{"text": s.text, "start": s.start, "duration": s.duration} for s in raw_transcript]
    except Exception as e:
        msg = f"Transcript API failed: {e}"
        set_phase(conn, video_id, "fetch", "failed", msg)
        raise RuntimeError(msg) from e

    is_auto = any(
        "[__" in seg.get("text", "") or seg.get("text", "").startswith("[")
        for seg in transcript[:5]
    )

    segments = []
    total_dur = 0.0
    for seg in transcript:
        dur = seg.get("duration", 0.0)
        start = seg.get("start", 0.0)
        segments.append({
            "text": seg["text"],
            "start": start,
            "duration": dur,
        })
        total_dur = max(total_dur, start + dur)

    record = {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": meta["title"],
        "author": meta.get("author", ""),
        "is_auto_generated": 1 if is_auto else 0,
        "total_duration_sec": total_dur,
        "segment_count": len(segments),
        "segments": segments,
    }

    import os
    os.makedirs(RAW_DIR, exist_ok=True)
    raw_path = RAW_DIR / f"{video_id}.json"
    with open(raw_path, "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    # Also register in videos table
    conn.execute(
        """INSERT OR REPLACE INTO videos
           (video_id, url, title, author, is_auto_generated, total_duration_sec)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (video_id, record["url"], meta["title"], meta.get("author", ""),
         int(is_auto), total_dur),
    )
    conn.commit()

    set_phase(conn, video_id, "fetch", "done")
    print(f"  {len(segments)} segments, {total_dur:.0f}s")
    return str(raw_path)
