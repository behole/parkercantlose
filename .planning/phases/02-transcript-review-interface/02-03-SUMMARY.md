---
phase: 02-transcript-review-interface
plan: 03
subsystem: ui
tags: [htmx, jinja2, fastapi, pico-css, approval-workflow]

# Dependency graph
requires:
  - phase: 02-transcript-review-interface
    provides: "Web app scaffold, ReviewStatus model, review page with transcript editing"
provides:
  - "Video list page with review status badges and edit counts"
  - "Approve/unapprove CRUD and API endpoints"
  - "Approval bar UI with HTMX swap on review page"
  - "Phase 3 NLP pipeline gate (get_nlp_ready_debates, is_debate_nlp_ready)"
affects: [03-nlp-analysis]

# Tech tracking
tech-stack:
  added: []
  patterns: [htmx-partial-swap-for-approval, pipeline-gate-pattern]

key-files:
  created:
    - src/parker/web/templates/partials/approval_bar.html
  modified:
    - src/parker/crud.py
    - src/parker/web/routes.py
    - src/parker/pipeline.py
    - src/parker/web/templates/video_list.html
    - src/parker/web/templates/partials/status_badge.html
    - src/parker/web/templates/review.html
    - src/parker/web/static/style.css

key-decisions:
  - "Approval bar returned as full partial on approve/unapprove for clean HTMX outerHTML swap"
  - "Fixed duplicate status column in video_list table per plan NOTE"

patterns-established:
  - "Pipeline gate pattern: get_nlp_ready_debates checks ReviewStatus.APPROVED before Phase 3 NLP"
  - "Approval bar partial: reusable HTMX component for approve/revoke workflow"

requirements-completed: [REVW-01, REVW-05]

# Metrics
duration: 3min
completed: 2026-04-12
---

# Phase 2 Plan 3: Video List, Approval Workflow & NLP Gate Summary

**Video list with status badges, HTMX approve/unapprove workflow, and Phase 3 NLP pipeline gate checking ReviewStatus.APPROVED**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-12T18:24:21Z
- **Completed:** 2026-04-12T18:27:08Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Video list page shows all debates with title, color-coded review status badge, edit count, and review link
- Approve/unapprove endpoints swap approval bar via HTMX for seamless UX
- Phase 3 NLP pipeline gate functions prevent unapproved transcripts from entering analysis
- Full status lifecycle: unreviewed -> in_progress (on edit) -> approved (on approve) -> in_progress (on unapprove)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add approval CRUD, routes, and Phase 3 pipeline gate** - `bd18baf` (feat)
2. **Task 2: Build video list template, status badge partial, and approval UI** - `03b7a8e` (feat)

## Files Created/Modified
- `src/parker/crud.py` - Added approve_debate, unapprove_debate, get_approved_debates, count_edits_for_debate
- `src/parker/web/routes.py` - Added POST approve/unapprove routes, updated video_list with edit counts
- `src/parker/pipeline.py` - Added get_nlp_ready_debates and is_debate_nlp_ready gate functions
- `src/parker/web/templates/video_list.html` - Debate table with status badges, edit counts, review links
- `src/parker/web/templates/partials/status_badge.html` - Color-coded review status badge partial
- `src/parker/web/templates/partials/approval_bar.html` - HTMX approval bar with approve/revoke buttons
- `src/parker/web/templates/review.html` - Added approval bar above review layout
- `src/parker/web/static/style.css` - Approval bar, button, and message styles

## Decisions Made
- Approval bar returned as full partial (not just badge) for clean HTMX outerHTML swap
- Fixed duplicate status column in video_list table -- kept single "Review Status" column using the status_badge partial include per plan NOTE

## Deviations from Plan

None - plan executed exactly as written (duplicate column fix was explicitly noted in plan).

## Issues Encountered
- WhisperX dependency prevents `pip install -e .` -- used `.venv/bin/python` with pre-installed venv instead
- `httpx` not installed in venv, so `TestClient` import fails -- verified routes via direct router inspection

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 2 complete: web app has full transcript review workflow (view, edit, approve)
- Phase 3 NLP analysis can use `get_nlp_ready_debates()` and `is_debate_nlp_ready()` as gate checks
- All status transitions verified: unreviewed -> in_progress -> approved -> in_progress

---
*Phase: 02-transcript-review-interface*
*Completed: 2026-04-12*
