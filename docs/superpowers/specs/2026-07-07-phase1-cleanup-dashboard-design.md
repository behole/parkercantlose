# Phase 1: Data Cleanup & Dashboard Overhaul

**Date:** 2026-07-07
**Status:** design-approved
**Codebase:** parker-debate-pipeline

## Overview

Phase 1 delivers the foundation for all future analysis work: a cleaned-up dataset, an automated cleanup pipeline, and a rich sidebar-based dashboard with interactive charts. Everything subsequent (search enhancements, debate comparison, topic/stance analytics) depends on clean data and a navigable frontend.

## Architecture

```
src/parker/
  analytics.py          NEW — stats aggregation, cleanup detection, auto-dedup
  cli.py                ADD  — `parker cleanup` command
  crud.py               ADD  — merge_topic_match, reject_topic_match, get_cleanup_inbox helpers
  pipeline.py           MOD  — post-analysis hook calls auto_merge_topics() + auto_link_guests()
  web/
    __init__.py          MOD  — shared sidebar context injection
    routes.py            ADD  — `/admin/cleanup` route + cleanup API endpoints
    public_routes.py     MOD  — rewritten `/` dashboard route
    templates/
      dashboard.html     REWRITE — sidebar layout, KPI cards, charts, activity feed
      _sidebar.html      NEW — persistent nav partial with cleanup badge
      cleanup.html       NEW — admin cleanup inbox
      video_list.html     MOD  — include sidebar
      debate_list.html    MOD  — include sidebar
      debate_detail.html  MOD  — include sidebar
      patterns.html       MOD  — include sidebar
      search_results.html MOD  — include sidebar
      review.html         MOD  — include sidebar (admin)
    static/
      (no new files)      Chart.js loaded from CDN
```

## Component Details

### 1. analytics.py (new module)

Stateless aggregation + cleanup. No new database tables — reuses `TopicMatch` (already exists).

```
get_dashboard_stats(session) → Dict
  Returns: {total_debates, approved_count, total_hours, unique_guests,
            completion_pct, pipeline_status_counts}

get_topic_frequency(session, limit=10) → List[Tuple[str, int]]
  Top N topics across all debates.

get_debate_timeline(session) → List[Tuple[str, int]]
  Debates grouped by upload month (YYYY-MM), sorted chronologically.

detect_duplicate_topics(session, threshold=0.85) → List[TopicMatch]
  Topics with similarity >= threshold. Already partially implemented via TopicMatch table.

detect_unlinked_guests(session) → List[Debate]
  Approved debates where speaker "caller" appears but no guest_id linked.

detect_anomalies(session) → Dict
  Returns: {failed_pipelines, empty_transcripts, unreviewed_count, auto_generated_count}

auto_merge_topics(session, threshold=0.95) → int
  For TopicMatch rows with similarity >= 0.95 and status="suggested": merge the topics,
  re-point stances/utterances, update status to "confirmed". Returns count merged.

auto_link_guests(session) → int
  For debates with caller speaker + no guest_id: look for exact guest name match,
  link if found. Returns count linked.

get_cleanup_inbox(session) → Dict
  Returns: {ambiguous_topics, unlinked, anomalies}
  Ambiguous = 0.85 <= similarity < 0.95.
```

### 2. Dashboard v2 (rewrite of `/` route)

**Layout:** Sidebar (Option B from mockup)

**Sidebar contents:**
- Navigation links: Dashboard, Debates, Patterns, Guests, Search
- Active-state highlighting based on `request.url.path`
- Cleanup badge: "3 items" count when `get_cleanup_inbox()` returns items, hidden when zero
- Is a Jinja2 partial (`_sidebar.html`) included on every page via `{% include "_sidebar.html" %}`

**Top KPI cards (4 across):**
- Total debates / approved count
- Total content hours / average per debate
- Completion rate % (debates with status COMPLETED or approved)
- Unique guests tracked

**Charts (Chart.js from CDN):**
- Horizontal bar chart: top 10 topic frequencies
- Line chart: debates uploaded per month (timeline)

**Data flow:** All chart data embedded in template as JSON, not fetched via separate API calls.

**Activity feed:** Last 5 pipeline events (processed, transcribed, approved, NLP complete), ordered by `created_at`/`updated_at`.

**Cleanup alerts card:** Summary of auto-resolved actions + "N items need review" link to `/admin/cleanup`.

### 3. Cleanup Page (`/admin/cleanup`)

**Auto-resolved summary banner:**
- "Last auto-cleanup merged 4 topics and linked 2 guests"
- "Run cleanup now" button triggers auto-merge + auto-link and refreshes

**Inbox sections:**

*Duplicate topics inbox:*
- Table: topic_a, topic_b, similarity score, debate titles, actions
- Actions: Accept (merge), Reject (mark status=rejected), Edit (rename one topic)
- Accept triggers merge: all stances under topic_b re-point to topic_a, topic_b marked merged_into_id

*Unlinked guests inbox:*
- Table: debate title, detected caller name, date, actions
- Actions: Link to existing guest (dropdown), Create new guest + link, Skip

*Pipeline anomalies:*
- List: failed runs with error messages, debates with 0 utterances, auto-generated transcript flags
- Actions: Retry, Dismiss, Inspect

**Cleanup API endpoints:**
- `POST /admin/api/cleanup/merge-topics` — merge two topics
- `POST /admin/api/cleanup/reject-match` — reject a topic match
- `POST /admin/api/cleanup/link-guest` — link debate to guest
- `POST /admin/api/cleanup/run-auto` — run auto_merge_topics + auto_link_guests

### 4. Shared Sidebar

`_sidebar.html` — Jinja2 partial included via `{% include "_sidebar.html" %}` at the top of every page template. Reads `request.url.path` for active link highlighting. Reads `cleanup_count` from template context (defaults to 0). All existing pages (debate list, patterns, search, debate detail, review, video list) get the sidebar added with no other changes to their content.

### 5. CLI

New `parker cleanup` command that runs `auto_merge_topics()` + `auto_link_guests()` from the terminal and prints a summary.

## Data Cleanup Heuristics

| Action | Condition | Automation |
|--------|-----------|------------|
| Merge topics | similarity >= 0.95, status=suggested | Auto (post-analysis hook) |
| Link guest to profile | exact name match, no existing link | Auto (post-analysis hook) |
| Flag for review | 0.85 <= similarity < 0.95 | Manual inbox |
| Flag unlinked | caller detected, no guest_id, no name match | Manual inbox |
| Flag anomaly | status=failed, utterance_count=0, auto-generated | Manual inbox |

## Dependencies

- **Chart.js** — loaded from CDN (`cdn.jsdelivr.net`), no npm/build step. ~60KB gzipped.
- No new Python dependencies.

## Out of Scope (Future Phases)

- Semantic search and search enhancements
- Debate comparison (side-by-side diff)
- Topic/stance evolution tracking and contradiction detection
- Time-series trend analysis beyond simple timeline
- Guest profile dashboards

## Testing

- `tests/test_analytics.py` — unit tests for all analytics functions
- `tests/test_cleanup.py` — unit tests for auto-merge/auto-link logic
- Existing test suite must remain green
