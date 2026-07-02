---
phase: 01-ingestion-transcription-pipeline
plan: 07
subsystem: testing
tags: [validation, e2e, diarization, quality-report]

# Dependency graph
requires:
  - phase: 01-ingestion-transcription-pipeline (plan 06)
    provides: Full pipeline orchestrator and CLI
provides:
  - Validation script for end-to-end pipeline testing
  - Quality report generation with turn boundary extraction
affects: [phase-2-transcript-review]

# Tech tracking
tech-stack:
  added: []
  patterns: [validation-script, quality-metrics-reporting]

key-files:
  created: [scripts/validate.py]
  modified: []

key-decisions:
  - "Validation script uses sys.path insertion to import from src/parker without package install"
  - "Turn boundaries extracted from first 30 utterances for manual spot-checking"

patterns-established:
  - "scripts/ directory for operational tooling outside the core package"

requirements-completed: []

# Metrics
duration: 1min
completed: 2026-04-09
---

# Phase 1 Plan 7: Validation & End-to-End Testing Summary

**Validation script for pipeline quality reporting with turn boundary extraction for manual diarization verification**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-09T23:32:08Z
- **Completed:** 2026-04-09T23:33:29Z
- **Tasks:** 1 of 2 (Task 2 requires manual verification -- checkpoint returned)
- **Files modified:** 1

## Accomplishments
- Created validation script that processes test videos through the full pipeline
- Script generates quality report with per-video metrics (utterance counts, speaker breakdown, confidence scores)
- Turn boundary extraction enables manual verification of diarization accuracy
- All 48 existing tests continue to pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Validation Script** - `5bbe714` (feat)
2. **Task 2: Manual Validation Procedure** - CHECKPOINT (requires human action: .env setup, real video URLs, manual turn boundary verification)

## Files Created/Modified
- `scripts/validate.py` - End-to-end validation script with quality reporting and turn boundary extraction

## Decisions Made
- Followed plan as specified for Task 1
- Task 2 deferred to human checkpoint as designed (requires HF_TOKEN, real YouTube URLs, manual audio verification)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

Task 2 requires manual steps:
1. Set `HF_TOKEN` in `.env` file
2. Identify 3 Parker debate YouTube video URLs
3. Run `source .venv/bin/activate && python scripts/validate.py --urls URL1 URL2 URL3`
4. Manually verify 30 turn boundaries against video audio
5. Target: >25/30 correct boundaries to validate Phase 1 diarization quality

## Next Phase Readiness
- Validation script ready for manual execution
- Once manual verification passes (>25/30 turn boundaries correct), Phase 1 is complete
- Phase 2 (Transcript Review) can begin after validation passes

## Self-Check: PASSED

- [x] `scripts/validate.py` exists
- [x] Commit `5bbe714` found in git log
- [x] 48 tests passing, 1 skipped (no regressions)

---
*Phase: 01-ingestion-transcription-pipeline*
*Completed: 2026-04-09 (Task 1 only; Task 2 awaiting manual verification)*
