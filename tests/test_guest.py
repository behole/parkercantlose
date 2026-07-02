"""Tests for guest identity — cross-video caller tracking."""

from pathlib import Path

from parker.crud import (
    create_debate,
    create_guest,
    get_all_guests,
    get_guest,
    get_guest_appearances,
    get_guest_stats,
    link_debate_to_guest,
    update_debate_status,
)
from parker.db import get_engine, get_session, init_db
from parker.models import Debate, Utterance, VideoStatus


def _setup_db_with_debates(tmp_path: Path) -> tuple:
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    with get_session(engine) as session:
        d1 = create_debate(
            session, youtube_id="vid00000001", title="Debate 1",
            url="https://youtube.com/watch?v=vid00000001", duration_seconds=3600.0,
        )
        d2 = create_debate(
            session, youtube_id="vid00000002", title="Debate 2 ft. Dean Withers",
            url="https://youtube.com/watch?v=vid00000002", duration_seconds=5400.0,
        )
        d3 = create_debate(
            session, youtube_id="vid00000003", title="Debate 3 ft. Dean Withers",
            url="https://youtube.com/watch?v=vid00000003", duration_seconds=2700.0,
        )
        update_debate_status(session, "vid00000001", VideoStatus.COMPLETED)
        update_debate_status(session, "vid00000002", VideoStatus.COMPLETED)
        update_debate_status(session, "vid00000003", VideoStatus.COMPLETED)

        session.add_all([
            Utterance(debate_id=d1.id, speaker="caller", text="I support Trump.", start_time=10.0, end_time=15.0),
            Utterance(debate_id=d1.id, speaker="caller", text="Tariffs are good.", start_time=20.0, end_time=25.0),
            Utterance(debate_id=d2.id, speaker="caller", text="I'm Dean Withers.", start_time=5.0, end_time=10.0),
            Utterance(debate_id=d2.id, speaker="caller", text="Epstein was bad.", start_time=30.0, end_time=35.0),
            Utterance(debate_id=d3.id, speaker="caller", text="Dean again.", start_time=12.0, end_time=18.0),
        ])
        session.commit()
        debate_ids = [d1.id, d2.id, d3.id]

    return engine, debate_ids


def test_create_guest(tmp_path: Path):
    engine, _ = _setup_db_with_debates(tmp_path)

    with get_session(engine) as session:
        guest = create_guest(session, name="Dean Withers")
        assert guest.id is not None
        assert guest.name == "Dean Withers"
        assert guest.notes is None


def test_get_guest(tmp_path: Path):
    engine, _ = _setup_db_with_debates(tmp_path)

    with get_session(engine) as session:
        created = create_guest(session, name="Anonymous Caller")
        guest = get_guest(session, created.id)
        assert guest is not None
        assert guest.name == "Anonymous Caller"


def test_get_all_guests(tmp_path: Path):
    engine, _ = _setup_db_with_debates(tmp_path)

    with get_session(engine) as session:
        create_guest(session, name="Dean Withers")
        create_guest(session, name="MAGA Bro #1")
        guests = get_all_guests(session)
        assert len(guests) == 2


def test_link_debate_to_guest(tmp_path: Path):
    engine, debate_ids = _setup_db_with_debates(tmp_path)

    with get_session(engine) as session:
        guest = create_guest(session, name="Dean Withers")
        debate = link_debate_to_guest(session, debate_ids[1], guest.id)
        assert debate.guest_id == guest.id


def test_get_guest_appearances(tmp_path: Path):
    engine, debate_ids = _setup_db_with_debates(tmp_path)

    with get_session(engine) as session:
        guest = create_guest(session, name="Dean Withers")
        link_debate_to_guest(session, debate_ids[1], guest.id)
        link_debate_to_guest(session, debate_ids[2], guest.id)

        appearances = get_guest_appearances(session, guest.id)
        assert len(appearances) == 2
        titles = [a.title for a in appearances]
        assert "Debate 2 ft. Dean Withers" in titles
        assert "Debate 3 ft. Dean Withers" in titles


def test_get_guest_stats(tmp_path: Path):
    engine, debate_ids = _setup_db_with_debates(tmp_path)

    with get_session(engine) as session:
        guest = create_guest(session, name="Dean Withers")
        link_debate_to_guest(session, debate_ids[1], guest.id)
        link_debate_to_guest(session, debate_ids[2], guest.id)

        stats = get_guest_stats(session, guest.id)
        assert stats["total_debates"] == 2
        assert stats["total_utterances"] == 3
        assert "Dean Withers" in stats["name"]


def test_unlinked_debates_have_no_guest(tmp_path: Path):
    engine, debate_ids = _setup_db_with_debates(tmp_path)

    with get_session(engine) as session:
        from sqlmodel import select

        debate = session.exec(select(Debate).where(Debate.id == debate_ids[0])).first()
        assert debate.guest_id is None
