# Roadmap: Parker Debate Dashboard

**Created:** 2026-04-09
**Phases:** 4
**v1 Requirements:** 20 (all mapped)

## Phase Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Ingestion & Transcription Pipeline | 7/7 (manual validation pending) | INGE-01, INGE-02, INGE-03, INGE-04 | 4 |
| 2 | 3/3 | Complete   | 2026-04-12 | 5 |
| 3 | 4/4 | Complete   | 2026-04-12 | 5 |
| 4 | Public Dashboard | Filterable, searchable public web interface | DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06 | 5 |

## Phase 1: Ingestion & Transcription Pipeline

**Goal:** YouTube URL in, timestamped speaker-labeled transcript out.

**Requirements:** INGE-01, INGE-02, INGE-03, INGE-04

**Rationale:** This is the make-or-break phase. If WhisperX with constrained 2-speaker diarization produces usable output, everything else follows. If it doesn't, the approach needs adjustment before investing further. The project constraint that "previous AI speaker parsing produced poor results" means we must validate this foundation first.

**Delivers:**
- CLI/script to submit YouTube URL and trigger processing
- Audio download via yt-dlp
- WhisperX transcription with word-level timestamps
- 2-speaker diarization constrained to Parker vs. caller
- SQLite storage of segments with checkpointing
- Per-video isolation — one failure doesn't cascade

**Success Criteria:**
1. User submits a YouTube URL and receives a word-level timestamped transcript with speaker labels without manual intervention
2. System identifies exactly 2 speakers per video with segment-level speaker attribution
3. Processing a single video completes end-to-end (download through diarization) without error on at least 3 test videos
4. Failed videos are isolated — one video's failure does not prevent other videos from processing

**Research Flags:**
- WhisperX configuration tuning for debate audio (model size, VAD sensitivity, alignment parameters)
- Parker voice embedding extraction for improved diarization anchoring
- GPU availability check — fallback to Deepgram API if no CUDA

**Key Decisions:**
- WhisperX model size: balance speed vs. accuracy on phone-quality caller audio
- Diarization approach: pyannote with 2-speaker constraint vs. simple Parker-embedding-based classification

**Plans:** 7/7 plans executed

Plans:
- [x] 01-01-PLAN.md — Project scaffolding & configuration
- [x] 01-02-PLAN.md — Data models & database layer
- [x] 01-03-PLAN.md — Audio download module (yt-dlp)
- [x] 01-04-PLAN.md — WhisperX transcription & diarization pipeline
- [x] 01-05-PLAN.md — Speaker identification & utterance extraction
- [x] 01-06-PLAN.md — Pipeline orchestrator & CLI integration
- [x] 01-07-PLAN.md — Validation & end-to-end testing (manual verification pending)

---

## Phase 2: Transcript Review Interface

**Goal:** Human review gate ensures speaker attribution and transcript accuracy before any downstream analysis.

**Requirements:** REVW-01, REVW-02, REVW-03, REVW-04, REVW-05

**Rationale:** All NLP analysis depends on accurate speaker attribution and transcript text. A single transcription error ("don't" → "do") flips meaning. The user's stated pain point is unreliable AI speaker parsing — the review UI must be a first-class feature, not an afterthought. This phase gates Phase 3.

**Delivers:**
- Web interface for viewing timestamped, speaker-labeled transcripts
- YouTube embed synced to transcript — click a line, jump to that moment
- Speaker attribution correction on any segment
- Transcript text editing on any segment
- Approval workflow — unreviewed transcripts are blocked from NLP analysis
- Visual indicators for review status (unreviewed, in-progress, approved)

**Success Criteria:**
1. User can view a timestamped transcript alongside YouTube video playback synced to the current segment
2. User can correct speaker attribution on any segment and the correction persists across page loads
3. User can correct transcript text and the correction persists across page loads
4. Unreviewed transcripts are visibly flagged and cannot enter the NLP analysis pipeline
5. User can mark a transcript as "approved," making it available for Phase 3 processing

**Research Flags:**
- UX patterns for transcript editing — inline editing vs. side panel
- Batch correction workflows — correcting all segments for one speaker at once

**Key Decisions:**
- Review granularity: segment-level vs. utterance-level approval
- Partial review: allow approving some sections while flagging others

**Plans:** 3/3 plans complete

Plans:
- [ ] 02-01-PLAN.md — Web foundation: models, dependencies, FastAPI scaffold, CLI serve command
- [ ] 02-02-PLAN.md — Review page: transcript display, YouTube sync, inline editing
- [x] 02-03-PLAN.md — Video list, approval workflow, Phase 3 pipeline gate (completed 2026-04-12)

---

## Phase 3: NLP Analysis Pipeline

**Goal:** Extract structured analysis from reviewed transcripts — topics, keywords, stance, frequency.

**Requirements:** NLPP-01, NLPP-02, NLPP-03, NLPP-04, NLPP-05

**Rationale:** Only enters NLP after humans have validated speaker attribution and transcript accuracy. This prevents garbage-in-garbage-out. Stance detection (not generic sentiment) is critical — debate language is inherently combative, so polarity classification would tag everything "negative."

**Delivers:**
- Keyword and phrase extraction per speaker per debate
- Topic extraction with human refinement UI (AI suggests, human refines)
- Stance classification per speaker per topic (SUPPORTS / OPPOSES / QUALIFIED / DEFLECTS)
- Frequency measurement of phrases, keywords, and ideas across debates
- Cross-debate topic matching for comparison

**Success Criteria:**
1. System generates keyword and phrase lists per speaker per reviewed debate with domain-specific stopword filtering
2. System suggests topics per debate that a human can accept, reject, rename, or merge
3. System classifies stance per speaker per topic with confidence scores
4. System produces frequency counts for phrases and keywords across all approved debates
5. System identifies matching topics across different debates enabling cross-debate comparison

**Research Flags:**
- Topic taxonomy design — seeded from debate titles, extracted from content, or hybrid
- Stance classification schema — needs domain-specific labeling approach
- Cross-debate topic matching algorithm — embedding similarity threshold, manual verification workflow

**Key Decisions:**
- Topic ontology: flat list vs. hierarchical taxonomy
- Stance model: fine-tuned classifier vs. prompt-based LLM extraction
- Cross-debate matching: automatic with confidence threshold vs. manual linking

**Plans:** 4/4 plans complete

Plans:
- [ ] 03-01-PLAN.md — NLP foundation: data models, config, Pydantic schemas, stopwords
- [ ] 03-02-PLAN.md — LLM extraction pipeline: prompts, extractor, CLI analyze command
- [ ] 03-03-PLAN.md — NLP CRUD operations, frequency queries, topic embeddings
- [ ] 03-04-PLAN.md — Topic refinement UI and cross-debate matching UI

---

## Phase 4: Public Dashboard

**Goal:** Public-facing web interface for browsing, searching, and analyzing all processed debates.

**Requirements:** DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06

**Rationale:** Built with real data in hand. Dashboard design is informed by actual transcript shapes, topic distributions, and speaker patterns from Phases 1-3. Pre-computed aggregations ensure performance. SSR for SEO since this is a public tool.

**Delivers:**
- Single-debate deep dive view (topics, positions, key quotes, transcript)
- Cross-debate pattern analysis (e.g., "Parker argued X across N debates")
- Side-by-side speaker comparison on shared topics
- Filterable by entity (debater, topic, keyword), sentiment, time period, metric
- Full-text search across all transcripts with time-coded results
- Public deployment — no login required, SEO-optimized

**Success Criteria:**
1. Any visitor can browse the dashboard and view debate analysis without creating an account or logging in
2. Single-debate view displays topics, speaker positions, key quotes, and full searchable transcript
3. Cross-debate view shows patterns like "Parker argued X across N debates" with drill-down capability
4. Filtering by debater, topic, keyword, sentiment/stance, time period, and metric returns accurate results
5. Full-text search across all transcripts returns time-coded, speaker-labeled results with video jump links

**Research Flags:**
- Dashboard performance with pre-computed aggregations
- SSR vs. SSG strategy for infrequently-updated content
- Chart library selection for stance/topic visualization

**Key Decisions:**
- Deployment target: Vercel, Railway, or self-hosted
- Data update strategy: rebuild on change vs. incremental updates
- Chart/visualization approach for topic maps and stance comparisons

---

## Phase Dependencies

```
Phase 1 → Phase 2 → Phase 3 → Phase 4
  (Ingest)   (Review)   (NLP)    (Dashboard)
```

- Phase 1 must complete before Phase 2 (need transcripts to review)
- Phase 2 must complete before Phase 3 (need reviewed transcripts for NLP)
- Phase 3 must complete before Phase 4 (need analyzed data for dashboard)
- Within each phase, parallel work is possible on independent components

## Requirement Coverage

| Phase | Requirements | Count |
|-------|-------------|-------|
| Phase 1: Ingestion & Transcription | INGE-01, INGE-02, INGE-03, INGE-04 | 4 |
| Phase 2: Transcript Review | REVW-01, REVW-02, REVW-03, REVW-04, REVW-05 | 5 |
| Phase 3: NLP Analysis | NLPP-01, NLPP-02, NLPP-03, NLPP-04, NLPP-05 | 5 |
| Phase 4: Public Dashboard | DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06 | 6 |
| **Total** | | **20** |

**Coverage:** 20/20 v1 requirements mapped (100%)

---
*Created: 2026-04-09*
