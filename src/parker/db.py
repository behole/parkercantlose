from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, inspect, text
from sqlmodel import Session, SQLModel, create_engine


def get_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def _run_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    if "debate" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("debate")}
        if "slug" not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE debate ADD COLUMN slug TEXT"))
                conn.commit()


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    _run_migrations(engine)
    from parker.search import run_fts_migration

    run_fts_migration(engine)


@contextmanager
def get_session(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
