---
phase: 03-nlp-analysis-pipeline
plan: 04
subsystem: ui
tags: [fastapi, htmx, jinja2, pico-css, topic-refinement, cross-debate-matching]

# Dependency graph
requires:
  - phase: 03-nlp-analysis-pipeline (03-02)
    provides: "NLP extraction pipeline and CRUD functions for topics, stances, keywords"
  - phase: 03-nlp-analysis-pipeline (03-03)
    provides: "NLP CRUD operations, topic embeddings, cross-debate similarity matching"
provides:
  - "Topic refinement UI with accept/reject/rename per topic"
  - "Stance classification display per speaker per topic"
  - "Keyword frequency table per debate"
  - "Cross-debate topic matching UI with confirm/reject"
  - "Navigation links connecting video list to topic refinement pages"
affects: [04-public-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [htmx-partial-swap-for-topic-actions, stances-grouped-by-topic-id, match-resolution-with-topic-and-debate-objects]

key-files:
  created:
    - src/parker/web/templates/topics.html
    - src/parker/web/templates/topic_matches.html
    - src/parker/web/templates/partials/topic_card.html
    - src/parker/web/templates/partials/stance_row.html
    - src/parker/web/templates/partials/match_card.html
  modified:
    - src/parker/web/routes.py
    - src/parker/web/templates/base.html

key-decisions:
  - "Reject topic returns empty HTML to remove card from DOM via HTMX outerHTML swap"
  - "Stances grouped by topic_id in route for efficient template rendering"
  - "Topic matches resolve full topic and debate objects in route for display context"

patterns-established:
  - "HTMX outerHTML swap pattern: action buttons target parent card ID, server returns updated card or empty string for removal"
  - "Route-level data resolution: complex joins done in route handler, templates receive flat data"

requirements-completed: [NLPP-02, NLPP-03, NLPP-05]

# Metrics
duration: 3min
completed: 2026-04-12
---

# Phase 3 Plan 4: Topic Refinement & Cross-Debate Matching UI Summary

**Topic refinement page with accept/reject/rename HTMX actions, stance tables, keyword display, and cross-debate topic matching page with confirm/reject workflow**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-12T19:23:50Z
- **Completed:** 2026-04-12T19:26:58Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- 8 new web routes for topic refinement and cross-debate matching with HTMX partial responses
- 5 new templates: topic refinement page, topic card, stance row, match card, topic matches page
- Navigation updated with Topic Matches link in base template
- Human-in-the-loop workflow: AI suggests topics, user accepts/rejects/renames via real-time HTMX actions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add topic refinement and matching web routes** - `c2d3d52` (feat)
2. **Task 2: Create topic refinement and matching templates** - `7cd8513` (feat)
3. **Task 3: Verify topic refinement and matching UI** - Auto-approved checkpoint

**Plan metadata:** (pending docs commit)

## Files Created/Modified
- `src/parker/web/routes.py` - 8 new routes: topic refinement page, accept/reject/rename topic, topic matches page, confirm/reject match
- `src/parker/web/templates/topics.html` - Topic refinement page with breadcrumb, NLP status check, topic cards, keyword table
- `src/parker/web/templates/topic_matches.html` - Cross-debate matching page with suggested and confirmed sections
- `src/parker/web/templates/partials/topic_card.html` - Topic card with status badge, stance table, HTMX action buttons
- `src/parker/web/templates/partials/stance_row.html` - Stance display with speaker label, confidence meter, evidence
- `src/parker/web/templates/partials/match_card.html` - Match card with similarity score, topic/debate context, confirm/reject buttons
- `src/parker/web/templates/base.html` - Added Topic Matches nav link

## Decisions Made
- Reject actions return empty HTML string for HTMX outerHTML swap to remove elements from DOM
- Stances grouped by topic_id in route handler rather than template for cleaner Jinja2 logic
- Topic matches page resolves full topic and debate objects in route for display context

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 NLP Analysis Pipeline complete with all 4 plans executed
- Topic refinement and matching UI provides human-in-the-loop quality control
- Ready for Phase 4: Public Dashboard development

## Self-Check: PASSED

All 7 files verified present. Both task commits (c2d3d52, 7cd8513) verified in git log.

---
*Phase: 03-nlp-analysis-pipeline*
*Completed: 2026-04-12*
