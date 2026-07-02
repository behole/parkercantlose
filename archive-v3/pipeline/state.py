"""Pipeline state machine — phase transitions, status queries."""
from datetime import datetime, timezone
from . import PHASES, STATUSES
from .db import get_conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def ensure_state_rows(conn, video_id):
    """Create pending state rows for all phases if they don't exist."""
    for phase in PHASES:
        conn.execute(
            "INSERT OR IGNORE INTO pipeline_state (video_id, phase, status) VALUES (?, ?, 'pending')",
            (video_id, phase),
        )
    conn.commit()


def set_phase(conn, video_id, phase, status, error=None):
    """Set a phase's status. Auto-sets started_at / finished_at."""
    now = _now()
    existing = conn.execute(
        "SELECT status, started_at FROM pipeline_state WHERE video_id=? AND phase=?",
        (video_id, phase),
    ).fetchone()

    started = existing["started_at"] if existing else None

    if status == "running":
        started = now
        conn.execute(
            """UPDATE pipeline_state
               SET status='running', started_at=?, error=NULL, finished_at=NULL
               WHERE video_id=? AND phase=?""",
            (started, video_id, phase),
        )
    elif status in ("done", "failed", "skipped"):
        finished = now
        conn.execute(
            """UPDATE pipeline_state
               SET status=?, finished_at=?, error=?,
                   started_at=COALESCE(started_at, ?)
               WHERE video_id=? AND phase=?""",
            (status, finished, error, started or now, video_id, phase),
        )
    else:
        conn.execute(
            "UPDATE pipeline_state SET status=?, error=? WHERE video_id=? AND phase=?",
            (status, error, video_id, phase),
        )
    conn.commit()


def get_status(conn, video_id=None):
    """Return pipeline status as a list of dicts. If video_id, filter to one."""
    if video_id:
        rows = conn.execute(
            """SELECT ps.video_id, ps.phase, ps.status, ps.error, ps.started_at, ps.finished_at,
                      v.title, v.url
               FROM pipeline_state ps
               LEFT JOIN videos v ON v.video_id = ps.video_id
               WHERE ps.video_id = ?
               ORDER BY CASE ps.phase
                   WHEN 'fetch' THEN 1
                   WHEN 'structure' THEN 2
                   WHEN 'store' THEN 3
                   WHEN 'analyze' THEN 4
               END""",
            (video_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT ps.video_id, ps.phase, ps.status, ps.error,
                      MAX(ps.started_at) OVER (PARTITION BY ps.video_id) as last_active,
                      v.title, v.url
               FROM pipeline_state ps
               LEFT JOIN videos v ON v.video_id = ps.video_id
               ORDER BY last_active DESC NULLS LAST, ps.video_id, ps.phase""",
        ).fetchall()

    return [dict(r) for r in rows]


def format_status(rows, detail=False):
    """Pretty-print status rows."""
    if not rows:
        return "No videos in pipeline. Use 'parker add <url>' to add one."

    # Group by video
    by_video = {}
    for r in rows:
        vid = r["video_id"]
        if vid not in by_video:
            by_video[vid] = {"title": r.get("title") or "?", "url": r.get("url") or "", "phases": {}}
        by_video[vid]["phases"][r["phase"]] = r

    status_icons = {
        "pending": "⏳",
        "running": "🔄",
        "done": "✅",
        "failed": "❌",
        "skipped": "⏭️",
    }

    lines = []
    for vid, info in by_video.items():
        title = (info["title"] or "?")[:60]
        phase_icons = " ".join(
            status_icons.get(info["phases"].get(p, {}).get("status", "pending"), "?")
            for p in PHASES
        )
        lines.append(f"  {phase_icons}  {vid}  {title}")

        if detail:
            for p in PHASES:
                ph = info["phases"].get(p, {})
                icon = status_icons.get(ph.get("status", "pending"), "?")
                err = f" — {ph['error']}" if ph.get("error") else ""
                started = ph.get("started_at", "")[:19] if ph.get("started_at") else ""
                lines.append(f"    {icon} {p:12s} {ph.get('status', '?'):8s} {started}{err}")

    return "\n".join(lines)


def reset_phase(conn, video_id, phase=None):
    """Reset a phase (or all phases if none specified) to pending."""
    if phase:
        conn.execute(
            "UPDATE pipeline_state SET status='pending', error=NULL, started_at=NULL, finished_at=NULL WHERE video_id=? AND phase=?",
            (video_id, phase),
        )
    else:
        conn.execute(
            "UPDATE pipeline_state SET status='pending', error=NULL, started_at=NULL, finished_at=NULL WHERE video_id=?",
            (video_id,),
        )
    conn.commit()


def needs_phase(conn, video_id, phase):
    """Check if a phase needs to be run. Returns (needs_run, error_or_None)."""
    row = conn.execute(
        "SELECT status, error FROM pipeline_state WHERE video_id=? AND phase=?",
        (video_id, phase),
    ).fetchone()
    if not row:
        return True, None
    if row["status"] == "done":
        return False, None
    if row["status"] == "failed":
        return True, row["error"]
    return True, None
