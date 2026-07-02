# Architecture Research

**Domain:** YouTube debate transcription and analysis
**Researched:** 2026-04-09
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BATCH PROCESSING LAYER                       │
│                                                                     │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌─────────┐ │
│  │ YouTube  │──>│   WhisperX   │──>│    NLP       │──>│  Data   │ │
│  │ Ingest   │   │  Pipeline    │   │  Analysis    │   │  Store  │ │
│  └──────────┘   └──────────────┘   └──────────────┘   └────┬────┘ │
│       │               │                   │                 │      │
│       │         ┌─────┴─────┐       ┌─────┴─────┐          │      │
│       │         │ • Whisper  │       │ • Keywords │          │      │
│       │         │ • VAD      │       │ • Topics   │          │      │
│       │         │ • Forced   │       │ • Sentiment│          │      │
│       │         │   Align    │       │ • Phrases  │          │      │
│       │         │ • Diarize  │       └───────────┘          │      │
│       │         └───────────┘                               │      │
└─────────────────────────────────────────────────────────────┼──────┘
                                                              │
┌─────────────────────────────────────────────────────────────┼──────┐
│                     HUMAN REVIEW LAYER                       │      │
│                                                              │      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐     │      │
│  │  Speaker     │   │  Topic       │   │  Transcript  │     │      │
│  │  Correction  │──>│  Refinement  │──>│  Approval    │─────┘      │
│  │  UI          │   │  UI          │   │  UI          │            │
│  └──────────────┘   └──────────────┘   └──────────────┘            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PUBLIC DASHBOARD LAYER                          │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Single   │  │ Cross    │  │ Filter   │  │  API             │   │
│  │ Debate   │  │ Debate   │  │ Engine   │  │  Layer           │   │
│  │ View     │  │ View     │  │          │  │  (Static/SSR)    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| YouTube Ingest | Download audio from YouTube URLs, extract metadata | yt-dlp CLI/library |
| WhisperX Pipeline | Transcription, word-level timestamps, speaker diarization | WhisperX (Whisper + pyannote) |
| NLP Analysis | Keyword extraction, topic extraction, sentiment analysis, phrase frequency | LLM API or spaCy + custom |
| Data Store | Persist structured debate data, transcripts, analysis results | SQLite (dev) / PostgreSQL (prod) |
| Speaker Correction UI | Human review/correction of speaker attribution | Web form (part of dashboard) |
| Topic Refinement UI | Human review/refinement of AI-extracted topics | Web form (part of dashboard) |
| Transcript Approval UI | Final review gate before data goes public | Web form (part of dashboard) |
| Single Debate View | Deep dive into one debate — transcript, speakers, topics, sentiment | Dashboard page |
| Cross Debate View | Pattern analysis across all debates — shared topics, recurring phrases | Dashboard page |
| Filter Engine | Filter by entity, sentiment, time, metrics across debates | API query builder |
| API Layer | Serve structured data to dashboard, handle filter queries | REST or tRPC |

## Recommended Project Structure

```
src/
├── pipeline/              # Batch processing: ingest → transcript → analysis
│   ├── ingest/            # YouTube download and metadata extraction
│   ├── transcription/     # WhisperX wrapper, audio processing
│   ├── diarization/       # Speaker labeling, Parker vs caller assignment
│   ├── nlp/               # Keyword, topic, sentiment, phrase extraction
│   └── orchestrator.py    # Pipeline runner — coordinates stages
├── store/                 # Data access layer
│   ├── models/            # Data models / ORM schemas
│   ├── db.py              # Database connection and migrations
│   └── queries/           # Query functions for dashboard
├── dashboard/             # Public-facing web frontend
│   ├── pages/             # Route-level pages
│   ├── components/        # UI components (filters, charts, transcript viewer)
│   └── api/               # API route handlers
├── review/                # Human review interface (admin)
│   ├── speaker-correction/# Fix speaker attribution errors
│   ├── topic-refinement/  # Accept/reject/edit AI-extracted topics
│   └── approval/          # Gate before publishing
├── shared/                # Shared types, constants, utilities
│   └── types/             # TypeScript types or Pydantic models
└── scripts/               # CLI tools for batch operations
    ├── process_video.py   # Process single video through pipeline
    ├── batch_process.py   # Process multiple videos
    └── export.py          # Export data utilities
```

### Structure Rationale

- **pipeline/:** All batch processing is isolated. Each stage is independent and testable. The orchestrator ties them together but each stage can run standalone for debugging.
- **store/:** Single data access layer shared by dashboard and review UI. Prevents query duplication and enforces data consistency.
- **dashboard/:** Public-facing web app. Separated from review/ because access patterns, caching, and deployment may differ.
- **review/:** Admin-only human review flows. Could share auth with dashboard or be separate — this is a deployment concern, not an architecture one.
- **scripts/:** CLI tools for batch operations. These are operational utilities, not part of the running application.

## Architectural Patterns

### Pattern 1: Pipeline with Checkpointing
**What:** Each pipeline stage writes its output to the data store. Subsequent stages read from the store, not from the previous stage's in-memory output. If a stage fails, you restart from the last checkpoint, not the beginning.
**When to use:** Batch processing pipelines where stages are expensive (transcription takes minutes per video).
**Trade-offs:** Slightly more complex data flow, but resilience against failures is critical when transcription takes real time and money.

### Pattern 2: Structured Transcript as Central Data Model
**What:** The transcript is the spine of the system. Everything hangs off it. A `Utterance` has: text, speaker, start/end time, debate_id. Keywords, topics, sentiment are all linked to utterances or spans of utterances.
**When to use:** When analysis is always in context of "who said what when."
**Trade-offs:** More normalized schema, but queries are straightforward because everything joins to utterances.

### Pattern 3: AI-First with Human Review Gate
**What:** AI does the initial pass (diarization, topic extraction, sentiment). Human review is a structured correction step, not a from-scratch annotation step. The AI output is presented as suggestions that humans accept, reject, or modify.
**When to use:** When AI output is "mostly right" but not reliable enough for production without verification.
**Trade-offs:** Review UI needs to show AI confidence and make correction easy. If AI quality is very low, the review step becomes more expensive than manual annotation.

### Pattern 4: Static Site Generation for Dashboard
**What:** Pre-compute dashboard views from the data store. Deploy as static pages or server-rendered pages with aggressive caching. The dashboard is read-only — no live queries from the public site.
**When to use:** Public dashboard with infrequent data updates (new debates added weekly, not hourly).
**Trade-offs:** Need a rebuild/revalidate step when data changes, but public site is fast and cheap to host.

## Data Flow

### Request Flow (Batch Processing)

```
YouTube URL
    │
    ▼
┌──────────────────────────────────────────────┐
│ 1. INGEST                                     │
│    • Download audio (yt-dlp)                  │
│    • Extract metadata (title, date, duration) │
│    • Save raw audio file                      │
│    • Create Debate record in DB               │
│    Status: INGESTED                           │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│ 2. TRANSCRIPTION + DIARIZATION                │
│    • Run WhisperX pipeline:                   │
│      - VAD (voice activity detection)         │
│      - Whisper transcription (batched)        │
│      - Forced alignment (word-level timestamps│
│      - Pyannote diarization (num_speakers=2)  │
│    • Assign: SPEAKER_00 → Parker,             │
│              SPEAKER_01 → Caller              │
│    • Create Utterance records in DB           │
│    Status: TRANSCRIBED                        │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│ 3. NLP ANALYSIS                               │
│    • Extract keywords per utterance           │
│    • Extract topics per debate                │
│    • Sentiment analysis per utterance         │
│    • Phrase frequency counting                │
│    • Create Topic, Keyword, Sentiment records │
│    Status: ANALYZED                           │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│ 4. HUMAN REVIEW                               │
│    • Speaker correction (fix misattributions) │
│    • Topic refinement (add/remove/merge)      │
│    • Final approval                           │
│    Status: REVIEWED → PUBLISHED              │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│ 5. PUBLISH                                    │
│    • Rebuild cached dashboard views           │
│    • Update search indices                    │
│    Status: LIVE                               │
└──────────────────────────────────────────────┘
```

### Key Data Flows

1. **Ingestion Flow:** YouTube URL → yt-dlp → raw audio file + metadata → Debate record in DB. Audio stored locally (or in S3). Metadata includes YouTube ID, title, upload date, duration.

2. **Transcription Flow:** Raw audio → WhisperX (Whisper large-v2 + pyannote diarization with `min_speakers=2, max_speakers=2`) → array of utterances with word-level timestamps and speaker labels → Utterance records in DB.

3. **Speaker Assignment Flow:** After diarization produces SPEAKER_00/SPEAKER_01, assign Parker to the speaker with more total speaking time (or the host pattern). This is a heuristic that needs human verification.

4. **NLP Flow:** Array of utterances → keyword extraction (per utterance) + topic extraction (per debate) + sentiment analysis (per utterance) → Topic, Keyword, Sentiment records linked to utterances.

5. **Dashboard Query Flow:** User filter request → API layer → query builder → DB → JSON response → dashboard rendering. Filters combine: speaker, topic, keyword, sentiment range, date range.

6. **Review Flow:** Admin loads debate → sees transcript with speaker labels + AI-extracted topics → corrects speaker attribution → approves topics → marks debate as reviewed.

## Data Model (Core Entities)

```
Debate
├── id, youtube_id, title, upload_date, duration
├── topic (pre-defined), status (ingested|transcribed|analyzed|reviewed|published)
├── caller_name (optional, can be added during review)
└── created_at, updated_at

Utterance
├── id, debate_id (FK → Debate)
├── speaker (parker | caller)
├── text, start_time, end_time
├── word_count
└── created_at

Keyword
├── id, utterance_id (FK → Utterance), debate_id (FK → Debate)
├── keyword, frequency (across debate)
├── source (ai_extracted | human_added)
└── confidence

Topic
├── id, debate_id (FK → Debate)
├── name, description
├── source (ai_extracted | human_refined)
├── status (suggested | confirmed | rejected)
└── utterance_ids (link table for topic mentions)

Sentiment
├── id, utterance_id (FK → Utterance)
├── score (float, -1.0 to 1.0)
├── label (positive | neutral | negative)
├── model_used, confidence
└── is_overridden (boolean — human correction flag)

Phrase
├── id, text, normalized_text
├── frequency (total across all debates)
└── appearances (link table → utterance_id + debate_id)
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Dozens of videos (current) | SQLite sufficient. Single-machine processing. Monorepo fine. |
| Hundreds of videos | Move to PostgreSQL. Add processing queue (Celery/Redis). Separate review and dashboard deployments. |
| Thousands of videos | Add object storage (S3) for audio files. Horizontal scaling for NLP pipeline. Consider read replicas for dashboard DB. |

**This project is designed for dozens of videos.** Do not over-engineer for scale that won't arrive. SQLite, local files, single deployment.

## Anti-Patterns

### Anti-Pattern 1: Real-Time Processing Expectations
**What people do:** Build a streaming pipeline that processes videos as they're uploaded.
**Why it's wrong:** This is a batch workload. Dozens of videos processed once. Real-time infrastructure adds complexity for zero benefit.
**Do this instead:** CLI scripts that process videos one-at-a-time or in batches. Pipeline state tracked in DB for resume capability.

### Anti-Pattern 2: Skipping Human Review
**What people do:** Trust AI diarization and topic extraction completely, skip human verification.
**Why it's wrong:** The project brief explicitly notes "previous attempts with AI speaker parsing produced poor results." Speaker attribution errors propagate to every downstream analysis — sentiment, topic mapping, comparison views all become unreliable.
**Do this instead:** Make human review a first-class step. Design the review UI to be fast and efficient. AI suggests, human verifies.

### Anti-Pattern 3: Generic Diarization
**What people do:** Use pyannote with default settings, accept SPEAKER_00/SPEAKER_01 as final.
**Why it's wrong:** This is always 2 speakers (Parker + caller). Generic diarization doesn't exploit this constraint. It also doesn't identify *which* speaker is Parker.
**Do this instead:** Always pass `min_speakers=2, max_speakers=2` to constrain the model. Then use heuristics (Parker speaks more, Parker introduces topics, Parker's voice is consistent across videos) plus human review to assign Parker vs. caller labels. Consider creating a Parker voice embedding for future videos.

### Anti-Pattern 4: Building the Dashboard Before the Data
**What people do:** Start with the frontend dashboard, mock data, build visualizations.
**Why it's wrong:** Dashboard requirements change based on what the data actually looks like. You'll rebuild the dashboard once you see real transcript + analysis output.
**Do this instead:** Build pipeline first. Process 3-5 videos end-to-end. See what the data looks like. Then build the dashboard to match the actual data shape.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| YouTube (yt-dlp) | CLI subprocess call | Download audio, extract metadata. No API key needed for public videos. |
| WhisperX | Python library call | Local execution. Requires CUDA GPU for reasonable speed. Falls back to CPU (slower). |
| pyannote (via WhisperX) | Bundled with WhisperX | Requires HuggingFace token + accepting model license (CC-BY-4.0 for community model). |
| OpenAI/Anthropic API (NLP) | HTTP API calls | For topic extraction, sentiment analysis. Can substitute with local models (spaCy, transformers) to avoid API costs. |
| LLM API (speaker heuristic) | HTTP API call | Optional: use LLM to help determine which speaker is Parker based on transcript content patterns. |

### Recommended Primary Tool: WhisperX

WhisperX is purpose-built for this exact use case. It combines:
- **Whisper** (best available transcription)
- **Forced alignment** (word-level timestamps via wav2vec2)
- **Pyannote diarization** (speaker labeling)
- **VAD** (voice activity detection to reduce hallucination)

Into a single pipeline with one command:

```python
import whisperx
# Transcribe + align + diarize in one pass
model = whisperx.load_model("large-v2", device="cuda", compute_type="float16")
audio = whisperx.load_audio("debate.mp3")
result = model.transcribe(audio, batch_size=16)

# Word-level alignment
model_a, metadata = whisperx.load_align_model(language_code=result["language"], device="cuda")
result = whisperx.align(result["segments"], model_a, metadata, audio, "cuda")

# Speaker diarization (constrained to 2 speakers)
diarize_model = whisperx.DiarizationPipeline(token=HF_TOKEN, device="cuda")
diarize_segments = diarize_model(audio, min_speakers=2, max_speakers=2)
result = whisperx.assign_word_speakers(diarize_segments, result)
```

This eliminates the need to wire Whisper + pyannote + alignment separately.

### NLP Pipeline Options

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| LLM API (GPT-4/Claude) | Best quality topic extraction, understands context, handles nuance | Cost per video, API dependency | Use for topic extraction + sentiment on first pass |
| spaCy + transformers | Free, local, fast, no API dependency | Lower quality topic extraction, more engineering | Use for keyword extraction, NER, basic sentiment |
| Hybrid (LLM for topics, local for keywords) | Best of both worlds | Two systems to maintain | Recommended approach |

## Build Order

The pipeline stages define the natural build order. Each stage depends on the previous one's output:

```
Phase 1: INGEST + TRANSCRIPTION          ← Foundation, validates approach
  ├── YouTube download (yt-dlp)
  ├── WhisperX integration
  ├── Basic DB schema (Debate, Utterance)
  └── Process 3-5 test videos, inspect output quality

Phase 2: SPEAKER ASSIGNMENT + REVIEW      ← Solves the hardest problem
  ├── Parker vs. caller heuristic
  ├── Speaker correction UI (admin)
  ├── Process all videos
  └── Human review of all speaker attributions

Phase 3: NLP ANALYSIS                     ← Builds on verified data
  ├── Keyword extraction pipeline
  ├── Topic extraction + refinement UI
  ├── Sentiment analysis
  └── Phrase frequency counting

Phase 4: DASHBOARD                        ← Built with real data in hand
  ├── Single debate view
  ├── Cross-debate analysis view
  ├── Filter engine
  └── Public deployment

Phase 5: POLISH + ITERATE
  ├── Parker voice embedding (improve future diarization)
  ├── Export/share features
  └── Performance optimization
```

**Key insight:** Phases 1 and 2 validate the core premise. If WhisperX + constrained diarization + human review produces accurate speaker attribution, everything else follows. If it doesn't, the approach needs adjustment before building further.

## Sources

- OpenAI Whisper: https://github.com/openai/whisper — MIT license, state-of-the-art transcription
- pyannote-audio: https://github.com/pyannote/pyannote-audio — Speaker diarization, MIT license, community model CC-BY-4.0
- WhisperX: https://github.com/m-bain/whisperX — Combined Whisper + alignment + diarization, BSD-2-Clause
- yt-dlp: https://github.com/yt-dlp/yt-dlp — YouTube download, Unlicense license
- WhisperX paper: Bain et al., "WhisperX: Time-Accurate Speech Transcription of Long-Form Audio", INTERSPEECH 2023

---
*Architecture research for: YouTube debate transcription and analysis*
*Researched: 2026-04-09*
