"""Migrate data from old parker.db (v3/v4 regex pipeline) into new debates.db schema."""
import sqlite3
from pathlib import Path

from parker.crud import create_debate, get_debate_by_youtube_id, update_debate_status
from parker.db import get_session
from parker.models import Utterance, VideoStatus


def _read_old_videos(old_conn: sqlite3.Connection) -> list[dict]:
    old_conn.row_factory = sqlite3.Row
    rows = old_conn.execute(
        "SELECT video_id, url, title, author, total_duration_sec FROM videos"
    ).fetchall()
    return [dict(r) for r in rows]


def _read_old_utterances(old_conn: sqlite3.Connection, video_id: str) -> list[dict]:
    old_conn.row_factory = sqlite3.Row
    rows = old_conn.execute(
        "SELECT idx, speaker, text, start_sec, end_sec FROM utterances WHERE video_id=? ORDER BY idx",
        (video_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _map_speaker(old_speaker: str) -> tuple[str, str | None]:
    """Map old speaker label to (new_speaker, speaker_raw)."""
    if old_speaker == "parker":
        return "parker", None
    return "caller", old_speaker


def migrate_old_parker_db(engine, old_db_path: Path) -> dict:
    """Migrate videos and utterances from old parker.db into new debates.db.

    Idempotent: skips videos already present (by youtube_id).
    Returns summary dict with counts.
    """
    if not old_db_path.exists():
        return {"videos_migrated": 0, "utterances_migrated": 0, "skipped": 0, "error": f"Not found: {old_db_path}"}

    old_conn = sqlite3.connect(str(old_db_path))
    old_videos = _read_old_videos(old_conn)

    videos_migrated = 0
    utterances_migrated = 0
    skipped = 0

    for v in old_videos:
        yt_id = v["video_id"]
        title = v.get("title") or yt_id
        url = v.get("url") or f"https://youtube.com/watch?v={yt_id}"
        duration = v.get("total_duration_sec")

        with get_session(engine) as session:
            existing = get_debate_by_youtube_id(session, yt_id)
            if existing:
                skipped += 1
                continue

            debate = create_debate(
                session,
                youtube_id=yt_id,
                title=title,
                url=url,
                duration_seconds=duration,
            )

        old_utterances = _read_old_utterances(old_conn, yt_id)

        with get_session(engine) as session:
            for u in old_utterances:
                speaker, speaker_raw = _map_speaker(u.get("speaker", "guest"))
                utterance = Utterance(
                    debate_id=debate.id,
                    speaker=speaker,
                    speaker_raw=speaker_raw,
                    text=u["text"],
                    start_time=u["start_sec"],
                    end_time=u.get("end_sec", u["start_sec"] + 1.0),
                )
                session.add(utterance)

            update_debate_status(session, yt_id, VideoStatus.COMPLETED)
            session.commit()

        utterances_migrated += len(old_utterances)
        videos_migrated += 1

    old_conn.close()
    return {
        "videos_migrated": videos_migrated,
        "utterances_migrated": utterances_migrated,
        "skipped": skipped,
    }
