
from parker.analytics import (
    get_dashboard_stats,
    get_debate_timeline,
    get_recent_activity,
    get_topic_frequency,
)
from parker.crud import create_debate, create_guest
from parker.db import get_engine, get_session, init_db
from parker.models import (
    ReviewStatus,
    Topic,
    VideoStatus,
)


def test_get_dashboard_stats_empty(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        stats = get_dashboard_stats(session)
    assert stats["total_debates"] == 0
    assert stats["total_hours"] == 0


def test_get_dashboard_stats_with_data(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(
            session,
            youtube_id="abc123",
            title="Test Debate 1",
            url="https://youtube.com/watch?v=abc123",
            duration_seconds=3600,
            upload_date="2026-01-15",
        )
        d1.status = VideoStatus.COMPLETED
        session.add(d1)
        d2 = create_debate(
            session,
            youtube_id="def456",
            title="Test Debate 2",
            url="https://youtube.com/watch?v=def456",
            duration_seconds=5400,
            upload_date="2026-02-20",
        )
        d2.status = VideoStatus.COMPLETED
        d2.review_status = ReviewStatus.APPROVED
        session.add(d2)
        create_guest(session, name="Caller One")
        session.commit()

    with get_session(engine) as session:
        stats = get_dashboard_stats(session)
    assert stats["total_debates"] == 2
    assert stats["approved_count"] == 1
    assert stats["total_hours"] == 2.5
    assert stats["unique_guests"] == 1
    assert stats["completion_pct"] == 100


def test_get_topic_frequency_empty(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        freq = get_topic_frequency(session)
    assert freq == []


def test_get_topic_frequency_with_topics(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "Debate 1", "https://youtube.com/watch?v=abc123")
        t1 = Topic(debate_id=d1.id, name="Immigration", status="suggested")
        t2 = Topic(debate_id=d1.id, name="Economy", status="suggested")
        session.add_all([t1, t2])
        session.commit()

    with get_session(engine) as session:
        freq = get_topic_frequency(session, limit=10)
    assert ("Immigration", 1) in freq
    assert ("Economy", 1) in freq


def test_get_debate_timeline(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        create_debate(session, "abc123", "Jan Debate", "https://youtube.com/watch?v=abc123", upload_date="2026-01-10")
        create_debate(session, "def456", "Jan Debate 2", "https://youtube.com/watch?v=def456", upload_date="2026-01-20")
        create_debate(session, "ghi789", "Feb Debate", "https://youtube.com/watch?v=ghi789", upload_date="2026-02-05")
        session.commit()

    with get_session(engine) as session:
        timeline = get_debate_timeline(session)
    assert len(timeline) == 2
    assert ("2026-01", 2) in timeline
    assert ("2026-02", 1) in timeline


def test_get_recent_activity(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        create_debate(session, "abc123", "Test Debate", "https://youtube.com/watch?v=abc123")
        session.commit()

    with get_session(engine) as session:
        activity = get_recent_activity(session, limit=5)
    assert len(activity) == 1
    assert activity[0]["title"] == "Test Debate"
    assert activity[0]["youtube_id"] == "abc123"
