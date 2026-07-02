"""Tests for migrating data from old parker.db to new debates.db schema."""

import sqlite3
from pathlib import Path

from parker.db import get_engine, get_session, init_db
from parker.migration import migrate_old_parker_db
from parker.models import Debate, ReviewStatus, Utterance, VideoStatus


def _create_old_db(db_path: Path) -> None:
    """Create an old-format parker.db with test data."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE videos (
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

        CREATE TABLE utterances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            idx INTEGER,
            speaker TEXT,
            text TEXT,
            start_sec REAL,
            end_sec REAL,
            chapter INTEGER
        );

        CREATE TABLE chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            chapter INTEGER,
            start_idx INTEGER,
            end_idx INTEGER,
            start_time REAL,
            end_time REAL,
            duration_sec REAL
        );

        CREATE TABLE pipeline_state (
            video_id TEXT NOT NULL,
            phase TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            error TEXT,
            started_at TEXT,
            finished_at TEXT,
            PRIMARY KEY (video_id, phase)
        );
    """)

    conn.execute(
        "INSERT INTO videos (video_id, url, title, author, total_duration_sec, utterance_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("testVid00001", "https://youtube.com/watch?v=testVid00001",
         "Test Debate", "Parkergetajob", 3600.0, 3),
    )
    conn.execute(
        "INSERT INTO videos (video_id, url, title, author, total_duration_sec, utterance_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("testVid00002", "https://youtube.com/watch?v=testVid00002",
         "Second Debate", "Parkergetajob", 5400.0, 2),
    )

    for phase in ["fetch", "structure", "store"]:
        conn.execute(
            "INSERT INTO pipeline_state (video_id, phase, status) VALUES (?, ?, 'done')",
            ("testVid00001", phase),
        )
        conn.execute(
            "INSERT INTO pipeline_state (video_id, phase, status) VALUES (?, ?, 'done')",
            ("testVid00002", phase),
        )

    utterances = [
        ("testVid00001", 0, "parker", "Welcome to the stream.", 0.0, 5.2, 0),
        ("testVid00001", 1, "guest_1", "Hi, thanks for having me.", 5.5, 10.0, 0),
        ("testVid00001", 2, "parker", "Do you support Donald Trump?", 10.3, 13.0, 0),
        ("testVid00002", 0, "parker", "What's up everyone?", 0.0, 3.0, 0),
        ("testVid00002", 1, "guest_3", "I have a question about tariffs.", 3.5, 8.0, 0),
    ]
    for vid, idx, speaker, text, start, end, chapter in utterances:
        conn.execute(
            "INSERT INTO utterances (video_id, idx, speaker, text, start_sec, end_sec, chapter) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (vid, idx, speaker, text, start, end, chapter),
        )

    conn.commit()
    conn.close()


def test_migrate_creates_debates_from_old_videos(tmp_path: Path):
    old_db = tmp_path / "parker.db"
    new_db = tmp_path / "debates.db"
    _create_old_db(old_db)

    engine = get_engine(new_db)
    init_db(engine)

    result = migrate_old_parker_db(engine, old_db)

    assert result["videos_migrated"] == 2
    assert result["utterances_migrated"] == 5
    assert result["skipped"] == 0

    with get_session(engine) as session:
        from sqlmodel import select

        debates = session.exec(select(Debate).order_by(Debate.youtube_id)).all()
        assert len(debates) == 2
        assert debates[0].youtube_id == "testVid00001"
        assert debates[0].title == "Test Debate"
        assert debates[0].duration_seconds == 3600.0
        assert debates[0].status == VideoStatus.COMPLETED
        assert debates[0].review_status == ReviewStatus.UNREVIEWED

        assert debates[1].youtube_id == "testVid00002"
        assert debates[1].title == "Second Debate"


def test_migrate_maps_speakers_correctly(tmp_path: Path):
    old_db = tmp_path / "parker.db"
    new_db = tmp_path / "debates.db"
    _create_old_db(old_db)

    engine = get_engine(new_db)
    init_db(engine)

    migrate_old_parker_db(engine, old_db)

    with get_session(engine) as session:
        from sqlmodel import select

        debate = session.exec(
            select(Debate).where(Debate.youtube_id == "testVid00001")
        ).first()
        assert debate is not None

        utterances = session.exec(
            select(Utterance).where(Utterance.debate_id == debate.id).order_by(Utterance.start_time)
        ).all()
        assert len(utterances) == 3

        assert utterances[0].speaker == "parker"
        assert utterances[0].speaker_raw is None

        assert utterances[1].speaker == "caller"
        assert utterances[1].speaker_raw == "guest_1"

        assert utterances[2].speaker == "parker"


def test_migrate_is_idempotent(tmp_path: Path):
    old_db = tmp_path / "parker.db"
    new_db = tmp_path / "debates.db"
    _create_old_db(old_db)

    engine = get_engine(new_db)
    init_db(engine)

    migrate_old_parker_db(engine, old_db)
    result = migrate_old_parker_db(engine, old_db)

    assert result["videos_migrated"] == 0
    assert result["utterances_migrated"] == 0
    assert result["skipped"] == 2


def test_migrate_preserves_text_and_timestamps(tmp_path: Path):
    old_db = tmp_path / "parker.db"
    new_db = tmp_path / "debates.db"
    _create_old_db(old_db)

    engine = get_engine(new_db)
    init_db(engine)

    migrate_old_parker_db(engine, old_db)

    with get_session(engine) as session:
        from sqlmodel import select

        debate = session.exec(
            select(Debate).where(Debate.youtube_id == "testVid00001")
        ).first()
        assert debate is not None

        utterances = session.exec(
            select(Utterance).where(Utterance.debate_id == debate.id).order_by(Utterance.start_time)
        ).all()

        assert utterances[0].text == "Welcome to the stream."
        assert utterances[0].start_time == 0.0
        assert utterances[0].end_time == 5.2

        assert utterances[1].text == "Hi, thanks for having me."
        assert utterances[1].start_time == 5.5
        assert utterances[1].end_time == 10.0
