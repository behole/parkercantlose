from pathlib import Path

from parker.crud import (
    create_debate,
    get_debate_by_youtube_id,
    get_debates_by_status,
    merge_topic_match,
    reject_topic_match,
    reset_failed_debate,
    update_debate_status,
)
from parker.db import get_engine, get_session, init_db
from parker.models import Stance, Topic, TopicMatch, VideoStatus


def _setup_db(tmp_data_dir: Path):
    db_path = tmp_data_dir / "test.db"
    engine = get_engine(db_path)
    init_db(engine)
    return engine


def test_create_debate(tmp_data_dir: Path):
    engine = _setup_db(tmp_data_dir)
    with get_session(engine) as session:
        debate = create_debate(
            session,
            youtube_id="abc123",
            title="Test Debate",
            url="https://youtube.com/watch?v=abc123",
            duration_seconds=1800.0,
            upload_date="20250101",
        )
        assert debate.id is not None
        assert debate.youtube_id == "abc123"
        assert debate.status == VideoStatus.PENDING


def test_get_debate_by_youtube_id(tmp_data_dir: Path):
    engine = _setup_db(tmp_data_dir)
    with get_session(engine) as session:
        create_debate(session, youtube_id="findme", title="Find Me", url="https://youtube.com/watch?v=findme")
    with get_session(engine) as session:
        found = get_debate_by_youtube_id(session, "findme")
        assert found is not None
        assert found.title == "Find Me"


def test_get_debate_not_found(tmp_data_dir: Path):
    engine = _setup_db(tmp_data_dir)
    init_db(engine)
    with get_session(engine) as session:
        found = get_debate_by_youtube_id(session, "nonexistent")
        assert found is None


def test_update_debate_status(tmp_data_dir: Path):
    engine = _setup_db(tmp_data_dir)
    with get_session(engine) as session:
        create_debate(session, youtube_id="stat123", title="Status Test", url="https://youtube.com/watch?v=stat123")
    with get_session(engine) as session:
        updated = update_debate_status(session, "stat123", VideoStatus.DOWNLOADED)
        assert updated is not None
        assert updated.status == VideoStatus.DOWNLOADED


def test_update_debate_status_with_error(tmp_data_dir: Path):
    engine = _setup_db(tmp_data_dir)
    with get_session(engine) as session:
        create_debate(session, youtube_id="err123", title="Error Test", url="https://youtube.com/watch?v=err123")
    with get_session(engine) as session:
        updated = update_debate_status(session, "err123", VideoStatus.FAILED, error_message="Download failed: 404")
        assert updated is not None
        assert updated.status == VideoStatus.FAILED
        assert updated.error_message == "Download failed: 404"


def test_get_debates_by_status(tmp_data_dir: Path):
    engine = _setup_db(tmp_data_dir)
    with get_session(engine) as session:
        create_debate(session, youtube_id="s1", title="One", url="https://youtube.com/watch?v=s1")
        create_debate(session, youtube_id="s2", title="Two", url="https://youtube.com/watch?v=s2")
    with get_session(engine) as session:
        update_debate_status(session, "s2", VideoStatus.COMPLETED)
    with get_session(engine) as session:
        pending = get_debates_by_status(session, VideoStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].youtube_id == "s1"
        completed = get_debates_by_status(session, VideoStatus.COMPLETED)
        assert len(completed) == 1


def test_reset_failed_debate(tmp_data_dir: Path):
    engine = _setup_db(tmp_data_dir)
    with get_session(engine) as session:
        create_debate(session, youtube_id="retry1", title="Retry", url="https://youtube.com/watch?v=retry1")
    with get_session(engine) as session:
        update_debate_status(session, "retry1", VideoStatus.FAILED, error_message="Some error")
    with get_session(engine) as session:
        reset = reset_failed_debate(session, "retry1")
        assert reset is not None
        assert reset.status == VideoStatus.PENDING
        assert reset.error_message is None


def test_merge_topic_match(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "D1", "https://youtube.com/watch?v=abc123")
        d2 = create_debate(session, "def456", "D2", "https://youtube.com/watch?v=def456")
        t1 = Topic(debate_id=d1.id, name="Immigration", status="suggested")
        t2 = Topic(debate_id=d2.id, name="Immigration Policy", status="suggested")
        session.add_all([t1, t2])
        session.flush()
        s1 = Stance(debate_id=d1.id, topic_id=t1.id, speaker="parker", label="SUPPORTS", confidence=0.9)
        s2 = Stance(debate_id=d2.id, topic_id=t2.id, speaker="caller", label="OPPOSES", confidence=0.8)
        session.add_all([s1, s2])
        match = TopicMatch(topic_a_id=t1.id, topic_b_id=t2.id, similarity=0.96, status="suggested")
        session.add(match)
        session.commit()
        match_id = match.id
        t2_id = t2.id
        t1_id = t1.id

    with get_session(engine) as session:
        result = merge_topic_match(session, match_id)
    assert result is not None
    assert result["stances_moved"] == 1
    assert result["merged_into"] == "Immigration"

    with get_session(engine) as session:
        match_after = session.get(TopicMatch, match_id)
        assert match_after.status == "confirmed"
        t2_after = session.get(Topic, t2_id)
        assert t2_after.merged_into_id == t1_id


def test_reject_topic_match(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "D1", "https://youtube.com/watch?v=abc123")
        d2 = create_debate(session, "def456", "D2", "https://youtube.com/watch?v=def456")
        t1 = Topic(debate_id=d1.id, name="Taxes", status="suggested")
        t2 = Topic(debate_id=d2.id, name="Tax Policy", status="suggested")
        session.add_all([t1, t2])
        session.flush()
        match = TopicMatch(topic_a_id=t1.id, topic_b_id=t2.id, similarity=0.88, status="suggested")
        session.add(match)
        session.commit()
        match_id = match.id

    with get_session(engine) as session:
        result = reject_topic_match(session, match_id)
    assert result is True

    with get_session(engine) as session:
        match_after = session.get(TopicMatch, match_id)
        assert match_after.status == "rejected"
