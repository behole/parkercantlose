#!/usr/bin/env python3
"""Phase 3: Store - Load structured transcripts into SQLite with FTS5.

Schema:
  videos    - video metadata
  utterances - individual speaker turns with timestamps
  chapters  - guest conversation boundaries
  utterances_fts - FTS5 virtual table for full-text search

Usage:
    python3 store.py <structured_json> [--db PATH]
    python3 store.py --load-all <dir> [--db PATH]
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


DB_PATH = "./data/parker.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    url TEXT,
    title TEXT,
    author TEXT,
    is_auto_generated INTEGER,
    total_duration_sec INTEGER,
    utterance_count INTEGER,
    chapter_count INTEGER,
    speakers TEXT  -- JSON array
);

CREATE TABLE IF NOT EXISTS utterances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    idx INTEGER,
    speaker TEXT,
    text TEXT,
    start_sec REAL,
    end_sec REAL,
    chapter INTEGER,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    chapter INTEGER,
    start_idx INTEGER,
    end_idx INTEGER,
    start_time REAL,
    end_time REAL,
    duration_sec REAL,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS utterances_fts USING fts5(
    text, speaker, video_id,
    content='utterances',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS utterances_ai AFTER INSERT ON utterances BEGIN
    INSERT INTO utterances_fts(rowid, text, speaker, video_id)
    VALUES (new.id, new.text, new.speaker, new.video_id);
END;

CREATE TRIGGER IF NOT EXISTS utterances_ad AFTER DELETE ON utterances BEGIN
    INSERT INTO utterances_fts(utterances_fts, rowid, text, speaker, video_id)
    VALUES ('delete', old.id, old.text, old.speaker, old.video_id);
END;

CREATE INDEX IF NOT EXISTS idx_utterances_video ON utterances(video_id);
CREATE INDEX IF NOT EXISTS idx_utterances_speaker ON utterances(speaker);
CREATE INDEX IF NOT EXISTS idx_utterances_chapter ON utterances(video_id, chapter);
CREATE INDEX IF NOT EXISTS idx_chapters_video ON chapters(video_id);
"""


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def load_structured(conn, structured_path):
    with open(structured_path) as f:
        data = json.load(f)

    vid = data["video_id"]

    # Check if already loaded
    existing = conn.execute("SELECT video_id FROM videos WHERE video_id = ?", (vid,)).fetchone()
    if existing:
        print(f"  Video {vid} already in DB, skipping (use --force to reload)")
        return False

    # Insert video
    conn.execute(
        "INSERT INTO videos (video_id, url, title, author, is_auto_generated, total_duration_sec, utterance_count, chapter_count, speakers) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (vid, data["url"], data["title"], data["author"],
         1 if data["is_auto_generated"] else 0,
         data["total_duration_sec"], data["utterance_count"],
         data["chapter_count"], json.dumps(data["speakers"]))
    )

    # Map utterance index to chapter
    utt_to_chapter = {}
    for ch in data["chapters"]:
        for idx in range(ch["start_idx"], ch["end_idx"] + 1):
            utt_to_chapter[idx] = ch["chapter"]

    # Insert utterances
    for i, utt in enumerate(data["utterances"]):
        conn.execute(
            "INSERT INTO utterances (video_id, idx, speaker, text, start_sec, end_sec, chapter) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (vid, i, utt["speaker"], utt["text"], utt["start"], utt["end"],
             utt_to_chapter.get(i))
        )

    # Insert chapters
    for ch in data["chapters"]:
        conn.execute(
            "INSERT INTO chapters (video_id, chapter, start_idx, end_idx, start_time, end_time, duration_sec) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (vid, ch["chapter"], ch["start_idx"], ch["end_idx"],
             ch["start_time"], ch["end_time"],
             ch["end_time"] - ch["start_time"])
        )

    conn.commit()
    print(f"  Loaded {vid}: {data['utterance_count']} utterances, {data['chapter_count']} chapters")
    return True


def main():
    parser = argparse.ArgumentParser(description="Load structured transcripts into SQLite")
    parser.add_argument("input", nargs="?", help="Structured JSON file or directory")
    parser.add_argument("--db", default=DB_PATH, help=f"Database path (default: {DB_PATH})")
    parser.add_argument("--load-all", action="store_true", help="Load all .structured.json files from input dir")
    parser.add_argument("--force", action="store_true", help="Reload even if video already in DB")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    args = parser.parse_args()

    conn = init_db(args.db)

    if args.stats:
        row = conn.execute("SELECT COUNT(*) FROM videos").fetchone()
        print(f"Videos: {row[0]}")
        row = conn.execute("SELECT COUNT(*) FROM utterances").fetchone()
        print(f"Utterances: {row[0]}")
        row = conn.execute("SELECT COUNT(*) FROM chapters").fetchone()
        print(f"Chapters: {row[0]}")
        conn.close()
        return

    if not args.input:
        parser.print_help()
        conn.close()
        sys.exit(1)

    if args.force:
        # Delete existing data for reload
        pass  # handled per-video

    if args.load_all:
        files = sorted(Path(args.input).glob("*.structured.json"))
        print(f"Found {len(files)} structured files")
        for f in files:
            load_structured(conn, str(f))
    else:
        load_structured(conn, args.input)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
