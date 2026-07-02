from sqlalchemy import Engine, text

FTS_TABLE_SQL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS utterances_fts USING fts5("
    "text, speaker, content='utterance', content_rowid='id'"
    ")"
)

FTS_TRIGGER_INSERT = (
    "CREATE TRIGGER IF NOT EXISTS utterances_fts_insert AFTER INSERT ON utterance BEGIN"
    " INSERT INTO utterances_fts(rowid, text, speaker)"
    " VALUES (new.id, new.text, new.speaker);"
    " END"
)

FTS_TRIGGER_UPDATE = (
    "CREATE TRIGGER IF NOT EXISTS utterances_fts_update AFTER UPDATE ON utterance BEGIN"
    " INSERT INTO utterances_fts(utterances_fts, rowid, text, speaker)"
    " VALUES ('delete', old.id, old.text, old.speaker);"
    " INSERT INTO utterances_fts(rowid, text, speaker)"
    " VALUES (new.id, new.text, new.speaker);"
    " END"
)

FTS_TRIGGER_DELETE = (
    "CREATE TRIGGER IF NOT EXISTS utterances_fts_delete AFTER DELETE ON utterance BEGIN"
    " INSERT INTO utterances_fts(utterances_fts, rowid, text, speaker)"
    " VALUES ('delete', old.id, old.text, old.speaker);"
    " END"
)


def run_fts_migration(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(FTS_TABLE_SQL))
        conn.execute(text(FTS_TRIGGER_INSERT))
        conn.execute(text(FTS_TRIGGER_UPDATE))
        conn.execute(text(FTS_TRIGGER_DELETE))
        conn.commit()


def rebuild_fts(engine: Engine) -> None:
    import sqlite3

    db_path = str(engine.url.database)
    raw = sqlite3.connect(db_path)
    raw.execute("DELETE FROM utterances_fts")
    raw.execute("INSERT INTO utterances_fts(rowid, text, speaker) SELECT id, text, speaker FROM utterance")
    raw.commit()
    raw.close()
