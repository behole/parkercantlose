---
phase: 02-transcript-review-interface
plan: 01
subsystem: web
tags: [fastapi, uvicorn, jinja2, htmx, pico-css, sqlite]

# Dependency graph
requires:
  - phase: 01-ingestion-transcription-pipeline
    provides: "Data models (Debate, Utterance), database layer, CLI framework"
provides:
  - "ReviewStatus enum with unreviewed/in_progress/approved values"
  - "Debate.review_status and Utterance edit-tracking fields"
  - "FastAPI app factory with Jinja2 templates and static file serving"
  - "Base HTML template with Pico CSS and HTMX"
  - "CLI serve command launching uvicorn"
  - "Database migration script for existing data"
affects: [02-02, 02-03, 03-nlp-analysis, 04-public-dashboard]

# Tech tracking
tech-stack:
  added: [fastapi, uvicorn, jinja2, python-multipart, pico-css, htmx]
  patterns: [app-factory, template-inheritance, cli-serve-command]

key-files:
  created:
    - src/parker/web/__init__.py
    - src/parker/web/routes.py
    - src/parker/web/templates/base.html
    - src/parker/web/templates/video_list.html
    - src/parker/web/templates/review.html
    - src/parker/web/templates/partials/segment.html
    - src/parker/web/templates/partials/status_badge.html
    - src/parker/web/static/style.css
    - src/parker/web/static/review.js
    - scripts/migrate_review_fields.py
  modified:
    - src/parker/models.py
    - src/parker/config.py
    - src/parker/cli.py
    - pyproject.toml

key-decisions:
  - "Used Pico CSS + HTMX via CDN for lightweight styling and interactivity"
  - "FastAPI app factory pattern with engine/templates stored in app.state"
  - "Migration script uses raw SQLite ALTER TABLE for safe column additions"

patterns-established:
  - "App factory: create_app() returns configured FastAPI instance"
  - "Template inheritance: base.html with content/scripts/title blocks"
  - "CLI integration: serve command with host/port options using uvicorn factory mode"

requirements-completed: [REVW-01, REVW-05]

# Metrics
duration: 5min
completed: 2026-04-12
---

# Phase 2 Plan 01: Web App Foundation Summary

**FastAPI web scaffold with ReviewStatus enum, Pico CSS + HTMX base template, and CLI serve command**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-12T18:11:59Z
- **Completed:** 2026-04-12T18:17:00Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- Added ReviewStatus enum and review/edit-tracking fields to Debate and Utterance models
- Created FastAPI app factory with routes, Jinja2 templates, and static file serving
- Built base HTML template with Pico CSS and HTMX CDN integration
- Added `parker serve` CLI command launching uvicorn with hot reload
- Created SQLite migration script for existing databases

## Task Commits

Each task was committed atomically:

1. **Task 1: Update data models and add dependencies** - `e07ba71` (feat)
2. **Task 2: Create FastAPI web scaffold, base template, and CLI serve command** - `9b7e7ac` (feat)

## Files Created/Modified
- `src/parker/models.py` - Added ReviewStatus enum, review_status on Debate, edit-tracking fields on Utterance
- `src/parker/config.py` - Added web_host and web_port settings
- `pyproject.toml` - Added fastapi, uvicorn, jinja2, python-multipart dependencies
- `scripts/migrate_review_fields.py` - SQLite migration for existing databases
- `src/parker/web/__init__.py` - FastAPI app factory with static files and templates
- `src/parker/web/routes.py` - Route stubs for /, /videos, /videos/{id}/review
- `src/parker/web/templates/base.html` - Base layout with Pico CSS and HTMX
- `src/parker/web/templates/video_list.html` - Placeholder video list page
- `src/parker/web/templates/review.html` - Placeholder review page
- `src/parker/web/templates/partials/segment.html` - Segment partial placeholder
- `src/parker/web/templates/partials/status_badge.html` - Status badge partial placeholder
- `src/parker/web/static/style.css` - Base custom styles
- `src/parker/web/static/review.js` - Review JS placeholder
- `src/parker/cli.py` - Added serve command and main() entry point

## Decisions Made
- Used Pico CSS + HTMX via CDN for lightweight styling and interactivity (no build step needed)
- FastAPI app factory pattern with engine/templates stored in app.state for clean dependency injection
- Migration script uses raw SQLite ALTER TABLE for safe idempotent column additions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- whisperx dependency prevents `pip install -e .` on Python 3.14 (pre-existing issue, not caused by this plan). Worked around by installing new deps directly and using the project .venv with Python 3.11.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Web server foundation ready for Plan 02 (transcript review page with YouTube sync)
- Web server foundation ready for Plan 03 (video list and status management)
- All template stubs and partial placeholders in place for subsequent plans

---
## Self-Check: PASSED

All 14 files verified present. Both task commits (e07ba71, 9b7e7ac) verified in git log.

---
*Phase: 02-transcript-review-interface*
*Completed: 2026-04-12*
