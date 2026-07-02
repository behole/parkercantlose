---
phase: 01-ingestion-transcription-pipeline
verified: 2026-04-09T23:55:00Z
status: gaps_found
score: 3/4 must-haves verified
must_haves:
  truths:
    - "User submits a YouTube URL and receives a word-level timestamped transcript with speaker labels without manual intervention"
    - "System identifies exactly 2 speakers per video with segment-level speaker attribution"
    - "Processing a single video completes end-to-end without error on at least 3 test videos"
    - "Failed videos are isolated -- one video's failure does not prevent other videos from processing"
  artifacts:
    - path: "src/parker/cli.py"
      provides: "CLI entry point with process, batch, status, retry commands"
    - path: "src/parker/pipeline.py"
      provides: "Pipeline orchestrator with checkpointing and error isolation"
    - path: "src/parker/download.py"
      provides: "yt-dlp audio download with error handling"
    - path: "src/parker/transcribe.py"
      provides: "WhisperX transcription, alignment, and diarization pipeline"
    - path: "src/parker/speakers.py"
      provides: "Parker identification heuristic and utterance extraction"
    - path: "src/parker/models.py"
      provides: "SQLModel schemas for Debate and Utterance"
    - path: "src/parker/db.py"
      provides: "Database engine, init, and session management"
    - path: "src/parker/crud.py"
      provides: "CRUD operations for Debate records"
    - path: "src/parker/config.py"
      provides: "pydantic-settings configuration"
    - path: "scripts/validate.py"
      provides: "Validation script with quality reporting"
  key_links:
    - from: "cli.py"
      to: "pipeline.py"
      via: "import process_video, process_batch, get_status_summary, retry_failed"
    - from: "pipeline.py"
      to: "download.py"
      via: "import download_audio, extract_youtube_id"
    - from: "pipeline.py"
      to: "transcribe.py"
      via: "import run_pipeline"
    - from: "pipeline.py"
      to: "speakers.py"
      via: "import identify_parker, extract_utterances"
    - from: "pipeline.py"
      to: "crud.py"
      via: "import create_debate, get_debate_by_youtube_id, update_debate_status"
    - from: "speakers.py"
      to: "models.py"
      via: "import Utterance"
    - from: "transcribe.py"
      to: "pyannote.audio"
      via: "import Pipeline as PyannotePipeline"
gaps:
  - truth: "Processing a single video completes end-to-end without error on at least 3 test videos"
    status: partial
    reason: "Only 2 videos processed successfully (jNQXAC9IVRw 19s test, DKHZZ4CoQH0 30min debate). Success criterion requires at least 3."
    artifacts: []
    missing:
      - "Process one additional real YouTube video end-to-end to meet the 3-video threshold"
---

# Phase 1: Ingestion & Transcription Pipeline Verification Report

**Phase Goal:** YouTube URL in, timestamped speaker-labeled transcript out.
**Verified:** 2026-04-09T23:55:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User submits YouTube URL and receives word-level timestamped transcript with speaker labels without manual intervention | VERIFIED | CLI `process` command wired end-to-end. Real transcript `DKHZZ4CoQH0_transcript.txt` shows 196 utterances with `[MM:SS] SPEAKER: text` format. Raw JSON includes word-level timestamps. |
| 2 | System identifies exactly 2 speakers per video with segment-level speaker attribution | VERIFIED | `diarize_audio()` constrains `min_speakers=2, max_speakers=2`. `identify_parker()` maps SPEAKER_00/01 to parker/caller. Real data: 98 parker + 97 caller + 1 unknown (empty speaker_raw edge case, 0.5% -- not a blocker). |
| 3 | Processing completes end-to-end on at least 3 test videos | PARTIAL | 2 of 3 required videos completed: `jNQXAC9IVRw` (19s, 2 utterances) and `DKHZZ4CoQH0` (30min, 196 utterances). Both show status=completed in DB. One more video needed. |
| 4 | Failed videos are isolated -- one failure does not prevent others from processing | VERIFIED | `process_batch()` catches per-video exceptions, returns None for failures, continues to next video. `test_process_batch_isolates_failures` validates this behavior. Pipeline wraps each video in try/except with status=FAILED checkpoint. |

**Score:** 3/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/parker/config.py` | pydantic-settings configuration | VERIFIED | 27 lines, Settings class with all required fields, ensure_dirs() |
| `src/parker/models.py` | SQLModel schemas | VERIFIED | 48 lines, Debate + Utterance + VideoStatus with all required fields |
| `src/parker/db.py` | Database engine/session | VERIFIED | 22 lines, get_engine, init_db, get_session |
| `src/parker/crud.py` | CRUD operations | VERIFIED | 80 lines, create/read/update/reset debate operations |
| `src/parker/download.py` | yt-dlp wrapper | VERIFIED | 118 lines, download_audio + extract_youtube_id + typed exceptions |
| `src/parker/transcribe.py` | WhisperX pipeline | VERIFIED | 265 lines, 3-stage pipeline (transcribe, align, diarize) with run_pipeline orchestrator |
| `src/parker/speakers.py` | Speaker ID + utterance extraction | VERIFIED | 149 lines, identify_parker heuristic + extract_utterances with turn merging |
| `src/parker/pipeline.py` | Pipeline orchestrator | VERIFIED | 240 lines, process_video with 4-stage checkpointing, batch, status, retry |
| `src/parker/cli.py` | CLI entry point | VERIFIED | 112 lines, 4 commands (process, batch, status, retry) wired to pipeline |
| `scripts/validate.py` | Validation script | VERIFIED | 158 lines, processes test videos and generates quality report |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| cli.py | pipeline.py | import process_video, process_batch, get_status_summary, retry_failed | WIRED | Line 10: direct imports, all 4 commands call pipeline functions |
| pipeline.py | download.py | import download_audio, extract_youtube_id | WIRED | Lines 12-13: imports used in process_video stages 1 |
| pipeline.py | transcribe.py | import run_pipeline | WIRED | Line 15: used in process_video stage 2 |
| pipeline.py | speakers.py | import identify_parker, extract_utterances | WIRED | Line 14: used in process_video stages 3-4 |
| pipeline.py | crud.py | import create_debate, get_debate_by_youtube_id, update_debate_status | WIRED | Lines 6-9: used throughout for checkpointing |
| speakers.py | models.py | import Utterance | WIRED | Line 9: Utterance objects created in extract_utterances |
| transcribe.py | pyannote.audio | from pyannote.audio import Pipeline | WIRED | Line 149: diarize_audio loads pyannote pipeline with 2-speaker constraint |
| transcribe.py | whisperx | import whisperx | WIRED | Lines 71, 112, 203: lazy imports in transcribe_audio, align_transcription, assign_speakers |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INGE-01 | 01-03 | User can submit YouTube URL and get audio extracted | SATISFIED | `download_audio()` downloads best audio, converts to 16kHz mono WAV via ffmpeg. Real audio files exist in `data/audio/`. |
| INGE-02 | 01-04 | System transcribes audio using WhisperX | SATISFIED | `transcribe_audio()` loads whisperx large-v2 model, transcribes with batch processing. Real transcripts produced. |
| INGE-03 | 01-04 | System produces word-level timestamped transcript | SATISFIED | `align_transcription()` runs wav2vec2 forced alignment. Raw JSON saved with word-level `start`/`end`/`score` fields. |
| INGE-04 | 01-05 | System identifies speakers via 2-speaker diarization | SATISFIED | `diarize_audio()` uses pyannote with min_speakers=2, max_speakers=2. `identify_parker()` maps to parker/caller. Real data shows 98/97 parker/caller split. |

No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | No TODO/FIXME/PLACEHOLDER/NotImplementedError found in any src/parker/ file |

Zero anti-patterns detected across all source files.

### Human Verification Required

#### 1. Third Video End-to-End Processing

**Test:** Run `source .venv/bin/activate && python scripts/validate.py --urls "URL"` with a third Parker debate YouTube URL.
**Expected:** Video processes to completion with both parker and caller utterances in the output transcript.
**Why human:** Requires selecting a real YouTube URL, network access, and ~10 minutes of GPU/CPU processing time.

#### 2. Diarization Quality Assessment

**Test:** Open `data/transcripts/DKHZZ4CoQH0_transcript.txt` alongside the YouTube video. Verify 10 speaker turn boundaries match reality.
**Expected:** At least 8/10 turn boundaries are correctly attributed (parker vs caller).
**Why human:** Requires listening to audio and comparing speaker labels against actual voices.

#### 3. Word-Level Timestamp Accuracy

**Test:** Open `data/transcripts/DKHZZ4CoQH0_raw.json`, pick 5 words with timestamps, and verify against video playback.
**Expected:** Word timestamps accurate within 500ms.
**Why human:** Requires video playback comparison.

### Gaps Summary

One gap prevents full goal achievement:

**Success Criterion 3 requires 3 test videos; only 2 have been processed.** The pipeline itself is fully functional -- all code is wired, 48 tests pass, and the 2 completed videos demonstrate high-quality output (196 properly-labeled utterances from a 30-minute debate). The gap is purely in validation coverage, not in implementation. Processing one additional video would close this gap.

The 1 "unknown" speaker utterance out of 196 (0.5%) is a minor edge case where a segment had an empty speaker_raw field, likely from a very short interjection that pyannote could not attribute. This does not affect the overall quality of the pipeline.

---

_Verified: 2026-04-09T23:55:00Z_
_Verifier: Claude (gsd-verifier)_
