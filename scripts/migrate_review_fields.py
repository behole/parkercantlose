"""Migration script: add review_status to debate, edit-tracking to utterance."""
import sqlite3
import sys
from pathlib import Path


def migrate(db_path: str = "data/db/debates.db") -> None:
    path = Path(db_path)
    if not path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(path))
    cursor = conn.cursor()

    # Add review_status to debate
    try:
        cursor.execute("ALTER TABLE debate ADD COLUMN review_status TEXT DEFAULT 'unreviewed'")
        print("Added debate.review_status")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("debate.review_status already exists")
        else:
            raise

    # Add original_speaker and original_text to utterance
    for col in ["original_speaker", "original_text"]:
        try:
            cursor.execute(f"ALTER TABLE utterance ADD COLUMN {col} TEXT DEFAULT NULL")
            print(f"Added utterance.{col}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print(f"utterance.{col} already exists")
            else:
                raise

    # Add edited_at to utterance
    try:
        cursor.execute("ALTER TABLE utterance ADD COLUMN edited_at TEXT DEFAULT NULL")
        print("Added utterance.edited_at")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("utterance.edited_at already exists")
        else:
            raise

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "data/db/debates.db"
    migrate(db)
