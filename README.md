# Parker Debate Dashboard

**YouTube URL in, speaker-labeled argument map out.**

Transcribes long-form 1-on-1 debate videos, separates who said what, extracts the claims,
and puts the whole argument landscape behind a filterable dashboard.

The goal isn't "what was said" — it's **topic mapping**. Across every debate, on any given
subject: what are all the arguments, who makes them, how often, and where do they collide.

This is analytical, not evaluative. It does not score debates or decide who won.

---

## Status

Running on real data. As of 2026-07-16:

| | |
|---|---|
| Debates processed | **15** |
| Utterances extracted | **3,934** |
| Speaker attribution | parker 1,976 · caller 1,957 · **unknown 1** (99.97%) |
| Human-reviewed | 6 approved · 3 in progress · 6 unreviewed |
| NLP analysis | 3 of 15 debates — 11 topics, 50 keywords, 30 stances |
| Tests | 1,648 lines across 13 modules |

**Note:** `data/` is gitignored (audio, transcripts, DBs are large and rights-encumbered),
so a fresh clone starts empty. The numbers above are from the local working DB.

**Known gap:** NLP extraction has only been run on 3 of 15 debates. Transcription and
review are ahead of analysis.

---

## Why the human review step exists

The project constraint was that prior AI-only speaker parsing produced poor results. So the
pipeline doesn't trust its own diarization — every debate lands in a review interface where
speaker attribution can be corrected before it flows into analysis.

On the current corpus, constrained 2-speaker diarization gets 3,933 of 3,934 utterances
attributed, and the parker/caller split (1,976/1,957) matches what a 1-on-1 format should
produce. Review catches the rest.

---

## How it works

```
YouTube URL
   ↓  yt-dlp                     audio download
   ↓  WhisperX                   transcription, word-level timestamps
   ↓  pyannote                   diarization, constrained to exactly 2 speakers
   ↓  review UI                  human corrects speaker attribution
   ↓  LLM extraction             claims, topics, stances → Pydantic schemas
   ↓  embeddings                 semantic search across utterances
   ↓  FastAPI + SQLite FTS5      public filterable dashboard
```

Each video is processed in isolation with checkpointing — one failure doesn't cascade, and
`retry` picks up where it stopped.

---

## Quick start

```bash
uv sync                              # or: pip install -e ".[dev]"
cp .env.example .env                 # add HF_TOKEN for pyannote diarization

parker process "https://youtube.com/watch?v=..."   # single video
parker batch urls.txt                              # many
parker status                                      # pipeline state
parker retry                                       # resume failures
parker cleanup                                     # clear partial artifacts
parker backfill-slugs                              # assign slugs to existing debates

uvicorn parker.web:app --reload      # dashboard at localhost:8000
```

Admin routes live under `/admin/*`; public dashboard at `/`.

---

## Stack

**Pipeline:** WhisperX · pyannote · yt-dlp · Typer
**Data:** SQLModel · SQLite + FTS5 · Pydantic v2
**Analysis:** LLM claim extraction with structured schemas · embeddings-backed search
**Web:** FastAPI · Jinja2
**Deploy:** gunicorn · nginx · systemd (`deploy/`)

## Layout

```
src/parker/
  pipeline.py      orchestration + checkpointing
  download.py      yt-dlp ingestion
  transcribe.py    WhisperX + diarization
  speakers.py      speaker assignment
  crud.py          data layer
  models.py        SQLModel schema
  analytics.py     cross-debate aggregation
  search.py        FTS + semantic search
  nlp/
    extractor.py   claim/topic/stance extraction
    embeddings.py  vector search
    schemas.py     Pydantic output contracts
    prompts.py     extraction prompts
  web/             FastAPI routes, templates, static
tests/             13 modules, 1,648 lines
.planning/         phase plans, specs, state
```

## Testing

```bash
pytest              # 48 tests
ruff check .
```

Tests cover pipeline wiring, CRUD, schema validation, and device detection. Transcription
itself is mocked — WhisperX inference is validated by the human review pass on real audio,
not in CI.

---

## Scope

**In:** batch ingestion, 2-speaker debates, topic mapping, public dashboard, dozens of videos.

**Out:** debate scoring or "who won" judging, real-time/streaming processing, mobile app,
thousands-of-videos scale.
