"""Phase 3: Store — load structured transcript into SQLite."""
import json
from . import STRUCT_DIR, DB_PATH
from .state import set_phase


def run(conn, video_id):
    """Execute store phase. Loads structured JSON into utterances + chapters tables."""
    set_phase(conn, video_id, "store", "running")

    struct_path = STRUCT_DIR / f"{video_id}.structured.json"
    if not struct_path.exists():
        msg = f"Structured file not found: {struct_path}"
        set_phase(conn, video_id, "store", "failed", msg)
        raise FileNotFoundError(msg)

    with open(struct_path) as f:
        data = json.load(f)

    # Remove old data for this video (triggers cascade for FTS)
    conn.execute("DELETE FROM chapters WHERE video_id=?", (video_id,))
    conn.execute("DELETE FROM utterances WHERE video_id=?", (video_id,))

    # Insert chapters
    chapters = data.get("chapters", [])
    for ch in chapters:
        dur = ch["end_time"] - ch["start_time"]
        conn.execute(
            """INSERT INTO chapters (video_id, chapter, start_idx, end_idx,
               start_time, end_time, duration_sec)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                video_id, ch["chapter"],
                ch.get("start_idx", 0), ch.get("end_idx", 0),
                ch["start_time"], ch["end_time"], dur,
            ),
        )

    # Insert utterances
    utterances = data.get("utterances", [])
    for i, utt in enumerate(utterances):
        # Find which chapter this utterance belongs to
        chapter = None
        for ch in chapters:
            if ch.get("start_idx", 0) <= i <= ch.get("end_idx", 99999):
                chapter = ch["chapter"]
                break

        conn.execute(
            """INSERT INTO utterances
               (video_id, idx, speaker, text, start_sec, end_sec, chapter)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                video_id, i,
                utt.get("speaker", f"guest_{i}"),
                utt["text"],
                utt["start"], utt.get("end", utt["start"] + 1),
                chapter,
            ),
        )

    conn.commit()

    # Rebuild FTS
    conn.execute("INSERT INTO utterances_fts(utterances_fts) VALUES('rebuild')")
    conn.commit()

    print(f"  Stored {len(chapters)} chapters, {len(utterances)} utterances")
    set_phase(conn, video_id, "store", "done")
