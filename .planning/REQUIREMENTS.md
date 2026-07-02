# Requirements: Parker Debate Dashboard

**Defined:** 2026-04-09
**Core Value:** Topic mapping — understanding the full landscape of arguments on any given subject across all debates

## v1 Requirements

### Video Ingestion & Transcription

- [ ] **INGE-01**: User can submit a YouTube URL and get audio extracted
- [ ] **INGE-02**: System transcribes audio using best available method (WhisperX)
- [ ] **INGE-03**: System produces word-level timestamped transcript
- [ ] **INGE-04**: System identifies speakers via diarization constrained to 2 speakers (Parker vs. caller)

### Transcript & Review

- [x] **REVW-01**: User can view timestamped, speaker-labeled transcript
- [x] **REVW-02**: User can play video synced to transcript (click a line, jump to that moment)
- [x] **REVW-03**: User can correct speaker attribution on any segment
- [x] **REVW-04**: User can correct transcript text errors
- [x] **REVW-05**: Unreviewed transcripts are blocked from NLP analysis until approved

### NLP Analysis

- [x] **NLPP-01**: System extracts keywords and phrases per speaker per debate
- [x] **NLPP-02**: System extracts topics per debate (hybrid AI suggests, human refines)
- [x] **NLPP-03**: System classifies stance per speaker per topic (SUPPORTS/OPPOSES/QUALIFIED/DEFLECTS)
- [x] **NLPP-04**: System measures frequency of phrases, keywords, and ideas across debates
- [x] **NLPP-05**: System matches topics across debates for cross-debate comparison

### Dashboard & Visualization

- [ ] **DASH-01**: User can view single-debate deep dive (topics, positions, key quotes)
- [ ] **DASH-02**: User can view cross-debate pattern analysis (Parker argued X across N debates)
- [ ] **DASH-03**: User can compare speakers side-by-side on shared topics
- [ ] **DASH-04**: User can filter by entity (debater, topic, keyword), sentiment, time period, and metric
- [ ] **DASH-05**: User can search across all transcripts with time-coded results
- [ ] **DASH-06**: Dashboard is public-facing — anyone can browse without login

## v2 Requirements

### Advanced Features

- **ADVN-01**: Argument evolution timeline — how positions shift over time
- **ADVN-02**: Topic browser / argument graph — interactive visual map of the debate landscape
- **ADVN-03**: Caller archetype tagging — tag callers by worldview for cross-caller analysis
- **ADVN-04**: Share links and embeddable widgets — per-debate and per-topic shareable URLs
- **ADVN-05**: Automated new video processing — webhook-triggered pipeline for new uploads
- **ADVN-06**: API access — let researchers query structured debate data

## Out of Scope

| Feature | Reason |
|---------|--------|
| Debate scoring / "who won" | This is an analytical tool, not evaluative — not our place to judge winners |
| Real-time/streaming processing | Batch ingestion is sufficient for dozens of pre-recorded videos |
| Mobile app | Web-first, responsive is enough |
| Massive scale (thousands+) | Designed for dozens of videos, not enterprise scale |
| AI chatbot / "ask the debate" | RAG over debates risks hallucination and misattribution — too risky for an accuracy-focused tool |
| Full video editing suite | Descript/VEED already do this — analysis is our value prop |
| Automated fact-checking | Philosophical/political claims are unresolvable by AI — link to sources instead |
| Social features (comments, likes) | Moderation burden and toxicity risk — link to YouTube comments instead |
| Multi-language translation | Debate nuance is hard to translate, doubles corpus complexity |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGE-01 | Phase 1: Ingestion & Transcription | Pending |
| INGE-02 | Phase 1: Ingestion & Transcription | Pending |
| INGE-03 | Phase 1: Ingestion & Transcription | Pending |
| INGE-04 | Phase 1: Ingestion & Transcription | Pending |
| REVW-01 | Phase 2: Transcript Review | Complete |
| REVW-02 | Phase 2: Transcript Review | Complete |
| REVW-03 | Phase 2: Transcript Review | Complete |
| REVW-04 | Phase 2: Transcript Review | Complete |
| REVW-05 | Phase 2: Transcript Review | Complete |
| NLPP-01 | Phase 3: NLP Analysis | Complete |
| NLPP-02 | Phase 3: NLP Analysis | Complete |
| NLPP-03 | Phase 3: NLP Analysis | Complete |
| NLPP-04 | Phase 3: NLP Analysis | Complete |
| NLPP-05 | Phase 3: NLP Analysis | Complete |
| DASH-01 | Phase 4: Public Dashboard | Pending |
| DASH-02 | Phase 4: Public Dashboard | Pending |
| DASH-03 | Phase 4: Public Dashboard | Pending |
| DASH-04 | Phase 4: Public Dashboard | Pending |
| DASH-05 | Phase 4: Public Dashboard | Pending |
| DASH-06 | Phase 4: Public Dashboard | Pending |

**Coverage:**
- v1 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-09*
*Last updated: 2026-04-09 after initial definition*
