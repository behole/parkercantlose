# Project Research Summary

**Project:** Parker Debate Dashboard
**Domain:** YouTube debate transcription and analysis
**Researched:** 2026-04-09
**Confidence:** HIGH

## Executive Summary

This research establishes a clear technical path for building a YouTube debate transcription-to-dashboard tool centered on topic mapping — Parker's debates vs. callers, analyzed for argument structure, stance, and cross-debate patterns. The core value proposition (topic/idea extraction with ontology) has no direct competitor; existing tools (Otter, Sonix, Gong) handle meetings and calls, not debate-specific argument analysis.

The recommended architecture follows a batch-processing pipeline: YouTube ingest → WhisperX transcription+diarization → NLP analysis → human review → public dashboard. This order is critical — the user's prior experience with poor AI speaker parsing means the human review gate must be a first-class pipeline stage, not an afterthought. The project is scoped for dozens of videos, which means SQLite, local processing, and single-machine deployment are appropriate. No premature scaling.

The biggest technical risk is diarization quality. Compressed YouTube audio with phone-quality callers degrades speaker separation. Mitigating this requires constraining to exactly 2 speakers, using Parker's voice as a reference embedding, building the correction UI early, and treating AI diarization as a 70% solution that humans refine. All downstream analysis (topic mapping, stance detection, cross-debate patterns) depends on accurate speaker attribution, so this is the make-or-break problem.

## Key Findings

### Recommended Stack

A Python ML pipeline paired with a Next.js dashboard, bridged by FastAPI. WhisperX is the recommended starting point because it combines transcription (Whisper), word-level alignment (wav2vec2), and diarization (pyannote) into a single integrated pipeline — eliminating manual timestamp alignment between systems. SQLite is sufficient for the data volume (dozens of videos = thousands of segments). The stack avoids over-engineering: no PostgreSQL, no message queues, no containerization needed at this scale.

**Core technologies:**
- Python 3.11+: ML pipeline, data processing — lingua franca for ML/AI
- WhisperX 3.8.5: Combined transcription + diarization + forced alignment — single pipeline eliminates timestamp misalignment between systems
- yt-dlp (nightly): YouTube audio download — the standard, 156k stars, actively maintained
- SQLite (via SQLModel): Primary database — handles thousands of segments trivially, zero ops, single file
- FastAPI 0.115.x: API server — bridges Python pipeline to Next.js frontend
- Next.js 15 + TypeScript: Dashboard frontend — SSR for SEO, API routes, React ecosystem
- Tailwind CSS 4 + shadcn/ui: Dashboard styling and components — utility-first CSS, copy-paste components for tables/filters/charts
- Recharts + TanStack Table: Data visualization — composable charts and headless table primitives

**Supporting technologies:**
- BERTopic: Topic modeling across debates (defer to v2 for cross-debate matching)
- HuggingFace transformers: Sentiment/stance analysis
- Zod + Pydantic: Runtime validation on both frontend and backend

### Expected Features

Feature research identified 10 table-stakes features, 10 differentiators, and 8 anti-features. The critical insight is that no competitor offers debate-specific analysis — cross-conversation topic matching, argument structure extraction, and per-topic stance comparison are unique to this tool.

**Must have (table stakes):**
- Video ingestion + transcription — core function, multiple providers available
- Speaker diarization with Parker identification — 2-speaker format is best case for accuracy
- Timestamped, searchable transcript — navigation, citation, verification
- Video-synced playback — YouTube embed with time-synced transcript
- Basic filtering (video, speaker, date) — dashboard users expect Excel-level filtering
- Human correction tools — the user's stated pain point; build early for trust

**Should have (competitive):**
- Topic/idea extraction with ontology — the CORE value prop, no competitor does this for debates
- Side-by-side speaker comparison per topic — instantly see where each party stands
- Cross-debate pattern analysis — "Parker argued X across 12 debates" — the hardest technical challenge
- Stance detection (not generic sentiment) — SUPPORTS/OPPOSES/QUALIFIED/DEFLECTS per topic per speaker
- Frequency measurement — rhetorical pattern detection across the corpus

**Defer (v2+):**
- Argument evolution timeline — requires full corpus + consistent taxonomy
- Topic browser / argument graph — interactive visual map
- Automated new video processing — webhook-triggered pipeline
- API access for researchers

### Architecture Approach

Three-layer architecture: batch processing layer, human review layer, public dashboard layer. The pipeline follows a strict sequential flow: ingest → transcribe+diarize → NLP analysis → human review → publish. Each stage checkpoints to the database, enabling resume-from-failure.

**Major components:**
1. **Pipeline (Python)** — Batch processing: YouTube download, WhisperX transcription+diarization, NLP analysis. Each stage is isolated and testable. Checkpointing enables resume from last successful stage.
2. **Data Store (SQLite)** — Structured debate data with the Utterance as the central data model. Everything (keywords, topics, sentiment) links to utterances. Schema versioned from day one.
3. **Review Interface (Next.js admin)** — Speaker correction, topic refinement, transcript approval. AI suggests, human verifies. Unreviewed transcripts are blocked from the dashboard.
4. **Public Dashboard (Next.js)** — Single-debate view, cross-debate analysis, filter engine. Pre-computed aggregations for performance. SSR with aggressive caching.
5. **API Layer (FastAPI)** — REST API serving structured data to the dashboard. Pydantic models for validation.

**Key architectural patterns:**
- Pipeline with checkpointing (expensive stages must be resumable)
- Structured transcript as central data model (Utterance is the spine)
- AI-first with human review gate (AI does 70%, humans verify)
- Static/SSR generation for dashboard (read-only public site, infrequent updates)

### Critical Pitfalls

1. **Treating diarization as solved** — YouTube audio quality varies, phone callers have compression artifacts. Constrain to 2 speakers, use Parker's voice embedding, build review UI first. All downstream analysis depends on correct speaker attribution.
2. **Building NLP on unreviewed transcripts** — A single transcription error ("don't" → "do") flips meaning. Enforce human review as a gate before NLP. No unreviewed transcript enters the analysis pipeline.
3. **Whisper hallucination on bad audio** — Phone-quality caller audio triggers hallucinated text. Pre-process audio, use large-v3 model, disable `condition_on_previous_text`, test on the worst video first.
4. **Generic sentiment in debate context** — Standard models tag everything "negative" because debate language is combative. Build stance detection (pro/con per topic) instead of polarity classification.
5. **Batch processing without per-video isolation** — One bad video can cascade failures. Process each video as an isolated unit with its own success/failure state and checkpointing.
6. **Keyword extraction confusing noise with signal** — Debate markers ("I think", "you know") dominate frequency counts. Use domain-specific stopwords, extract n-grams, validate against known debate subjects.
7. **Building dashboard before data** — Dashboard requirements change once you see real data. Build pipeline first, process 3-5 videos, then build the dashboard to match actual data shapes.

## Implications for Roadmap

### Phase 1: Foundation (Ingest + Transcription + Review)
**Rationale:** Validates the core premise. If WhisperX + constrained diarization + human review produces accurate speaker attribution, everything else follows. If it doesn't, the approach needs adjustment before building further.
**Delivers:** Working pipeline from YouTube URL to speaker-labeled, timestamped transcript with human review UI. 3-5 test videos processed end-to-end.
**Addresses:** Table-stakes features (ingestion, transcription, diarization, search, playback, corrections)
**Avoids:** Pitfalls 1 (diarization), 2 (audio quality), 3 (timestamp alignment), 4 (unreviewed transcripts), 7 (batch isolation), 8 (YouTube limits), 9 (schema evolution)

### Phase 2: Analysis (NLP Pipeline)
**Rationale:** Builds on verified, reviewed transcripts. Only enters NLP after humans have validated speaker attribution and transcript accuracy.
**Delivers:** Keyword extraction, topic extraction with refinement UI, stance/sentiment analysis, phrase frequency counting across all processed videos.
**Addresses:** Differentiators (topic extraction, frequency measurement, stance detection)
**Avoids:** Pitfalls 5 (keyword noise), 6 (generic sentiment)

### Phase 3: Dashboard (Public Web Interface)
**Rationale:** Built with real data in hand. Dashboard design informed by actual transcript shapes, topic distributions, and speaker patterns from Phases 1-2.
**Delivers:** Single-debate view, cross-debate analysis view, filter engine, search, public deployment. Pre-computed aggregations for performance.
**Addresses:** Table-stakes (public dashboard, filtering) and differentiators (cross-debate patterns, speaker comparison)
**Avoides:** Pitfall 10 (dashboard performance) through pre-computed aggregations and proper indexing

### Phase 4: Iterate (Polish + Advanced Features)
**Rationale:** Core functionality validated. Now add competitive differentiators and polish.
**Delivers:** Cross-debate topic matching, caller archetype tagging, share/embed links, Parker voice embedding for improved future diarization, export features.
**Addresses:** v1.x features (cross-debate matching, comparison cards, sharing)

### Phase 5: Advanced (v2 Features)
**Rationale:** Requires full corpus with consistent topic taxonomy — only possible after Phases 1-3 establish the data foundation.
**Delivers:** Argument evolution timeline, topic browser / argument graph, automated new video processing, API access.
**Addresses:** v2+ features (evolution timeline, argument graph, automation)

### Phase Ordering Rationale

- **Pipeline before dashboard:** Dashboard requirements are unknown until you see real data. Building pipeline first produces the actual data shapes that inform dashboard design. (Avoids Pitfall 7.)
- **Review before NLP:** All NLP analysis depends on accurate speaker attribution and transcript text. Human review gates prevent garbage-in-garbage-out. (Avoids Pitfall 4.)
- **Per-debate topics before cross-debate matching:** Cross-debate analysis requires a consistent topic taxonomy. You need per-debate topic extraction working first to build the taxonomy that enables cross-video matching.
- **Stance detection over sentiment:** Generic sentiment is meaningless in debate context. Building stance detection from the start avoids the "everything is negative" trap. (Avoids Pitfall 6.)

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** WhisperX configuration tuning for debate audio (model size, VAD sensitivity, alignment parameters). Parker voice embedding extraction approach.
- **Phase 2:** Topic taxonomy design — should this be seeded from debate titles/subjects, extracted from transcript content, or both? Stance classification schema needs domain-specific labeling.
- **Phase 3:** Cross-debate topic matching algorithm — embedding similarity threshold, manual verification workflow, taxonomy reconciliation between videos.
- **Phase 4:** Parker voice embedding persistence and reuse across videos for improved automated diarization.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | WhisperX + SQLite + Next.js is a proven pattern for ML-powered web apps. All components well-documented with active communities. |
| Features | HIGH | Feature landscape well-understood through competitor analysis. MVP scope is clear. No speculative features in Phase 1. |
| Architecture | HIGH | Batch pipeline with checkpointing is standard for this type of workload. Three-layer separation (pipeline, review, dashboard) is well-established. |
| Pitfalls | HIGH | Pitfalls identified from documented Whisper/diarization behaviors and domain experience. Mitigation strategies are concrete and testable. |

**Overall confidence:** HIGH

### Gaps to Address

- **WhisperX debate-specific tuning:** Default WhisperX parameters are not optimized for 1v1 debate audio with phone-quality callers. Need empirical testing on actual Parker videos to determine optimal model size, VAD sensitivity, and batch size.
- **Topic taxonomy design:** Unknown whether topics should be seeded from debate titles, extracted from transcript content, or use a hybrid approach. This is the core value prop and needs design work before Phase 2.
- **Parker voice embedding approach:** The idea of anchoring diarization to Parker's voice is sound, but the implementation (extracting a clean sample, computing embedding, using it across videos) needs validation.
- **GPU availability:** WhisperX requires CUDA for reasonable speed. If no GPU is available, need to fall back to Deepgram API ($0.01/min) — this changes the pipeline architecture.

## Sources

### Primary (HIGH confidence)
- WhisperX GitHub (v3.8.5) — combined Whisper + alignment + diarization pipeline
- pyannote-audio GitHub (v4.0.4) — speaker diarization, community model
- faster-whisper GitHub (v1.2.1) — CTranslate2-optimized Whisper
- yt-dlp GitHub (156k stars) — YouTube download
- OpenAI Whisper documentation — hallucination behavior, timestamp accuracy, model tradeoffs
- User-provided context — previous failed attempts with AI speaker parsing, 1v1 format, "best available" requirement

### Secondary (MEDIUM confidence)
- Deepgram pricing and API documentation — alternative transcription + diarization
- AssemblyAI product documentation — bundled transcription + diarization + sentiment
- Competitor analysis (Otter, Sonix, Gong) — feature landscape, pricing, competitive gaps
- BERTopic documentation — topic modeling approach for v2

---
*Research completed: 2026-04-09*
*Ready for roadmap: yes*
