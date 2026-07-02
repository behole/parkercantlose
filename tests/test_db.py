from pathlib import Path

from sqlmodel import Session, select

from parker.db import get_engine, get_session, init_db
from parker.models import Debate, VideoStatus


def test_init_db_creates_tables(tmp_data_dir: Path):
    db_path = tmp_data_dir / "test.db"
    engine = get_engine(db_path)
    init_db(engine)
    with Session(engine) as session:
        debate = Debate(youtube_id="abc123", title="Test", url="https://youtube.com/watch?v=abc123")
        session.add(debate)
        session.commit()
        statement = select(Debate).where(Debate.youtube_id == "abc123")
        result = session.exec(statement).one()
        assert result.title == "Test"
        assert result.status == VideoStatus.PENDING


def test_get_session_yields_session(tmp_data_dir: Path):
    db_path = tmp_data_dir / "test.db"
    engine = get_engine(db_path)
    init_db(engine)
    with get_session(engine) as session:
        debate = Debate(youtube_id="xyz789", title="Session Test", url="https://youtube.com/watch?v=xyz789")
        session.add(debate)
        session.commit()
    with Session(engine) as session:
        statement = select(Debate).where(Debate.youtube_id == "xyz789")
        result = session.exec(statement).one()
        assert result.title == "Session Test"


def test_unique_youtube_id_constraint(tmp_data_dir: Path):
    db_path = tmp_data_dir / "test.db"
    engine = get_engine(db_path)
    init_db(engine)
    from sqlalchemy.exc import IntegrityError

    with Session(engine) as session:
        d1 = Debate(youtube_id="dup123", title="First", url="https://youtube.com/watch?v=dup123")
        session.add(d1)
        session.commit()
    with Session(engine) as session:
        d2 = Debate(youtube_id="dup123", title="Second", url="https://youtube.com/watch?v=dup123")
        session.add(d2)
        try:
            session.commit()
            assert False, "Should have raised IntegrityError"
        except IntegrityError:
            session.rollback()
