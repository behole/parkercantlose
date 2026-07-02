"""Pipeline database — schema init, connection, migration."""
import sqlite3
import os
from datetime import datetime

from . import DB_PATH

SCHEMA_VERSION = 1


def get_conn(db_path=None):
    """Return a connection to the canonical DB."""
    if db_path is None:
        db_path = DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    """Create all tables and indexes. Idempotent."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_state (
            video_id TEXT NOT NULL,
            phase TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            error TEXT,
            started_at TEXT,
            finished_at TEXT,
            PRIMARY KEY (video_id, phase)
        );

        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT,
            author TEXT,
            is_auto_generated INTEGER DEFAULT 0,
            total_duration_sec REAL,
            utterance_count INTEGER,
            chapter_count INTEGER,
            speakers TEXT,
            added_at TEXT DEFAULT (datetime('now'))
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

        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        );
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
        (SCHEMA_VERSION,),
    )
    conn.commit()
    return conn


def migrate_old_db(conn, old_db_path):
    """Attempt to migrate data from an old parker.db."""
    if not os.path.exists(old_db_path):
        return False, f"Not found: {old_db_path}"

    old = sqlite3.connect(old_db_path)
    old.row_factory = sqlite3.Row

    # Check if old db has videos
    tables = old.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [r["name"] for r in tables]
    migrated = 0

    # Try to pull videos
    for table in ["videos", "utterances", "chapters"]:
        if table in table_names:
            try:
                rows = old.execute(f"SELECT * FROM {table}").fetchall()
                if rows:
                    cols = [desc[0] for desc in old.execute(f"SELECT * FROM {table} LIMIT 1").description]
                    placeholders = ",".join(["?"] * len(cols))
                    col_str = ",".join(cols)
                    for row in rows:
                        try:
                            conn.execute(
                                f"INSERT OR IGNORE INTO {table} ({col_str}) VALUES ({placeholders})",
                                tuple(row),
                            )
                            migrated += 1
                        except Exception:
                            pass
            except Exception as e:
                pass

    old.close()

    if migrated > 0:
        conn.commit()
        return True, f"Migrated {migrated} rows from {old_db_path}"
    return False, f"No migratable data in {old_db_path}"
