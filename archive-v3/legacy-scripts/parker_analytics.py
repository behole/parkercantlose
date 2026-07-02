#!/usr/bin/env python3
"""Parker Pipeline Analytics - Rich queries, mention counts, keyword analysis.

Usage:
    python3 parker_analytics.py mentions "epstein"
    python3 parker_analytics.py mentions "epstein,tariff,immigration" --by-guest
    python3 parker_analytics.py mentions "epstein" --by-video
    python3 parker_analytics.py guest-stats [VIDEO_ID]
    python3 parker_analytics.py topics [VIDEO_ID]
    python3 parker_analytics.py transcript VIDEO_ID [--chapter N] [--speaker guest_3]
    python3 parker_analytics.py export-dashboard [--output FILE]
"""

import argparse
import json
import sqlite3
import sys
import re
from collections import Counter, defaultdict

DB_PATH = "./data/parker.db"

TOPIC_KEYWORDS = {
    "economy": ["economy", "inflation", "gdp", "jobs", "unemployment", "wages", "tariff", "tariffs", "trade", "tax", "taxes", "debt", "deficit", "stock market"],
    "immigration": ["immigration", "immigrant", "immigrants", "border", "deport", "deportation", "asylum", "migrant", "undocumented", "illegal alien"],
    "election": ["election", "vote", "voted", "voting", "ballot", "democrat", "republican", "candidate", "poll", "polls", "electoral"],
    "healthcare": ["healthcare", "health care", "insurance", "medical", "hospital", "medicare", "medicaid", "obamacare"],
    "education": ["education", "school", "schools", "college", "student", "university", "teacher"],
    "environment": ["climate", "climate change", "environment", "energy", "oil", "gas", "renewable", "green new deal", "fossil fuel"],
    "military": ["military", "war", "army", "troops", "defense", "nato", "foreign policy", "ukraine", "israel", "gaza"],
    "social-issues": ["abortion", "gun", "guns", "lgbtq", "trans", "transgender", "gender", "religion", "marriage", "race", "racism", "racist", "police", "blm"],
    "conspiracy": ["epstein", "qanon", "deep state", "rigged", "stolen election", "pizzagate", "hunter biden", "laptop"],
    "media": ["fake news", "mainstream media", "cnn", "fox news", "msnbc", "media bias", "censorship"],
    "january-6th": ["january 6", "jan 6", "capitol", "insurrection", "riot"],
    "covid": ["covid", "vaccine", "vaccines", "vaccination", "mask", "masks", "lockdown", "pandemic", "fauci"],
}


def fmt_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def yt_link(video_id, seconds):
    return "https://youtu.be/%s?t=%d" % (video_id, int(seconds))


def cmd_mentions(conn, args):
    """Count keyword mentions across transcripts."""
    keywords = [k.strip().lower() for k in args.keywords.split(",")]

    for keyword in keywords:
        print("\n=== Mentions of '%s' ===" % keyword)

        # Find all utterances containing the keyword
        rows = conn.execute(
            "SELECT u.video_id, u.speaker, u.text, u.start_sec, u.chapter, v.title "
            "FROM utterances u JOIN videos v ON v.video_id = u.video_id "
            "WHERE lower(u.text) LIKE ? ORDER BY u.video_id, u.start_sec",
            ("%" + keyword + "%",)
        ).fetchall()

        if not rows:
            print("  No mentions found.")
            continue

        total = len(rows)
        by_speaker = Counter()
        by_video = Counter()
        by_guest_video = defaultdict(Counter)

        for vid, spk, text, start, ch, title in rows:
            # Count actual occurrences in text (not just 1 per utterance)
            count = text.lower().count(keyword)
            by_speaker[spk] += count
            by_video[vid] += count
            by_guest_video[vid][spk] += count

        total_mentions = sum(by_speaker.values())
        print("  Total: %d mentions in %d utterances" % (total_mentions, total))

        if args.by_guest:
            print("\n  By speaker:")
            for spk, count in sorted(by_speaker.items(), key=lambda x: -x[1]):
                print("    %-15s %d" % (spk, count))

        if args.by_video:
            print("\n  By video:")
            for vid, count in sorted(by_video.items(), key=lambda x: -x[1]):
                title = conn.execute("SELECT title FROM videos WHERE video_id = ?", (vid,)).fetchone()[0]
                print("    %s (%s): %d" % (title[:50], vid, count))
                if args.by_guest:
                    for spk, sc in sorted(by_guest_video[vid].items(), key=lambda x: -x[1])[:5]:
                        print("      %-15s %d" % (spk, sc))

        if not args.by_guest and not args.by_video:
            # Default: show by speaker
            print("\n  By speaker:")
            for spk, count in sorted(by_speaker.items(), key=lambda x: -x[1])[:15]:
                print("    %-15s %d" % (spk, count))

        # Show sample matches
        if args.show_context:
            print("\n  Sample matches:")
            for vid, spk, text, start, ch, title in rows[:5]:
                ts = fmt_ts(start)
                link = yt_link(vid, start)
                snippet = text[:120] + "..." if len(text) > 120 else text
                print("    [%s] %s: %s" % (ts, spk, snippet))
                print("      %s" % link)


def cmd_guest_stats(conn, args):
    """Show per-guest statistics."""
    video_filter = ""
    params = []
    if args.video:
        video_filter = "WHERE u.video_id = ?"
        params = [args.video]

    rows = conn.execute("""
        SELECT u.video_id, u.speaker, COUNT(*) as utt_count,
               SUM(length(u.text)) as total_chars,
               MIN(u.start_sec) as first_seen,
               MAX(u.end_sec) as last_seen,
               v.title
        FROM utterances u
        JOIN videos v ON v.video_id = u.video_id
        %s
        GROUP BY u.video_id, u.speaker
        ORDER BY u.video_id, first_seen
    """ % video_filter, params).fetchall()

    current_vid = None
    for vid, spk, utt_count, chars, first, last, title in rows:
        if vid != current_vid:
            print("\n%s (%s)" % (title, vid))
            print("-" * 70)
            print("  %-15s %5s %8s %10s %s" % ("Speaker", "Utts", "Words~", "Duration", "Time Range"))
            current_vid = vid
        words = chars // 5  # rough word estimate
        duration = last - first
        print("  %-15s %5d %8d %8dm   %s - %s" % (
            spk, utt_count, words, duration / 60,
            fmt_ts(first), fmt_ts(last)))


def cmd_topics(conn, args):
    """Analyze topic distribution across streams."""
    video_filter = ""
    params = []
    if args.video:
        video_filter = "WHERE u.video_id = ?"
        params = [args.video]

    # Get all text grouped by video and speaker type
    rows = conn.execute("""
        SELECT u.video_id, u.speaker, u.text, v.title
        FROM utterances u
        JOIN videos v ON v.video_id = u.video_id
        %s
    """ % video_filter, params).fetchall()

    # Aggregate text by video
    by_video = defaultdict(lambda: {"texts": [], "title": ""})
    for vid, spk, text, title in rows:
        by_video[vid]["texts"].append(text.lower())
        by_video[vid]["title"] = title

    for vid, data in by_video.items():
        all_text = " ".join(data["texts"])
        print("\n%s (%s)" % (data["title"], vid))
        print("-" * 60)

        topic_counts = {}
        for topic, keywords in TOPIC_KEYWORDS.items():
            count = sum(all_text.count(kw) for kw in keywords)
            if count > 0:
                topic_counts[topic] = count

        for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
            bar = "#" * min(count // 2, 40)
            print("  %-15s %4d %s" % (topic, count, bar))


def cmd_transcript(conn, args):
    """Print full transcript for a video."""
    sql = "SELECT speaker, text, start_sec, chapter FROM utterances WHERE video_id = ?"
    params = [args.video]
    if args.chapter is not None:
        sql += " AND chapter = ?"
        params.append(args.chapter)
    if args.speaker:
        sql += " AND speaker = ?"
        params.append(args.speaker)
    sql += " ORDER BY start_sec"

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("No utterances found.")
        return

    title = conn.execute("SELECT title FROM videos WHERE video_id = ?", (args.video,)).fetchone()
    print("%s (%s)" % (title[0] if title else "Unknown", args.video))
    if args.chapter is not None:
        print("Chapter: %d" % args.chapter)
    if args.speaker:
        print("Speaker: %s" % args.speaker)
    print("=" * 60)
    print()

    for spk, text, start, ch in rows:
        ts = fmt_ts(start)
        print("[%s] Ch%s %-15s %s" % (ts, ch, spk, text))


def cmd_export_dashboard(conn, args):
    """Export data in dashboard-ready JSON format."""
    export = {
        "videos": [],
        "guest_stats": [],
        "topic_analysis": [],
        "mention_timeseries": [],
    }

    # Videos
    for row in conn.execute("SELECT * FROM videos"):
        vid, url, title, author, auto, dur, utts, chs, speakers = row
        export["videos"].append({
            "video_id": vid, "title": title, "duration_min": dur // 60,
            "utterances": utts, "chapters": chs,
            "speakers": json.loads(speakers),
        })

    # Guest stats per video
    rows = conn.execute("""
        SELECT u.video_id, u.speaker, COUNT(*) as utt_count,
               SUM(length(u.text)) as total_chars,
               MIN(u.start_sec) as first_seen,
               MAX(u.end_sec) as last_seen
        FROM utterances u
        GROUP BY u.video_id, u.speaker
        ORDER BY u.video_id, first_seen
    """).fetchall()
    for vid, spk, utt_count, chars, first, last in rows:
        export["guest_stats"].append({
            "video_id": vid, "speaker": spk, "utterances": utt_count,
            "est_words": chars // 5, "duration_min": round((last - first) / 60, 1),
            "start_time": round(first, 1), "end_time": round(last, 1),
        })

    # Topic analysis per video
    for vid_row in conn.execute("SELECT video_id, title FROM videos"):
        vid, title = vid_row
        texts = conn.execute("SELECT text FROM utterances WHERE video_id = ?", (vid,)).fetchall()
        all_text = " ".join(t[0].lower() for t in texts)
        topics = {}
        for topic, keywords in TOPIC_KEYWORDS.items():
            count = sum(all_text.count(kw) for kw in keywords)
            if count > 0:
                topics[topic] = count
        export["topic_analysis"].append({
            "video_id": vid, "title": title, "topics": topics,
        })

    # Time series: topic mentions per 10-min block per video
    for vid_row in conn.execute("SELECT video_id, title, total_duration_sec FROM videos"):
        vid, title, dur = vid_row
        block_size = 600  # 10 min blocks
        blocks = []
        for block_start in range(0, dur, block_size):
            block_end = block_start + block_size
            texts = conn.execute(
                "SELECT text FROM utterances WHERE video_id = ? AND start_sec >= ? AND start_sec < ?",
                (vid, block_start, block_end)
            ).fetchall()
            all_text = " ".join(t[0].lower() for t in texts)
            block_topics = {}
            for topic, keywords in TOPIC_KEYWORDS.items():
                count = sum(all_text.count(kw) for kw in keywords)
                if count > 0:
                    block_topics[topic] = count
            blocks.append({
                "start_min": block_start // 60,
                "end_min": block_end // 60,
                "topics": block_topics,
            })
        export["mention_timeseries"].append({
            "video_id": vid, "title": title, "blocks": blocks,
        })

    outfile = args.output or "data/dashboard-export.json"
    with open(outfile, "w") as f:
        json.dump(export, f, indent=2)
    print("Exported dashboard data to %s" % outfile)
    print("  Videos: %d" % len(export["videos"]))
    print("  Guest stats: %d entries" % len(export["guest_stats"]))
    print("  Topic analysis: %d videos" % len(export["topic_analysis"]))
    print("  Time series: %d videos" % len(export["mention_timeseries"]))


def main():
    parser = argparse.ArgumentParser(description="Parker Pipeline Analytics")
    sub = parser.add_subparsers(dest="command")

    # mentions
    p_mentions = sub.add_parser("mentions", help="Count keyword mentions")
    p_mentions.add_argument("keywords", help="Comma-separated keywords")
    p_mentions.add_argument("--by-guest", action="store_true", help="Break down by guest")
    p_mentions.add_argument("--by-video", action="store_true", help="Break down by video")
    p_mentions.add_argument("--show-context", action="store_true", help="Show sample matches")
    p_mentions.add_argument("--db", default=DB_PATH)

    # guest-stats
    p_gs = sub.add_parser("guest-stats", help="Per-guest statistics")
    p_gs.add_argument("video", nargs="?", help="Video ID (optional)")
    p_gs.add_argument("--db", default=DB_PATH)

    # topics
    p_topics = sub.add_parser("topics", help="Topic distribution")
    p_topics.add_argument("video", nargs="?", help="Video ID (optional)")
    p_topics.add_argument("--db", default=DB_PATH)

    # transcript
    p_tr = sub.add_parser("transcript", help="Print full transcript")
    p_tr.add_argument("video", help="Video ID")
    p_tr.add_argument("--chapter", "-c", type=int, help="Filter by chapter")
    p_tr.add_argument("--speaker", "-s", help="Filter by speaker")
    p_tr.add_argument("--db", default=DB_PATH)

    # export-dashboard
    p_exp = sub.add_parser("export-dashboard", help="Export dashboard JSON")
    p_exp.add_argument("--output", "-o", help="Output file path")
    p_exp.add_argument("--db", default=DB_PATH)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    conn = sqlite3.connect(args.db)

    if args.command == "mentions":
        cmd_mentions(conn, args)
    elif args.command == "guest-stats":
        cmd_guest_stats(conn, args)
    elif args.command == "topics":
        cmd_topics(conn, args)
    elif args.command == "transcript":
        cmd_transcript(conn, args)
    elif args.command == "export-dashboard":
        cmd_export_dashboard(conn, args)

    conn.close()


if __name__ == "__main__":
    main()

