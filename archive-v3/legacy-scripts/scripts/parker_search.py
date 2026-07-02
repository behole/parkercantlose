#!/usr/bin/env python3
"""
Phase 4 - Query: CLI search tool for Parker livestream transcripts.

Usage:
  parker-search "tariffs"                     # basic text search
  parker-search "tariffs" --speaker parker     # filter by speaker
  parker-search "tariffs" --topic economy      # filter by topic (future)
  parker-search --chapter Guest_40             # show all utterances for a guest
  parker-search --list-chapters                # list all chapters
  parker-search --stats                        # show database stats
  parker-search --context 2 "tariffs"          # show N utterances before/after
"""
import argparse
import sqlite3
import os
import sys
import textwrap

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'parker.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS or MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def yt_url(video_id, seconds):
    """Generate YouTube URL with timestamp."""
    return f"https://youtu.be/{video_id}?t={int(seconds)}"

def search(args):
    """Full-text search across utterances."""
    conn = get_conn()
    
    query_parts = []
    params = []
    
    # Build FTS query
    fts_query = args.query
    
    # Base query with FTS
    sql = """
        SELECT u.id, u.video_id, u.speaker, u.text, u.start_seconds, 
               u.end_seconds, u.chapter_guest
        FROM utterances u
        JOIN utterances_fts fts ON u.id = fts.rowid
        WHERE utterances_fts MATCH ?
    """
    params.append(fts_query)
    
    # Speaker filter
    if args.speaker:
        sql += " AND LOWER(u.speaker) = LOWER(?)"
        params.append(args.speaker)
    
    sql += " ORDER BY u.start_seconds"
    
    if args.limit:
        sql += f" LIMIT {args.limit}"
    
    results = conn.execute(sql, params).fetchall()
    
    if not results:
        print(f"No results for '{args.query}'")
        return
    
    print(f"Found {len(results)} results for '{args.query}'")
    if args.speaker:
        print(f"  (filtered to speaker: {args.speaker})")
    print()
    
    for r in results:
        ts = format_timestamp(r["start_seconds"])
        url = yt_url(r["video_id"], r["start_seconds"])
        
        # Wrap text
        text = r["text"]
        if len(text) > 200 and not args.full:
            text = text[:200] + "..."
        
        print(f"[{ts}] {r['speaker']} ({r['chapter_guest'] or '?'}):")
        for line in textwrap.wrap(text, width=80):
            print(f"  {line}")
        print(f"  -> {url}")
        
        # Context: show surrounding utterances
        if args.context and args.context > 0:
            context_results = conn.execute("""
                SELECT speaker, text, start_seconds FROM utterances
                WHERE video_id = ? AND id BETWEEN ? AND ?
                ORDER BY start_seconds
            """, (r["video_id"], r["id"] - args.context, r["id"] + args.context)).fetchall()
            
            for cr in context_results:
                if cr["start_seconds"] != r["start_seconds"]:
                    ctx_ts = format_timestamp(cr["start_seconds"])
                    ctx_text = cr["text"][:120] + "..." if len(cr["text"]) > 120 else cr["text"]
                    print(f"    [{ctx_ts}] {cr['speaker']}: {ctx_text}")
        
        print()
    
    conn.close()


def list_chapters(args):
    """List all chapters (guest conversations)."""
    conn = get_conn()
    
    results = conn.execute("""
        SELECT c.*, v.video_id 
        FROM chapters c
        JOIN videos v ON c.video_id = v.video_id
        ORDER BY c.video_id, c.start_seconds
    """).fetchall()
    
    print(f"{'Guest':<14} {'Start':>8} {'End':>8} {'Duration':>8} {'Utterances':>10}  Link")
    print("-" * 85)
    
    for r in results:
        start_ts = format_timestamp(r["start_seconds"])
        end_ts = format_timestamp(r["end_seconds"]) if r["end_seconds"] else "?"
        dur = format_timestamp(r["duration_seconds"]) if r["duration_seconds"] else "?"
        url = yt_url(r["video_id"], r["start_seconds"])
        
        # Highlight substantial chapters
        marker = " *" if r["duration_seconds"] and r["duration_seconds"] > 120 else ""
        
        print(f"{r['guest']:<14} {start_ts:>8} {end_ts:>8} {dur:>8} {r['utterance_count']:>10}  {url}{marker}")
    
    conn.close()


def show_chapter(args):
    """Show all utterances for a specific guest/chapter."""
    conn = get_conn()
    
    results = conn.execute("""
        SELECT speaker, text, start_seconds, end_seconds, video_id
        FROM utterances
        WHERE chapter_guest = ?
        ORDER BY start_seconds
    """, (args.chapter,)).fetchall()
    
    if not results:
        print(f"No utterances found for '{args.chapter}'")
        return
    
    print(f"=== {args.chapter} — {len(results)} utterances ===\n")
    
    for r in results:
        ts = format_timestamp(r["start_seconds"])
        text = r["text"]
        if len(text) > 300 and not args.full:
            text = text[:300] + "..."
        print(f"[{ts}] {r['speaker']}:")
        for line in textwrap.wrap(text, width=80):
            print(f"  {line}")
        print()
    
    conn.close()


def show_stats(args):
    """Show database statistics."""
    conn = get_conn()
    
    videos = conn.execute("SELECT COUNT(*) as c FROM videos").fetchone()["c"]
    utterances = conn.execute("SELECT COUNT(*) as c FROM utterances").fetchone()["c"]
    chapters = conn.execute("SELECT COUNT(*) as c FROM chapters").fetchone()["c"]
    words = conn.execute("SELECT SUM(LENGTH(text) - LENGTH(REPLACE(text, ' ', '')) + 1) as c FROM utterances").fetchone()["c"]
    
    speakers = conn.execute("""
        SELECT speaker, COUNT(*) as c, SUM(LENGTH(text)) as chars
        FROM utterances GROUP BY speaker ORDER BY c DESC LIMIT 10
    """).fetchall()
    
    db_size = os.path.getsize(DB_PATH)
    
    print(f"Parker Pipeline Database Stats")
    print(f"{'='*40}")
    print(f"  Videos:     {videos}")
    print(f"  Chapters:   {chapters}")
    print(f"  Utterances: {utterances}")
    print(f"  Words:      ~{words:,}")
    print(f"  DB Size:    {db_size/1024:.0f} KB")
    print(f"\nTop speakers by utterance count:")
    for s in speakers:
        print(f"  {s['speaker']:<14} {s['c']:>5} utterances  ({s['chars']:>6} chars)")
    
    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Search Parker livestream transcripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "tariffs"                    Search for 'tariffs'
  %(prog)s "military" --speaker parker  Parker talking about military
  %(prog)s --chapter Guest_40           Show full Guest_40 conversation
  %(prog)s --list-chapters              List all guest conversations
  %(prog)s --stats                      Database statistics
  %(prog)s "economy" --context 2        Show 2 utterances of context
        """
    )
    
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--speaker", "-s", help="Filter by speaker name")
    parser.add_argument("--chapter", "-c", help="Show utterances for a chapter/guest")
    parser.add_argument("--list-chapters", "-l", action="store_true", help="List all chapters")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--context", "-C", type=int, default=0, help="Context utterances around matches")
    parser.add_argument("--limit", "-n", type=int, default=20, help="Max results (default: 20)")
    parser.add_argument("--full", "-f", action="store_true", help="Show full text (no truncation)")
    
    args = parser.parse_args()
    
    if args.stats:
        show_stats(args)
    elif args.list_chapters:
        list_chapters(args)
    elif args.chapter:
        show_chapter(args)
    elif args.query:
        search(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
