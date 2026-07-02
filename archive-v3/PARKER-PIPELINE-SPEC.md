# Parker Pipeline — Functional Spec & Architecture

> Data aggregation + dashboard for Parker (YouTube creator).
> Current state: v3, Python/SQLite. Goal: redesign as a robust system.

---

## 1. What It Does

Ingest Parker's YouTube livestreams (Trump supporter debates), extract transcripts, identify who's speaking, store everything searchable, analyze keyword/topic patterns, and serve it via a Dashboard UI.

## 2. Current Architecture (v3)

```
streams.txt → [Fetch] → raw/       → [Structure] → structured/  → [Store] → SQLite DB
  (URLs)       fetch_transcript.py    structure_transcript.py      store.py   parker.db (+FTS5)
                                                                      ↓
                                                              [Analyze] [Search] [Export]
                                                              parker_   parker_   obsidian_
                                                              analytics search    export.py
```

### Phase 1 — Fetch
- **Script:** `fetch_transcript.py`
- **Input:** YouTube URL or video ID
- **Output:** `data/raw/{video_id}.json`
- **What it does:**
  - Extracts video ID from any YT URL format
  - Fetches transcript via `youtube-transcript-api`
  - Fetches video metadata (title, author) via oEmbed API
  - Saves raw transcript segments with timestamps
- **Dependency:** `youtube-transcript-api` (Python package)

### Phase 2 — Structure
- **Script:** `structure_transcript.py`
- **Input:** `data/raw/{video_id}.json`
- **Output:** `data/structured/{video_id}.structured.json`
- **What it does:**
  - Merges raw segments into logical utterances (splitting on `>>` markers YT uses for speaker changes)
  - Detects guest conversation chapters (gaps >60s or intro phrasing like "how old are you")
  - Labels speakers via a **hybrid heuristic** (v3):
    - Scores each utterance for Parker-ness (strong Parker phrases +3, moderate +1.5, questions +0.3)
    - If no strong signal, alternates by turn (Parker → guest_N → Parker → guest_N...)
    - Merges short chapters (<3min) into adjacent ones
- **Key design choice:** Speaker identification is regex-based, not ML-based. It infers Parker by verbal patterns and assumes alternation for guests. No actual speaker names, just `guest_1..N`.

### Phase 3 — Store
- **Script:** `store.py` / `scripts/store_db.py`
- **Input:** `structured/{video_id}.structured.json`
- **Output:** SQLite DB (`data/parker.db` + `db/parker.db`)
- **Schema:**

```
videos
  video_id TEXT PK, title, author, total_duration_sec, utterance_count, chapter_count, speakers (JSON array)

utterances
  id INTEGER PK, video_id FK, idx, speaker, text, start_sec REAL, end_sec REAL, chapter INTEGER
  INDEX on video_id, speaker, (video_id + chapter)

chapters
  id INTEGER PK, video_id FK, chapter, start_idx, end_idx, start_time, end_time, duration_sec

utterances_fts  (FTS5 virtual table)
  content = 'utterances', sync via triggers
  indexed columns: text, speaker, video_id
```

- **Notable:** Two DBs exist (`data/parker.db` and `db/parker.db`) with slightly different schemas — the `scripts/store_db.py` and root `store.py` diverged at some point.

### Phase 4 — Search
- **Script:** `parker_search.py`
- **What it does:** SQLite FTS5 full-text search across all utterances. Supports filtering by speaker, video, chapter. Returns results with YouTube timestamp links.

### Phase 5 — Analytics
- **Script:** `parker_analytics.py`
- **Commands:**
  - `mentions <keyword>` — count occurrences by speaker/video
  - `guest-stats` — who talked most, longest conversations
  - `topics` — topic keyword matching across 12 categories (economy, immigration, media, conspiracy, etc.)
  - `transcript <video_id>` — view transcript filtered by chapter/speaker
  - `export-dashboard` — JSON export for Datasette

### Phase 6 — Export
- **Script:** `obsidian_export.py`
- **What it does:** Generates Markdown notes with speaker-labeled transcripts for Obsidian vault. (**This is now vestigial — vault is no longer the home for this project.**)

### Dashboard
- **Metadata:** `metadata.json` defines Datasette-compatible dashboard config
- **Tables:** Videos, Transcript, Chapters
- **Prebuilt queries:** Keyword Mention Count, Topic Heatmap, Guest Leaderboard, Search Transcripts, Epstein Tracker
- **Dataset scale:** 6 videos, ~9,800 utterances, ~68 chapters

---

## 3. Current Pain Points

| Issue | Detail |
|---|---|
| **Speaker ID is fragile** | Regex-based Parker detection + turn alternation. No real speaker diarization. YouTube `>>` markers are unreliable. Guest labels are anonymized (`guest_1`) |
| **Two DBs, divergent** | `data/parker.db` and `db/parker.db` have different schemas. Which one is canonical? |
| **Hardcoded paths** | `obsidian_export.py` still points to the old vault path |
| **No pipeline state machine** | No tracking of what's been fetched/structured/stored. `run_pipeline.py` skips if raw exists, but there's no progress ledger |
| **Python 3.10 bytecode** | `__pycache__/` compiled for 3.10, running on 3.14 now — harmless but messy |
| **No guest identity tracking** | Same guest across videos is a new `guest_1` each time. No way to say "caller X appeared in streams A, B, C" |
| **No incremental update** | Adding a new video re-runs all phases manually. No watch-for-new-videos mode |
| **No export/API layer** | Only Datasette SQL queries. No REST API, no webhook for new content |

---

## 4. Suggested V4 Architecture

```
                      ┌──────────────┐
                      │  YT RSS /     │
                      │  Webhook      │
                      └──────┬───────┘
                             │ new video
                             ▼
 ┌─────────────────────────────────────────────┐
 │                 Pipeline                    │
 │  ┌────────┐  ┌──────────┐  ┌────────────┐  │
 │  │ Fetch  │→ │ Diarize  │→ │ Normalize  │  │
 │  │ (YT API)│  │ (whisperX │  │ (speaker ID │  │
 │  │        │  │  or similar)│  │  resolution)│  │
 │  └────────┘  └──────────┘  └────────────┘  │
 │        │           │              │         │
 │        ▼           ▼              ▼         │
 │  ┌────────────────────────────────────┐     │
 │  │         SQLite DB (single)         │     │
 │  │  - videos, speakers, utterances,  │     │
 │  │  - chapters, topics, tags         │     │
 │  │  - FTS5 for search               │     │
 │  └──────────────┬───────────────────┘     │
 └─────────────────┼─────────────────────────┘
                   │
     ┌─────────────┼─────────────┐
     ▼             ▼             ▼
 ┌────────┐  ┌─────────┐  ┌──────────┐
 │ Search │  │Analytics│  │Dashboard │
 │ (CLI)  │  │ (CLI)   │  │ (web UI) │
 └────────┘  └─────────┘  └──────────┘
```

### V4 Priorities (pick your battles):

**P1 — Speaker Identity**
- Replace heuristic with actual speaker diarization (WhisperX, pyannote, or AssemblyAI)
- OR at minimum: maintain a guest alias registry so repeat callers can be labeled across videos
- Store a `speakers` table with cross-video ID mapping

**P2 — Single Canonical DB**
- One schema, one `parker.db`. Kill the duplicate.
- Add migration tracking (schema version in DB)

**P3 — Dashboard as Primary UI**
- Datasette is a reasonable start but limited
- Options: Superset (already installed on this machine), or a custom lightweight web UI (FastAPI + SQLite)
- Real-time search, topic filters, speaker filters, YouTube timestamp deep-links

**P4 — Pipeline as State Machine**
- Track each video through phases (fetched → structured → stored → analyzed)
- `pipeline status` command to see what's processed, what's pending
- Allow re-processing individual phases

**P5 — Guest Identity & Tracking**
- Caller profiles: how many times they appeared, topics they discussed, political stance, sentiment
- "Show me all callers who mentioned Epstein" → list of guests + their streams

**P6 — Automated Ingestion**
- Poll Parker's YT channel RSS for new uploads
- Or webhook from YouTube
- Auto-run pipeline on new video

### Not-In-Scope (for now)
- Sentiment analysis on utterances
- Video download / clip extraction
- Multi-channel support (Parker-specific pipeline)

---

## 5. Current Data Summary

| Metric | Value |
|---|---|
| Videos processed | 6 |
| Total utterances | ~9,818 |
| Total chapters | ~68 |
| Identified speakers | 1 (Parker) + anonymous guests |
| Longest stream | 361 min (K_GoVxa5y6c) |
| Shortest stream | 153 min (E4idI3zRVTM) |
| DB size (data/parker.db) | [check with `ls -lh`] |

### Video IDs

| ID | Title | Duration | Utterances | Chapters |
|---|---|---|---|---|
| VlpsB1zj9qc | Parker Debates Trump supporters LIVE | ? | ? | ? |
| iu5qIXAYy24 | Parker Debates Trump supporters LIVE | ? | ? | ? |
| ao6FjGu1bbE | Parker Debates Trump supporters LIVE | ? | ? | ? |
| E4idI3zRVTM | Parker Debates Trump supporters LIVE | 153 min | 984 | 7 |
| K_GoVxa5y6c | ft. Dean Withers | 361 min | 2,381 | 23 |
| JPBNQ1imn0E | Parker Stream | ? | ? | ? |

---

## 6. Quick Start (as-is)

```bash
# Fetch a new video
python3 fetch_transcript.py "https://youtube.com/watch?v=VIDEO_ID"

# Full pipeline
python3 run_pipeline.py "VIDEO_ID"

# Batch from file
python3 run_pipeline.py --batch streams.txt

# Search
python3 parker_search.py "epstein"

# Analytics
python3 parker_analytics.py mentions "tariff,immigration"
python3 parker_analytics.py guest-stats
python3 parker_analytics.py topics

# Start Datasette dashboard
datasette data/parker.db --metadata metadata.json
```
