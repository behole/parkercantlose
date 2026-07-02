#!/usr/bin/env python3
"""Phase 4: Query - Search Parker livestream transcripts."""

import argparse
import json
import sqlite3
import sys

DB_PATH = "./data/parker.db"


def fmt_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def yt_link(video_id, seconds):
    return "https://youtu.be/%s?t=%d" % (video_id, int(seconds))


def search(conn, query, speaker=None, video_id=None, chapter=None, limit=20, context=1):
    fts_query = query
    sql = """
        SELECT u.video_id, u.idx, u.speaker, u.text, u.start_sec, u.end_sec, u.chapter,
               v.title
        FROM utterances_fts fts
        JOIN utterances u ON u.id = fts.rowid
        JOIN videos v ON v.video_id = u.video_id
        WHERE utterances_fts MATCH ?
    """
    params = [fts_query]
    if speaker:
        sql += " AND u.speaker LIKE ?"
        params.append("%" + speaker + "%")
    if video_id:
        sql += " AND u.video_id = ?"
        params.append(video_id)
    if chapter is not None:
        sql += " AND u.chapter = ?"
        params.append(chapter)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("No results found for: %s" % query)
        return

    print("Found %d results for '%s':\n" % (len(rows), query))
    for row in rows:
        vid, idx, spk, text, start, end, ch, title = row
        ts = fmt_ts(start)
        link = yt_link(vid, start)
        display_text = text if len(text) < 120 else text[:117] + "..."
        print("  [%s] Ch%s %-10s %s" % (ts, ch, spk, display_text))
        print("    %s" % link)
        if context > 0:
            ctx_rows = conn.execute(
                "SELECT speaker, text, start_sec FROM utterances WHERE video_id = ? AND idx BETWEEN ? AND ? AND idx != ? ORDER BY idx",
                (vid, idx - context, idx + context, idx)
            ).fetchall()
            for cr in ctx_rows:
                ctx_text = cr[1] if len(cr[1]) < 100 else cr[1][:97] + "..."
                print("      > %-10s %s" % (cr[0], ctx_text))
        print()


def show_stats(conn):
    vids = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    utts = conn.execute("SELECT COUNT(*) FROM utterances").fetchone()[0]
    chs = conn.execute("SELECT COUNT(*) FROM chapters").fetchone()[0]
    print("Parker Pipeline Database Stats")
    print("=" * 40)
    print("  Videos:     %d" % vids)
    print("  Utterances: %d" % utts)
    print("  Chapters:   %d" % chs)
    print()
    for row in conn.execute("SELECT video_id, title, utterance_count, chapter_count, total_duration_sec FROM videos"):
        vid, title, uc, cc, dur = row
        print("  %s" % title)
        print("    ID: %s | %d utterances | %d chapters | %dm" % (vid, uc, cc, dur // 60))
    print("\nSpeaker breakdown:")
    for row in conn.execute("SELECT speaker, COUNT(*) as cnt FROM utterances GROUP BY speaker ORDER BY cnt DESC LIMIT 10"):
        print("  %-12s %d utterances" % (row[0], row[1]))


def show_chapters(conn, video_id=None):
    sql = "SELECT c.*, v.title FROM chapters c JOIN videos v ON v.video_id = c.video_id"
    params = []
    if video_id:
        sql += " WHERE c.video_id = ?"
        params.append(video_id)
    sql += " ORDER BY c.video_id, c.chapter"
    rows = conn.execute(sql, params).fetchall()
    current_vid = None
    for row in rows:
        _, vid, ch, si, ei, st, et, dur, title = row
        if vid != current_vid:
            print("\n%s (%s)" % (title, vid))
            print("-" * 60)
            current_vid = vid
        sample = conn.execute(
            "SELECT text FROM utterances WHERE video_id = ? AND chapter = ? AND speaker = 'parker' LIMIT 1",
            (vid, ch)
        ).fetchone()
        sample_text = ""
        if sample:
            sample_text = sample[0][:60] + "..." if len(sample[0]) > 60 else sample[0]
        print("  Ch%2d: %s - %s (%2dm) %s" % (ch, fmt_ts(st), fmt_ts(et), dur / 60, sample_text))


def main():
    parser = argparse.ArgumentParser(description="Search Parker livestream transcripts")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--speaker", "-s", help="Filter by speaker (parker, guest)")
    parser.add_argument("--video", "-v", help="Filter by video ID")
    parser.add_argument("--chapter", "-c", type=int, help="Filter by chapter number")
    parser.add_argument("--limit", "-n", type=int, default=20, help="Max results")
    parser.add_argument("--context", type=int, default=1, help="Context utterances around match")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--chapters", action="store_true", help="Show chapter listing")
    parser.add_argument("--db", default=DB_PATH, help="Database path")
    args = parser.parse_args()
    conn = sqlite3.connect(args.db)
    if args.stats:
        show_stats(conn)
    elif args.chapters:
        show_chapters(conn, args.video)
    elif args.query:
        search(conn, args.query, speaker=args.speaker, video_id=args.video,
               chapter=args.chapter, limit=args.limit, context=args.context)
    else:
        parser.print_help()
    conn.close()


if __name__ == "__main__":
    main()
