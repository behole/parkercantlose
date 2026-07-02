---
phase: 01-ingestion-transcription-pipeline
plan: 05
subsystem: api
tags: [pydantic, sqlmodel, speaker-diarization, heuristics]

# Dependency graph
requires:
  - phase: 01-ingestion-transcription-pipeline
    provides: Utterance and Debate SQLModel schemas (plan 02)
provides:
  - identify_parker() speaker identification heuristic with confidence scoring
  - extract_utterances() diarized segment to Utterance record conversion
  - SpeakerAssignment pydantic model for speaker label mapping
affects: [01-ingestion-transcription-pipeline, 02-transcript-review]

# Tech tracking
tech-stack:
  added: []
  patterns: [speaking-time-plus-first-speaker heuristic, consecutive segment merging]

key-files:
  created: [src/parker/speakers.py, tests/test_speakers.py]
  modified: []

key-decisions:
  - "Fixed plan test data for low-confidence case where heuristics were actually agreeing"

patterns-established:
  - "Speaker identification: dual heuristic (speaking time + first speaker) with confidence flag"
  - "Utterance extraction: merge consecutive same-speaker segments before creating records"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-04-09
---

# Phase 1 Plan 05: Speaker Identification & Utterance Extraction Summary

**Parker speaker identification via speaking-time + first-speaker heuristic with confidence scoring, and utterance extraction with consecutive speaker-turn merging**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-09T23:18:27Z
- **Completed:** 2026-04-09T23:20:49Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- SpeakerAssignment pydantic model with parker/caller labels, confidence, and speaking time metrics
- identify_parker() heuristic that combines speaking time dominance with first-speaker detection
- extract_utterances() that merges consecutive same-speaker segments into Utterance records with word-level confidence
- 8 passing tests covering identification edge cases (empty, single speaker, disagreement) and extraction (basic, merging, empty text)

## Task Commits

Each task was committed atomically:

1. **Task 1: Parker Identification Heuristic** - `4077d5b` (feat)
2. **Task 2: Utterance Extraction from Diarized Segments** - `f107121` (feat)

## Files Created/Modified
- `src/parker/speakers.py` - Speaker identification heuristic and utterance extraction functions
- `tests/test_speakers.py` - 8 tests covering all speaker identification and extraction scenarios

## Decisions Made
- Fixed plan's test data for low-confidence test case: original data had both heuristics agreeing (SPEAKER_01 was both first speaker and highest time), adjusted so they disagree (SPEAKER_01 first but SPEAKER_00 has most time)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test data for low-confidence heuristic disagreement**
- **Found during:** Task 1 (Parker Identification Heuristic)
- **Issue:** Plan's test segments for `test_identify_parker_low_confidence` had SPEAKER_01 with 25s total and as first speaker -- both heuristics agreed, so confidence was "high" not "low" as expected
- **Fix:** Adjusted segment durations so SPEAKER_00 has more speaking time (25s) while SPEAKER_01 speaks first (10s), creating genuine heuristic disagreement
- **Files modified:** tests/test_speakers.py
- **Verification:** All 5 identification tests pass
- **Committed in:** 4077d5b (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in plan test data)
**Impact on plan:** Necessary correction for test correctness. No scope creep.

## Issues Encountered
- test_transcribe.py from parallel plan 01-04 has import errors (expected -- that plan is still executing). Excluded from test runs; not in scope.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Speaker identification and utterance extraction ready for integration with transcription pipeline (plan 01-04)
- extract_utterances() expects diarized segments with speaker/start/end/text/words fields

---
*Phase: 01-ingestion-transcription-pipeline*
*Completed: 2026-04-09*
