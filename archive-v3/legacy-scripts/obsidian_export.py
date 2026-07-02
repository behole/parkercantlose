#!/usr/bin/env python3
"""Phase 5: Obsidian - Generate stream notes with chapters and timestamps.

Creates a markdown note for each video in the Obsidian vault with:
- Stream metadata
- Chapter listing with YouTube timestamp links
- Key quotes per chapter
- Topic tags

Usage:
    python3 obsidian_export.py [--db PATH] [--vault PATH] [--video VIDEO_ID]
"""

import argparse
import json
import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime


DB_PATH = "./data/parker.db"
VAULT_PATH = os.path.expanduser("~/2026L/2026L/the-factory/01_Projects/Parker-Pipeline")


def fmt_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def yt_link(video_id, seconds):
    return "https://youtu.be/%s?t=%d" % (video_id, int(seconds))


def get_chapter_summary(conn, video_id, chapter):
    """Get a text preview of a chapter from Parker's utterances."""
    rows = conn.execute(
        "SELECT text FROM utterances WHERE video_id = ? AND chapter = ? AND speaker = 'parker' ORDER BY start_sec LIMIT 5",
        (video_id, chapter)
    ).fetchall()
    texts = [r[0] for r in rows]
    combined = " ".join(texts)
    if len(combined) > 200:
        combined = combined[:197] + "..."
    return combined


def get_chapter_topics(conn, video_id, chapter):
    """Extract likely topics from chapter text using keyword matching."""
    topic_keywords = {
        "economy": ["economy", "inflation", "gdp", "jobs", "unemployment", "wages", "tariff", "trade", "tax"],
        "immigration": ["immigration", "immigrant", "border", "deport", "asylum", "migrant", "undocumented", "illegal"],
        "election": ["election", "vote", "ballot", "democrat", "republican", "candidate", "poll"],
        "healthcare": ["healthcare", "insurance", "medical", "hospital", "medicare", "medicaid"],
        "education": ["education", "school", "college", "student", "university", "teacher"],
        "environment": ["climate", "environment", "energy", "oil", "gas", "renewable", "green"],
        "military": ["military", "war", "army", "troops", "defense", "nato", "foreign policy"],
        "social-issues": ["abortion", "gun", "lgbtq", "trans", "gender", "religion", "marriage", "race", "racism"],
    }

    rows = conn.execute(
        "SELECT text FROM utterances WHERE video_id = ? AND chapter = ?",
        (video_id, chapter)
    ).fetchall()
    all_text = " ".join(r[0].lower() for r in rows)

    found = []
    for topic, keywords in topic_keywords.items():
        count = sum(all_text.count(kw) for kw in keywords)
        if count >= 2:
            found.append((topic, count))
    found.sort(key=lambda x: -x[1])
    return [t[0] for t in found[:3]]


def generate_note(conn, video_id, vault_path):
    """Generate an Obsidian note for a video."""
    vid_row = conn.execute(
        "SELECT * FROM videos WHERE video_id = ?", (video_id,)
    ).fetchone()
    if not vid_row:
        print("Video %s not found in DB" % video_id)
        return None

    vid, url, title, author, is_auto, duration, utt_count, ch_count, speakers_json = vid_row
    speakers = json.loads(speakers_json)

    chapters = conn.execute(
        "SELECT * FROM chapters WHERE video_id = ? ORDER BY chapter",
        (video_id,)
    ).fetchall()

    # Collect all topics for frontmatter tags
    all_topics = set()

    # Build note
    lines = []
    lines.append("---")
    lines.append("title: \"%s\"" % title.replace('"', '\\"'))
    lines.append("author: %s" % author)
    lines.append("video_id: %s" % video_id)
    lines.append("url: %s" % url)
    lines.append("duration: %s" % fmt_ts(duration))
    lines.append("utterances: %d" % utt_count)
    lines.append("chapters: %d" % ch_count)
    lines.append("auto_generated: %s" % ("true" if is_auto else "false"))
    lines.append("type: livestream-transcript")
    lines.append("date: %s" % datetime.now().strftime("%Y-%m-%d"))

    # Build chapter outline
    lines.append("---")
    lines.append("")
    lines.append("# %s" % title)
    lines.append("")
    lines.append("**Channel:** [%s](%s)" % (author, "https://www.youtube.com/@Parkergetajob"))
    lines.append("**Duration:** %s | **Utterances:** %d | **Chapters:** %d" % (fmt_ts(duration), utt_count, ch_count))
    lines.append("**Watch:** [YouTube](%s)" % url)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Chapters")
    lines.append("")

    for ch_row in chapters:
        _, _, ch_num, start_idx, end_idx, start_time, end_time, ch_dur = ch_row
        ts_start = fmt_ts(start_time)
        ts_end = fmt_ts(end_time)
        link = yt_link(video_id, start_time)
        topics = get_chapter_topics(conn, video_id, ch_num)
        all_topics.update(topics)
        summary = get_chapter_summary(conn, video_id, ch_num)

        topic_tags = " ".join("#%s" % t for t in topics) if topics else ""

        lines.append("### Chapter %d — [%s](%s) (%dm)" % (ch_num, ts_start, link, ch_dur / 60))
        if topic_tags:
            lines.append(topic_tags)
        lines.append("")
        lines.append("> %s" % summary)
        lines.append("")

        # Get a few notable exchanges (longer utterances = more substantive)
        notable = conn.execute(
            "SELECT speaker, text, start_sec FROM utterances WHERE video_id = ? AND chapter = ? AND length(text) > 100 ORDER BY length(text) DESC LIMIT 3",
            (video_id, ch_num)
        ).fetchall()
        if notable:
            lines.append("**Key exchanges:**")
            for spk, text, start in notable:
                ts = fmt_ts(start)
                display = text[:150] + "..." if len(text) > 150 else text
                lines.append("- [%s](%s) **%s**: %s" % (ts, yt_link(video_id, start), spk, display))
            lines.append("")

    # Add tags to frontmatter (insert before closing ---)
    if all_topics:
        tag_line = "tags: [parker, livestream, debate, %s]" % ", ".join(sorted(all_topics))
    else:
        tag_line = "tags: [parker, livestream, debate]"
    # Insert tags into frontmatter
    for i, line in enumerate(lines):
        if line == "type: livestream-transcript":
            lines.insert(i + 1, tag_line)
            break

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by Parker Pipeline on %s*" % datetime.now().strftime("%Y-%m-%d %H:%M"))

    content = "\n".join(lines)

    # Save to vault
    Path(vault_path).mkdir(parents=True, exist_ok=True)
    safe_title = title.replace("/", "-").replace(":", " -")[:80]
    filename = "%s — %s.md" % (safe_title, video_id)
    filepath = os.path.join(vault_path, filename)
    with open(filepath, "w") as f:
        f.write(content)
    print("  Generated: %s" % filepath)
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Export transcripts to Obsidian notes")
    parser.add_argument("--db", default=DB_PATH, help="Database path")
    parser.add_argument("--vault", default=VAULT_PATH, help="Obsidian vault output directory")
    parser.add_argument("--video", "-v", help="Export specific video (default: all)")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    if args.video:
        generate_note(conn, args.video, args.vault)
    else:
        rows = conn.execute("SELECT video_id FROM videos").fetchall()
        print("Exporting %d videos to Obsidian..." % len(rows))
        for row in rows:
            generate_note(conn, row[0], args.vault)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
