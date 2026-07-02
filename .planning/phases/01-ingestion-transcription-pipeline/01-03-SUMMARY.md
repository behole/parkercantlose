---
phase: 01-ingestion-transcription-pipeline
plan: 03
subsystem: audio-download
tags: [yt-dlp, ffmpeg, youtube, audio, wav, download]

# Dependency graph
requires:
  - phase: 01-ingestion-transcription-pipeline
    provides: project scaffolding (plan 01), database models (plan 02)
provides:
  - download_audio() function wrapping yt-dlp for 16kHz mono WAV conversion
  - DownloadResult pydantic model with YouTube metadata
  - extract_youtube_id() supporting multiple URL formats
  - Typed exception hierarchy (DownloadError, VideoUnavailableError, RateLimitError, InvalidURLError)
affects: [01-ingestion-transcription-pipeline]

# Tech tracking
tech-stack:
  added: [yt-dlp, ffmpeg]
  patterns: [pydantic BaseModel for structured results, typed exception hierarchy, skip-by-default integration tests]

key-files:
  created: [src/parker/download.py, tests/test_download.py, tests/test_download_integration.py]
  modified: []

key-decisions:
  - "Used pydantic BaseModel for DownloadResult instead of dataclass for consistency with existing models"
  - "Removed FFmpegSubtitlesConvertor postprocessor from plan - not needed for audio-only download"
  - "Integration test skipped by default via RUN_INTEGRATION_TESTS env var"

patterns-established:
  - "Typed exception hierarchy: base DownloadError with youtube_id attribute, specialized subclasses"
  - "Integration tests gated by environment variable for CI-safe defaults"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-04-09
---

# Phase 1 Plan 3: Audio Download Module Summary

**yt-dlp wrapper with 16kHz mono WAV conversion, typed exceptions, and YouTube URL parsing**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-09T23:14:18Z
- **Completed:** 2026-04-09T23:16:19Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- download_audio() function wrapping yt-dlp with automatic 16kHz mono WAV conversion via ffmpeg
- Typed exception hierarchy for error handling (rate limiting, unavailable videos, invalid URLs)
- YouTube ID extraction supporting standard, short, embed, and bare ID formats
- Integration test for real downloads, safely skipped by default

## Task Commits

Each task was committed atomically:

1. **Task 1: Define Download Exceptions and Metadata Model** - `fa785d4` (feat)
2. **Task 2: YouTube ID Extraction Tests** - `1ef1b1f` (test)
3. **Task 3: Integration Test for Audio Download** - `a076b55` (test)

## Files Created/Modified
- `src/parker/download.py` - yt-dlp wrapper with download_audio(), extract_youtube_id(), exception classes, DownloadResult model
- `tests/test_download.py` - 10 unit tests for result model, exceptions, and URL extraction
- `tests/test_download_integration.py` - Integration test for real YouTube download (skipped by default)

## Decisions Made
- Used pydantic BaseModel for DownloadResult for consistency with existing SQLModel/pydantic patterns
- Removed FFmpegSubtitlesConvertor from postprocessors list (plan included it but it is not needed for audio-only)
- YouTube IDs are validated as exactly 11 characters per YouTube's actual format

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unnecessary FFmpegSubtitlesConvertor postprocessor**
- **Found during:** Task 1 (implementation)
- **Issue:** Plan included FFmpegSubtitlesConvertor in postprocessors list, which is not relevant for audio extraction and could cause errors
- **Fix:** Removed it from the postprocessors list, keeping only FFmpegExtractAudio
- **Files modified:** src/parker/download.py
- **Verification:** All tests pass
- **Committed in:** fa785d4 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor cleanup, no scope change.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. ffmpeg and yt-dlp are assumed available in the environment.

## Next Phase Readiness
- Audio download module ready for use by transcription pipeline (plan 04+)
- download_audio() returns DownloadResult with audio_path for WhisperX input
- Error handling covers rate limiting and unavailable videos for robust batch processing

---
*Phase: 01-ingestion-transcription-pipeline*
*Completed: 2026-04-09*
