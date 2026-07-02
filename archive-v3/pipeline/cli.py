#!/usr/bin/env python3
"""Parker Pipeline v4 — unified CLI for transcript ingestion and analysis.

Usage:
    parker status [VIDEO_ID]        — Show pipeline state for all or one video
    parker add <url_or_id>          — Add video to queue, fetch transcript
    parker add --batch <file>       — Batch add from file
    parker run <url_or_id>          — Run full pipeline: fetch → structure → store
    parker run <url_or_id> --from <phase>  — Run from a specific phase
    parker retry <video_id> <phase> — Re-run one phase
    parker reset <video_id> [phase] — Reset phase(s) to pending
    parker migrate [--old-db PATH]  — Migrate data from old parker.db

Status icons:  ✅ done  ⏳ pending  ❌ failed  🔄 running  ⏭️ skipped
"""

import argparse
import sys
import os

# Add project root to path so pipeline imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.db import get_conn, init_db, migrate_old_db
from pipeline.state import (
    ensure_state_rows, get_status, format_status,
    needs_phase, reset_phase, set_phase,
)
from pipeline import fetch as fetch_phase
from pipeline import structure as structure_phase
from pipeline import store as store_phase
from pipeline import DB_PATH


def cmd_status(args):
    conn = get_conn()
    init_db(conn)
    rows = get_status(conn, video_id=args.video_id)
    print(format_status(rows, detail=bool(args.video_id)))
    conn.close()


def cmd_add(args):
    conn = get_conn()
    init_db(conn)

    if args.batch:
        with open(args.batch) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        urls = [args.video]

    for url_or_id in urls:
        try:
            vid = fetch_phase.extract_video_id(url_or_id)
        except ValueError as e:
            print(f"  ✗ {url_or_id}: {e}")
            continue

        # Check if already exists
        existing = conn.execute(
            "SELECT video_id FROM videos WHERE video_id=?",
            (vid,),
        ).fetchone()

        if existing:
            print(f"  ⏭️  {vid}: already in pipeline")
            continue

        ensure_state_rows(conn, vid)
        print(f"  + {vid} added to queue")

        # Fetch immediately
        try:
            fetch_phase.run(conn, vid, f"https://youtube.com/watch?v={vid}")
            print(f"  ✅ {vid} fetched")
        except Exception as e:
            print(f"  ❌ {vid} fetch failed: {e}")

    conn.close()


def cmd_run(args):
    conn = get_conn()
    init_db(conn)

    try:
        vid = fetch_phase.extract_video_id(args.video)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    ensure_state_rows(conn, vid)

    phase_order = ["fetch", "structure", "store"]
    start = False

    for phase in phase_order:
        if args.from_phase and phase == args.from_phase:
            start = True
        if args.from_phase and not start:
            state = conn.execute(
                "SELECT status FROM pipeline_state WHERE video_id=? AND phase=?",
                (vid, phase),
            ).fetchone()
            if state and state["status"] != "done":
                if args.from_phase != phase:
                    set_phase(conn, vid, phase, "skipped")
            continue

        needs, err = needs_phase(conn, vid, phase)
        if not needs:
            print(f"\n[{phase}] ✅ already done, skipping")
            continue

        print(f"\n{'='*50}")
        print(f"[{phase}] Running for {vid}...")
        print(f"{'='*50}")

        try:
            if phase == "fetch":
                fetch_phase.run(conn, vid, f"https://youtube.com/watch?v={vid}")
            elif phase == "structure":
                structure_phase.run(conn, vid)
            elif phase == "store":
                store_phase.run(conn, vid)
            print(f"  ✅ {phase} complete")
        except Exception as e:
            print(f"  ❌ {phase} failed: {e}")

    conn.close()


def cmd_retry(args):
    conn = get_conn()
    init_db(conn)

    vid = args.video_id
    phase = args.phase

    if phase not in ["fetch", "structure", "store"]:
        print(f"Unknown phase: {phase}. Use: fetch, structure, store")
        sys.exit(1)

    # Reset the phase
    reset_phase(conn, vid, phase)
    print(f"  ↻ {vid}/{phase} reset to pending")

    # Run it
    print(f"\n{'='*50}")
    print(f"[{phase}] Re-running for {vid}...")
    print(f"{'='*50}")

    try:
        if phase == "fetch":
            fetch_phase.run(conn, vid, f"https://youtube.com/watch?v={vid}")
        elif phase == "structure":
            structure_phase.run(conn, vid)
        elif phase == "store":
            store_phase.run(conn, vid)
        print(f"  ✅ {phase} complete")
    except Exception as e:
        print(f"  ❌ {phase} failed: {e}")

    conn.close()


def cmd_reset(args):
    conn = get_conn()
    init_db(conn)
    reset_phase(conn, args.video_id, args.phase)
    what = f"/{args.phase}" if args.phase else " (all phases)"
    print(f"  ↻ {args.video_id}{what} reset")
    conn.close()


def cmd_migrate(args):
    conn = get_conn()
    init_db(conn)

    old_paths = args.old_db or []
    if not old_paths:
        # Auto-detect old DBs
        import glob
        candidates = glob.glob(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "db/parker.db"
        ))
        if not candidates:
            candidates = glob.glob(os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data/parker.db"
            ))
        old_paths = candidates

    for path in old_paths:
        if os.path.exists(path) and path != str(DB_PATH):
            ok, msg = migrate_old_db(conn, path)
            print(f"  {path}: {msg}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Parker Pipeline v4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Status:  ✅ done  ⏳ pending  ❌ failed  🔄 running  ⏭️ skipped",
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    # status
    p_status = sub.add_parser("status", help="Show pipeline status")
    p_status.add_argument("video_id", nargs="?", help="Filter to one video")

    # add
    p_add = sub.add_parser("add", help="Add video to pipeline")
    p_add.add_argument("video", nargs="?", help="YouTube URL or video ID")
    p_add.add_argument("--batch", help="File with one URL/ID per line")

    # run
    p_run = sub.add_parser("run", help="Run pipeline phases")
    p_run.add_argument("video", help="YouTube URL or video ID")
    p_run.add_argument("--from", dest="from_phase",
                       help="Start from phase: fetch, structure, store")

    # retry
    p_retry = sub.add_parser("retry", help="Re-run a specific phase")
    p_retry.add_argument("video_id", help="Video ID")
    p_retry.add_argument("phase", help="Phase to retry: fetch, structure, store")

    # reset
    p_reset = sub.add_parser("reset", help="Reset phase(s) to pending")
    p_reset.add_argument("video_id", help="Video ID")
    p_reset.add_argument("phase", nargs="?", help="Phase to reset (omit for all)")

    # migrate
    p_migrate = sub.add_parser("migrate", help="Migrate data from old DB")
    p_migrate.add_argument("--old-db", nargs="+", help="Path(s) to old parker.db")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "status": cmd_status,
        "add": cmd_add,
        "run": cmd_run,
        "retry": cmd_retry,
        "reset": cmd_reset,
        "migrate": cmd_migrate,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
