#!/usr/bin/env python3
"""
Phase 3 - Store: Load structured transcripts into SQLite with FTS5.

Schema:
  videos     - metadata per video (id, duration, fetched_at, chapter_count)
  chapters   - guest conversation blocks (guest, start, end, duration)
  utterances - merged speaker turns (speaker, text, timestamps)
  utterances_fts - FTS5 virtual table for full-text search
"""
import json
import sqlite3
import sys
import os
import glob

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'parker.db')

def init_db(db_path=None):
    """Create schema if not exists."""
    if db_path is None:
        db_path = DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            title TEXT,
            duration_seconds REAL,
            segment_count INTEGER,
            utterance_count INTEGER,
            chapter_count INTEGER,
            fetched_at TEXT,
            structured_at TEXT
        );
        
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            guest TEXT NOT NULL,
            chapter_num INTEGER,
            start_seconds REAL,
            end_seconds REAL,
            duration_seconds REAL,
            utterance_count INTEGER,
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        );
        
        CREATE TABLE IF NOT EXISTS utterances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            speaker TEXT NOT NULL,
            text TEXT NOT NULL,
            start_seconds REAL,
            end_seconds REAL,
            duration_seconds REAL,
            chapter_guest TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_utterances_video ON utterances(video_id);
        CREATE INDEX IF NOT EXISTS idx_utterances_speaker ON utterances(speaker);
        CREATE INDEX IF NOT EXISTS idx_utterances_start ON utterances(start_seconds);
        CREATE INDEX IF NOT EXISTS idx_chapters_video ON chapters(video_id);
    """)
    
    # FTS5 virtual table
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS utterances_fts USING fts5(
            text,
            speaker,
            video_id,
            content=utterances,
            content_rowid=id
        )
    """)
    
    conn.commit()
    return conn


def load_structured(structured_path, conn):
    """Load a structured JSON file into the database."""
    with open(structured_path) as f:
        data = json.load(f)
    
    video_id = data["video_id"]
    
    # Check if already loaded
    existing = conn.execute(
        "SELECT video_id FROM videos WHERE video_id = ?", (video_id,)
    ).fetchone()
    
    if existing:
        print(f"  Video {video_id} already in DB, skipping (use --force to reload)")
        return False
    
    # Insert video
    conn.execute("""
        INSERT INTO videos (video_id, utterance_count, chapter_count)
        VALUES (?, ?, ?)
    """, (video_id, data["total_utterances"], data["total_chapters"]))
    
    # Determine which chapter each utterance belongs to
    chapters = data.get("chapters", [])
    
    # Insert chapters
    for i, ch in enumerate(chapters):
        duration = (ch["end"] - ch["start"]) if ch.get("end") else 0
        conn.execute("""
            INSERT INTO chapters (video_id, guest, chapter_num, start_seconds, 
                                  end_seconds, duration_seconds, utterance_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (video_id, ch["guest"], i+1, ch["start"], ch.get("end"), 
              duration, ch["utterance_count"]))
    
    # Insert utterances
    for utt in data["utterances"]:
        duration = utt["end"] - utt["start"] if utt.get("end") else 0
        
        # Find which chapter this utterance belongs to
        chapter_guest = None
        for ch in chapters:
            if ch["start"] <= utt["start"] and (ch.get("end") is None or utt["start"] < ch["end"]):
                chapter_guest = ch["guest"]
                break
        
        conn.execute("""
            INSERT INTO utterances (video_id, speaker, text, start_seconds,
                                    end_seconds, duration_seconds, chapter_guest)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (video_id, utt["speaker"], utt["text"], utt["start"],
              utt.get("end"), duration, chapter_guest))
    
    # Rebuild FTS index
    conn.execute("INSERT INTO utterances_fts(utterances_fts) VALUES('rebuild')")
    
    conn.commit()
    print(f"  Loaded {video_id}: {data['total_utterances']} utterances, {data['total_chapters']} chapters")
    return True


def load_all(structured_dir=None, db_path=None):
    """Load all structured JSONs into the database."""
    if structured_dir is None:
        structured_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'structured')
    
    conn = init_db(db_path)
    
    files = glob.glob(os.path.join(structured_dir, '*.json'))
    print(f"Found {len(files)} structured files")
    
    loaded = 0
    for f in sorted(files):
        if load_structured(f, conn):
            loaded += 1
    
    # Show DB stats
    total_videos = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    total_utterances = conn.execute("SELECT COUNT(*) FROM utterances").fetchone()[0]
    total_chapters = conn.execute("SELECT COUNT(*) FROM chapters").fetchone()[0]
    
    print(f"\nDB stats:")
    print(f"  Videos: {total_videos}")
    print(f"  Chapters: {total_chapters}")
    print(f"  Utterances: {total_utterances}")
    print(f"  DB size: {os.path.getsize(db_path or DB_PATH) / 1024:.0f} KB")
    
    conn.close()
    return loaded


if __name__ == '__main__':
    force = '--force' in sys.argv
    
    if force:
        db_path = DB_PATH
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        if os.path.exists(db_path):
            os.remove(db_path)
            print("Removed existing DB")
    
    load_all()
