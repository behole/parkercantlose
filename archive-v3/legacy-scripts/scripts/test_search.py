#!/usr/bin/env python3
"""Quick FTS5 search test."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'db', 'parker.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Test basic search
queries = ["tariff", "immigration", "economy", "military", "climate", "Trump"]

for q in queries:
    results = conn.execute("""
        SELECT u.speaker, u.start_seconds, u.text, u.chapter_guest
        FROM utterances u
        JOIN utterances_fts fts ON u.id = fts.rowid
        WHERE utterances_fts MATCH ?
        ORDER BY u.start_seconds
        LIMIT 3
    """, (q,)).fetchall()
    
    print(f"\n=== '{q}' ({len(results)} shown) ===")
    for r in results:
        mins = r["start_seconds"] / 60
        text = r["text"][:100] + "..." if len(r["text"]) > 100 else r["text"]
        print(f"  [{mins:.0f}m] {r['speaker']:12s} ({r['chapter_guest'] or '?':12s}): {text}")

conn.close()
