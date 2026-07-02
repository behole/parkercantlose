---
phase: 02-transcript-review-interface
plan: 02
subsystem: ui
tags: [fastapi, htmx, jinja2, youtube-iframe-api, pico-css, transcript-review]

# Dependency graph
requires:
  - phase: 02-01
    provides: "FastAPI scaffold, ReviewStatus enum, base template with Pico CSS + HTMX, SQLModel models"
provides:
  - "Review page with YouTube embed and bidirectional transcript sync"
  - "HTMX PUT endpoint for speaker toggle (parker/caller)"
  - "HTMX PATCH endpoint for inline text editing"
  - "CRUD functions for utterance queries, speaker toggle, text update"
  - "Auto-transition of debate review_status from UNREVIEWED to IN_PROGRESS on first edit"
affects: [02-03, 03-nlp-analysis]

# Tech tracking
tech-stack:
  added: [youtube-iframe-api]
  patterns: [htmx-partial-swap, bidirectional-video-sync, inline-editing, original-preservation]

key-files:
  created: []
  modified:
    - src/parker/crud.py
    - src/parker/web/routes.py
    - src/parker/web/templates/review.html
    - src/parker/web/templates/partials/segment.html
    - src/parker/web/static/style.css
    - src/parker/web/static/review.js

key-decisions:
  - "Speaker toggle preserves original_speaker on first edit for audit trail"
  - "Text edit preserves original_text on first edit for diff visibility"
  - "Auto-transition review status from UNREVIEWED to IN_PROGRESS on any edit"
  - "250ms polling interval for YouTube sync (balance between responsiveness and performance)"

patterns-established:
  - "HTMX partial swap: PUT/PATCH returns segment partial with outerHTML swap"
  - "Original preservation: first edit saves original value, subsequent edits only update current"
  - "Route helper functions _get_engine/_get_templates for DRY request.app.state access"

requirements-completed: [REVW-01, REVW-02, REVW-03, REVW-04]

# Metrics
duration: 3min
completed: 2026-04-12
---

# Phase 2 Plan 02: Review Page & Transcript Sync Summary

**Review page with YouTube embed, bidirectional transcript sync, HTMX speaker toggle, and inline text editing with edit tracking**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-12T18:19:07Z
- **Completed:** 2026-04-12T18:22:08Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- CRUD layer with speaker toggle, text update, and auto review status transition
- Review page with YouTube IFrame API embed and 250ms bidirectional transcript sync
- HTMX-powered inline speaker toggle (PUT) and text editing (PATCH) with partial swaps
- Visual indicators: blue/red speaker badges, amber border for edited segments, pencil icon

## Task Commits

Each task was committed atomically:

1. **Task 1: Add review CRUD operations and wire review page route with data** - `23a8d21` (feat)
2. **Task 2: Build review page template, segment partial, styles, and YouTube sync JS** - `6a7205c` (feat)

## Files Created/Modified
- `src/parker/crud.py` - Added utterance CRUD: get_utterances_for_debate, toggle_utterance_speaker, update_utterance_text, _auto_transition_review_status
- `src/parker/web/routes.py` - Full review page route with data loading, HTMX PUT/PATCH endpoints for speaker toggle and text edit
- `src/parker/web/templates/review.html` - Review page with YouTube embed, transcript panel, auto-scroll toggle, edit count
- `src/parker/web/templates/partials/segment.html` - Segment partial with timestamp, speaker badge, inline text edit form, edit indicator
- `src/parker/web/static/style.css` - Complete styling: review layout grid, speaker badges, segment states, edit form, responsive
- `src/parker/web/static/review.js` - YouTube IFrame API integration, bidirectional sync, seekTo, startEdit/cancelEdit, Escape handler

## Decisions Made
- Speaker toggle preserves original_speaker on first edit for audit trail
- Text edit preserves original_text on first edit for diff visibility
- Auto-transition review status from UNREVIEWED to IN_PROGRESS on any edit
- 250ms polling interval for YouTube sync (balance between responsiveness and performance)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Review page fully functional, ready for Plan 03 (approval workflow, video list enhancements)
- All HTMX endpoints tested and returning correct partials
- YouTube sync ready for end-to-end testing with real debate data

---
*Phase: 02-transcript-review-interface*
*Completed: 2026-04-12*
