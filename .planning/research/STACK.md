# Stack Research

**Domain:** YouTube debate transcription and analysis
**Researched:** 2026-04-09
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | ML pipeline, data processing | Lingua franca for ML/AI. 3.11+ for performance gains. All ML libraries target Python first. |
| Next.js | 15.x | Public dashboard frontend | Full-stack React framework. SSR for SEO on public pages. API routes for backend endpoints. Massive ecosystem. |
| TypeScript | 5.x | Frontend type safety | Standard for Next.js projects. Catches data shape errors at compile time — critical when wrangling transcript data. |
| faster-whisper | 1.2.1 | Speech-to-text transcription | Best open-source transcription quality. CTranslate2 backend is 4x faster than openai/whisper with same accuracy. Supports `large-v3` and `turbo` models. Word-level timestamps built in. |
| pyannote-audio | 4.0.4 | Speaker diarization | State-of-the-art open-source diarization. `community-1` pipeline is free. For 1v1 debates, setting `num_speakers=2` gives dramatically better results. DER 11.7% on AISHELL-4 benchmark. |
| yt-dlp | Latest (nightly) | YouTube video/audio download | The standard. 156k GitHub stars. Actively maintained. Extracts audio, metadata, thumbnails. Nightly channel recommended for YouTube reliability. |
| SQLite (via better-sqlite3) | 3.x | Primary database | Dozens of videos = thousands of transcript segments. SQLite handles this trivially. Zero ops. Single file. Fast reads. No server needed. Upgrade to PostgreSQL only if you hit concurrent write limits. |
| Tailwind CSS | 4.x | Dashboard styling | Utility-first CSS. Ships minimal CSS. Perfect for data-heavy dashboards. |
| shadcn/ui | Latest | UI component library | Copy-paste components built on Radix UI. Full control over code. Excellent for dashboards with tables, filters, charts. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| WhisperX | 3.8.5 | Combined transcription + diarization pipeline | **Alternative to running faster-whisper + pyannote separately.** WhisperX orchestrates both with forced alignment for word-level speaker assignment. Recommended starting point — simpler than wiring the two libraries manually. |
| BERTopic | 0.17.x | Topic modeling across debates | Extracts topics from transcript segments. Supports dynamic topic modeling over time. Good for "what topics does Parker debate most?" queries. |
| transformers | 4.x | Sentiment analysis, NER | HuggingFace pipeline for sentiment classification. Use `finiteautomata/bertweet-base-sentiment-analysis` or similar domain-adaptable model. |
| FastAPI | 0.115.x | ML pipeline API server | Serves transcript data to Next.js frontend. Pydantic models for transcript schema validation. Automatic OpenAPI docs. |
| SQLModel | 0.0.22+ | Python ORM for SQLite | SQLAlchemy + Pydantic hybrid. Type-safe database models that double as API schemas. |
| Recharts | 2.x | Dashboard charts | React charting library. Composable, responsive. Good for sentiment timelines, frequency bar charts, topic heatmaps. |
| TanStack Table | 8.x | Data tables with filtering | Headless table primitives. Sorting, filtering, pagination. Essential for filterable transcript views. |
| Zod | 3.x | Runtime validation | Validates API responses and form inputs in Next.js. Catches data shape mismatches early. |
| pydantic | 2.x | Data validation (Python) | Transcript schema definition. Validates diarization output, enforces data contracts between pipeline stages. |
| ffmpeg / PyAV | Latest | Audio extraction and processing | Required by faster-whisper (uses PyAV internally) and pyannote. yt-dlp needs ffmpeg for audio extraction. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Python package management | Fast Rust-based pip/venv replacement. Used by pyannote and whisperX. |
| just | Task runner | For pipeline scripts: `just transcribe URL`, `just process-all`, etc. |
| ruff | Python linter/formatter | Replaces flake8 + black + isort. Fast. |
| biome | JS/TS linter/formatter | Fast Rust-based replacement for ESLint + Prettier. |
| pytest | Python testing | Test transcript parsing, diarization output format, data transformations. |
| vitest | Frontend testing | Fast, Vite-native test runner for React components. |

## Installation

```bash
# Python ML pipeline
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install whisperx==3.8.5 pyannote.audio==4.0.4 yt-dlp ffmpeg-python bertopic transformers fastapi sqlmodel pydantic

# Or install yt-dlp nightly for best YouTube support
uv pip install --pre "yt-dlp[default]"

# Frontend
npx create-next-app@latest dashboard --typescript --tailwind --eslint --app --src-dir
cd dashboard
npx shadcn@latest init
npx shadcn@latest add table card badge input select tabs
npm install recharts zod @tanstack/react-table
```

## Architecture Overview

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   yt-dlp    │────▶│  WhisperX        │────▶│   SQLite    │
│  (download) │     │  (transcribe +   │     │  (structured│
│             │     │   diarize)       │     │   data)     │
└─────────────┘     └──────────────────┘     └──────┬──────┘
                                                     │
                    ┌──────────────────┐              │
                    │  NLP Pipeline    │◀─────────────┘
                    │  (sentiment,     │
                    │   topics, freq)  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  FastAPI         │
                    │  (REST API)      │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Next.js         │
                    │  (Dashboard)     │
                    └──────────────────┘
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| WhisperX (local) | Deepgram API ($0.0097/min with diarization) | If you don't have a GPU. Deepgram Nova-3 quality is excellent. Cost for 50 hours of debate ≈ $29. |
| WhisperX (local) | AssemblyAI API ($0.23/hr with diarization) | If you want built-in sentiment analysis, topic detection, and entity extraction from a single API. Higher cost but more features out of the box. |
| WhisperX (local) | OpenAI Whisper API ($0.006/min) | Cheapest API option, but no diarization. Would need separate pyannote step anyway. Defeats the purpose. |
| SQLite | PostgreSQL | If you need concurrent writes from multiple pipeline workers, or expect >1000 videos, or need full-text search. Overkill for dozens of videos. |
| pyannote community-1 | pyannote precision-2 (premium) | If community-1 diarization accuracy is insufficient for your debates. precision-2 has ~30% lower DER. Has free credits to test. |
| BERTopic | LLM-based topic extraction (GPT-4) | If topics are domain-specific and need nuanced understanding. Higher cost, slower, but more accurate for philosophical/political debate topics. Consider for a v2. |
| faster-whisper `large-v3` | faster-whisper `turbo` | If transcription speed matters more than marginal accuracy gains. `turbo` is nearly as accurate as `large-v3` but faster. Both work well for English. |
| Next.js | Plain React + Vite | If you don't need SSR or API routes. You'd need a separate backend regardless. Next.js simplifies deployment. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| openai/whisper (original) | 4x slower than faster-whisper for same accuracy. No batching. Higher memory usage. | faster-whisper via WhisperX |
| google-cloud-speech | Expensive ($0.016/min minimum), worse diarization than pyannote, vendor lock-in. | WhisperX + pyannote |
| YouTube auto-captions | No speaker diarization. Low accuracy on debate content. No timestamps per speaker. Unreliable formatting. | WhisperX transcription |
| MongoDB | Document store adds complexity with no benefit. Transcript data is highly relational (videos → segments → speakers → analytics). | SQLite |
| Simple diarization (energy-based) | Terrible accuracy on debate audio where speakers may sound similar. Not production-viable. | pyannote-audio (neural diarization) |
| Whisper without forced alignment | Utterance-level timestamps are inaccurate by seconds. Word-level alignment is essential for accurate speaker assignment. | WhisperX with wav2vec2 forced alignment |
| WebSockets for pipeline | Unnecessary complexity for batch processing. These are pre-recorded videos, not live streams. | REST API (FastAPI) |
| Elasticsearch / Meilisearch | Overkill for dozens of videos. SQLite FTS5 handles full-text search on transcripts just fine. | SQLite FTS5 |

## Stack Patterns by Variant

**If running on a machine without GPU:**
- Use Deepgram API for transcription + diarization (bundled, high quality)
- Cost: ~$0.01/min = ~$30 for 50 hours of debate content
- Simpler pipeline, no CUDA dependencies

**If budget allows paid APIs and you want maximum simplicity:**
- AssemblyAI for transcription + diarization + sentiment + topics in one API call
- Single vendor, no ML dependencies to manage
- Cost: ~$0.23/hr for all features

**If you need the best possible diarization accuracy:**
- Use pyannote `precision-2` (premium API) instead of `community-1`
- DER drops from ~17% to ~13% on conversational benchmarks
- Can still run transcription locally with faster-whisper, only send audio to pyannote for diarization
- For 1v1 debates with `num_speakers=2`, accuracy will be significantly higher than benchmarks suggest

**If you want to process videos incrementally:**
- Store raw audio files alongside SQLite database
- Pipeline is idempotent: re-running on same video checks for existing transcript
- Add new videos by URL, pipeline handles download → transcribe → diarize → analyze → store

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| faster-whisper 1.2.1 | CUDA 12 + cuDNN 9 | For CUDA 11, downgrade ctranslate2 to 3.24.0 |
| faster-whisper 1.2.1 | Python 3.9+ | Tested through Python 3.13 |
| pyannote-audio 4.0.4 | Python 3.10+ | Requires ffmpeg system dependency |
| WhisperX 3.8.5 | faster-whisper, pyannote-audio | Bundles compatible versions |
| WhisperX 3.8.5 | CUDA 12.8 | Recommended CUDA version per their docs |
| yt-dlp | Python 3.10+ | Requires ffmpeg for audio extraction |
| Next.js 15 | Node.js 18.18+ | Requires Node 18 minimum |

## Key Decisions and Rationale

### Why WhisperX as the starting point
WhisperX combines faster-whisper (transcription) + pyannote (diarization) + wav2vec2 (forced alignment) into a single pipeline with word-level speaker assignment. For 1v1 debates, this is the highest quality open-source option available. You can always swap individual components later.

### Why SQLite over PostgreSQL
Dozens of videos × ~30 min each = ~1000-2000 segments. SQLite handles millions of rows. No server, no config, no connection pooling. The database is a single file you can version control. If you ever outgrow it, migrating to PostgreSQL is straightforward since SQLModel abstracts the driver.

### Why Python for ML + Next.js for dashboard
The ML ecosystem is Python-only. There's no credible alternative for transcription/diarization/NLP. The dashboard is a standard web app — Next.js gives you SSR, API routes, and the React ecosystem. FastAPI bridges them with a clean REST API. This split is standard in ML-powered web applications.

### Diarization strategy for 1v1 debates
The `num_speakers=2` constraint is the single biggest accuracy lever. Pyannote's community-1 model, when told there are exactly 2 speakers, performs dramatically better than when it has to discover speaker count. Always pass `min_speakers=2, max_speakers=2` for debate content.

## Sources

- faster-whisper GitHub: https://github.com/SYSTRAN/faster-whisper (v1.2.1, released Oct 2025)
- pyannote-audio GitHub: https://github.com/pyannote/pyannote-audio (v4.0.4, released Feb 2026)
- WhisperX GitHub: https://github.com/m-bain/whisperX (v3.8.5, released Apr 2026)
- yt-dlp GitHub: https://github.com/yt-dlp/yt-dlp (156k stars, nightly channel)
- Deepgram Pricing: https://deepgram.com/pricing (Nova-3 at $0.0077/min)
- AssemblyAI Pricing: https://assemblyai.com/pricing (Universal-3 Pro at $0.21/hr)
- pyannote community-1 model: https://hf.co/pyannote/speaker-diarization-community-1
- pyannote precision-2: https://docs.pyannote.ai

---
*Stack research for: YouTube debate transcription and analysis*
*Researched: 2026-04-09*
