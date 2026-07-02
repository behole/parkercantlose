# Feature Research

**Domain:** YouTube debate transcription and analysis
**Researched:** 2026-04-09
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Video-to-text transcription | Core function — without it nothing else works | LOW | YouTube provides auto-captions as baseline. Deepgram/AssemblyAI for higher accuracy. Multiple providers available. |
| Speaker identification (diarization) | Users need to know who said what — this is a debate tool | MEDIUM | AssemblyAI, Deepgram, and Sonix all offer this. Accuracy for 2-speaker format is good. Parker's voice is consistent across videos — can train/seed. |
| Timestamped transcript | Navigation, citation, and verification require time alignment | LOW | Standard output from all transcription APIs. Word-level timestamps available from AssemblyAI/Deepgram. |
| Searchable transcript | Users expect to find specific quotes or moments | LOW | Full-text search is trivial. Time-coded results slightly more effort. |
| Basic filtering (by video, speaker) | Dashboard users expect Excel-level filtering at minimum | MEDIUM | Standard UI pattern. Filter by video, speaker, date range. |
| Clean web interface | Users won't install software for a public-facing tool | MEDIUM | React/Next.js dashboard. Responsive, accessible. |
| Transcript accuracy display | Users need confidence in what they're reading | LOW | Show confidence scores, highlight uncertain segments, allow user corrections. |
| Video playback synced to transcript | Users need to verify quotes against original audio | MEDIUM | YouTube embed API with time-sync. Standard pattern (like Descript, Otter). |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Topic/idea extraction with ontology** | The CORE value prop — mapping the full argument landscape on any subject | HIGH | Hybrid AI extraction + human curation. Build a taxonomy of topics, sub-topics, arguments. This is what makes this tool unique vs generic transcription. |
| **Side-by-side speaker comparison per topic** | Instantly see where Parker and each caller stand on each issue | MEDIUM | Structured as: Topic > Speaker A position vs Speaker B position. Sentiment + key quotes. Visual comparison cards. |
| **Cross-debate pattern analysis** | "Parker has argued X about topic Y across 12 debates" — the 10,000ft view | HIGH | Requires consistent topic taxonomy across all videos. Aggregate frequency, stance evolution, argument patterns. This is the hardest technical challenge. |
| **Sentiment and stance analysis per speaker per topic** | Not just "positive/negative" but "agrees/disagrees/conditional/neutral" on each topic | MEDIUM | Custom stance classification (not generic sentiment). Map to a debate-specific schema: SUPPORTS, OPPOSES, QUALIFIED, DEFLECTS, CHALLENGES. |
| **Frequency measurement (phrases, keywords, arguments)** | "Parker uses this phrase 47 times across 30 debates" — rhetorical pattern detection | MEDIUM | n-gram frequency across corpus. Track argument templates, not just words. Requires argument-level parsing. |
| **Topic browser / argument map** | Visual navigation of the debate landscape — click a topic, see every debate where it came up | HIGH | Interactive graph or tree view. Topics → subtopics → arguments → evidence. Alternative: faceted search UI. |
| **Human-in-the-loop correction pipeline** | User has had bad AI speaker parsing — give them tools to fix and improve | MEDIUM | Correction UI for speaker labels, topic tags, transcript errors. Corrections feed back into accuracy. Essential for trust. |
| **Embeddable/shareable analysis** | Public-facing tool needs shareable links, embeddable widgets, social cards | LOW | Per-debate share links. Per-topic summary cards. OG meta for social previews. |
| **Argument evolution timeline** | Show how Parker's (or a caller type's) position on a topic has shifted over time | HIGH | Requires date-ordered corpus + consistent topic tagging. Visual timeline per topic. |
| **Caller archetype tagging** | Tag callers by worldview/position type to find patterns across similar callers | MEDIUM | Manual or AI-assisted tagging: "atheist", "Christian", "libertarian", etc. Enables cross-caller pattern analysis beyond individual. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time transcription of live streams | Users want instant analysis | Requires streaming infrastructure, WebSocket audio capture, real-time diarization — massive complexity for MVP with dozens of pre-recorded videos | Batch processing with quick turnaround. Add real-time later if live debates become a use case. |
| Full video editing suite | "Can you clip and remix arguments?" | Descript/VEED already do this. Building a video editor is a company-sized effort that distracts from the analysis value prop | YouTube clip links with time ranges. Export transcript excerpts. Link to original video moments. |
| AI-generated debate summaries | "Give me the TLDR of this 2-hour debate" | Generic summarization is table stakes (Sonix, Otter all do it). LLM summaries can hallucinate positions. For a tool about accuracy, this is risky | Structured extraction: key topics, positions, quotes. Let users draw conclusions. Offer summary as opt-in, clearly labeled. |
| Chatbot / "ask the debate" interface | "Chat with Parker's arguments" | RAG over debates is technically feasible but risks hallucination and misattribution. Users may treat it as authoritative when it's not. | Structured browsing + search. If chat is added, show sources for every claim and mark confidence. |
| Social features (comments, likes) | "Community debate discussion" | Moderation burden, toxicity risk, scope creep away from analysis tool | Link to original YouTube comments. Focus on analysis, not discussion. |
| Multi-language translation | Broad accessibility | Translation quality varies, debate nuance is hard to translate, doubles corpus complexity | English-only for MVP. Translation as future feature if audience demands it. |
| Automated fact-checking | "Rate the accuracy of claims" | Requires integration with knowledge bases, claim extraction is unreliable, political/philosophical claims are unresolvable by AI | Link claims to external sources. Let users verify. Don't position as truth arbiter. |

## Feature Dependencies

```
YouTube Video Ingestion
├── Audio Extraction
│   └── Transcription (STT)
│       ├── Speaker Diarization
│       │   ├── Speaker Verification (Parker vs Caller)
│       │   └── Human Correction Pipeline
│       ├── Timestamped Transcript
│       │   ├── Full-Text Search
│       │   └── Video Sync Playback
│       └── Topic/Keyword Extraction
│           ├── Argument Parsing
│           │   ├── Stance Classification
│           │   └── Sentiment Analysis
│           ├── Cross-Video Topic Matching
│           │   ├── Frequency Analysis
│           │   ├── Speaker Comparison (per topic)
│           │   └── Argument Evolution Timeline
│           └── Caller Archetype Tagging
├── Public Dashboard
│   ├── Filter/Search UI
│   ├── Topic Browser
│   ├── Debate Detail View
│   └── Share/Embed
└── Data Pipeline (Orchestration)
    └── Storage & Indexing
```

### Dependency Notes

- **Topic extraction requires clean transcription + speaker diarization:** Garbage in, garbage out. Speaker-labeled, timestamped transcripts are the foundation.
- **Cross-debate pattern analysis requires consistent topic taxonomy:** Topics extracted from video 1 must map to topics from video 30. This is the hardest dependency — needs either a shared embedding space or a curated taxonomy (or both).
- **Stance classification requires topic extraction + speaker diarization:** You can't classify a speaker's stance on a topic without knowing who spoke and what the topic is.
- **Human correction pipeline should be built early:** The user has flagged speaker parsing as a pain point. Building correction tools early builds trust and creates training data.
- **Public dashboard requires all downstream analysis:** The dashboard is the presentation layer — it can't be built until the data pipeline produces structured output.
- **Argument evolution timeline requires cross-video topic matching + date ordering:** The most complex feature, depends on everything else working. Defer to v2.
- **Frequency analysis requires cross-video topic matching:** Can't count "how many times Parker argued X" without consistent topic mapping across the corpus.

## MVP Definition

### Launch With (v1)

- [ ] **YouTube video ingestion pipeline** — download audio, extract transcript, diarize speakers. Batch process for initial corpus (~dozens of videos).
- [ ] **Speaker diarization with Parker identification** — 2-speaker format makes this tractable. Seed with Parker's known voice. Allow manual correction.
- [ ] **Timestamped, speaker-labeled transcript** — the foundational data structure. Store per-utterance with speaker, timestamp, confidence.
- [ ] **Full-text search with filters** — search across all transcripts. Filter by video, speaker, date range.
- [ ] **Video-synced transcript viewer** — YouTube embed + scroll-synced transcript. Click a line, jump to that moment.
- [ ] **Keyword/phrase frequency dashboard** — top terms per speaker, per video, across corpus. Simple bar charts and word clouds.
- [ ] **Basic topic extraction** — AI-extracted topics per debate, with human review/correction interface.
- [ ] **Per-debate detail view** — topics discussed, speaker positions, key quotes, sentiment indicators.
- [ ] **Public web interface** — clean, responsive dashboard. No login required for viewing.
- [ ] **Human correction tools** — fix speaker labels, correct transcript errors, edit topic tags.

### Add After Validation (v1.x)

- [ ] **Cross-debate topic matching** — connect the same topic across multiple videos. Requires embedding-based similarity + manual verification.
- [ ] **Side-by-side speaker comparison** — per-topic comparison cards: Parker's position vs caller's position.
- [ ] **Caller archetype tagging** — tag callers by worldview/position type for cross-caller analysis.
- [ ] **Argument frequency analysis** — "Parker makes this argument N times" across the corpus.
- [ ] **Share links and embeddable widgets** — per-debate and per-topic shareable URLs.

### Future Consideration (v2+)

- [ ] **Argument evolution timeline** — how positions shift over time. Requires full corpus analysis + consistent taxonomy.
- [ ] **Topic browser / argument graph** — interactive visual map of the debate landscape.
- [ ] **Stance classification schema** — SUPPORTS, OPPOSES, QUALIFIED, DEFLECTS, CHALLENGES per topic per speaker.
- [ ] **Automated new video processing** — webhook-triggered pipeline when new Parker debate videos are published.
- [ ] **API access** — let researchers query the structured debate data.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Video ingestion + transcription | CRITICAL | LOW | P1 |
| Speaker diarization | CRITICAL | MEDIUM | P1 |
| Timestamped transcript display | HIGH | LOW | P1 |
| Video-synced playback | HIGH | MEDIUM | P1 |
| Full-text search + filters | HIGH | LOW | P1 |
| Human correction pipeline | HIGH | MEDIUM | P1 |
| Public web dashboard | HIGH | MEDIUM | P1 |
| Keyword/phrase frequency | MEDIUM | LOW | P1 |
| Topic extraction (per-debate) | HIGH | HIGH | P1 |
| Cross-debate topic matching | HIGH | HIGH | P2 |
| Speaker comparison (per topic) | HIGH | MEDIUM | P2 |
| Stance/sentiment analysis | MEDIUM | MEDIUM | P2 |
| Caller archetype tagging | MEDIUM | MEDIUM | P2 |
| Share/embed links | MEDIUM | LOW | P2 |
| Argument frequency (cross-corpus) | HIGH | HIGH | P2 |
| Argument evolution timeline | HIGH | HIGH | P3 |
| Topic browser / argument graph | MEDIUM | HIGH | P3 |
| Automated new video processing | MEDIUM | MEDIUM | P3 |
| API access | LOW | MEDIUM | P3 |

## Competitor Feature Analysis

| Feature | Otter.ai | Sonix | AssemblyAI | Gong | Our Approach |
|---------|----------|-------|------------|------|--------------|
| **Transcription** | Real-time + batch, good accuracy | Batch, 99% claimed, 53+ languages | API-only, best-in-class accuracy, developer-focused | Call recording transcription | YouTube audio extraction → AssemblyAI/Deepgram API. Batch processing. |
| **Speaker diarization** | Basic (auto-identify speakers) | Speaker labeling with manual correction | Advanced diarization, speaker roles via prompting | N/A (sales calls, usually 2 speakers) | 2-speaker format is ideal. Seed Parker's voice. Manual correction UI for trust. |
| **Topic extraction** | Summary keywords, word clouds | AI topic detection, categorization | Sentiment, chapters, PII redaction, custom categories | AI-driven deal topics, objection tracking | Custom debate-topic taxonomy. Hybrid AI + human curation. Cross-video matching. |
| **Sentiment analysis** | Basic summary keywords | Sentiment analysis per segment | Built-in sentiment API | Conversation intelligence, deal risk signals | Debate-specific stance schema (not generic positive/negative). Per speaker per topic. |
| **Search** | Keyword search by speaker, date | Full-text search across transcripts | API returns, no UI | Search across all calls | Full-text + semantic search across corpus. Filter by speaker, topic, stance, date. |
| **Comparison/analytics** | Usage analytics, word clouds | Folders, tags, multi-file organization | API-only, no UI | Extensive deal analytics, coaching insights | Side-by-side speaker comparison per topic. Cross-debate pattern aggregation. Unique to debate format. |
| **Collaboration** | Groups, comments, sharing | Team collaboration, comments, assignments | N/A (API) | Team coaching, deal rooms | Public read-only. Correction interface for trusted users. |
| **Integrations** | Zoom, Teams, Meet, Dropbox | Zoom, Dropbox, Adobe Premiere, Zapier | REST API, SDKs | Salesforce, Zoom, Teams, 250+ integrations | YouTube API for ingestion. REST API for future extensibility. Minimal integrations for MVP. |
| **Price model** | Freemium ($10-20/mo) | Per-hour ($10-22/mo) | Pay-per-second of audio | Enterprise ($100+/user/mo) | Open source / self-hosted for core. Possible freemium if hosted. |

### Competitive Gaps We Fill

1. **No one does debate-specific analysis.** Otter/Sonix/Gong are meeting/call tools. None extract argument structure, track positions across conversations, or map a speaker's rhetorical landscape.

2. **Cross-conversation topic matching is rare.** Gong does it for sales deals. We do it for philosophical/political arguments. The domain is different but the pattern is proven.

3. **Speaker diarization with correction.** Most tools offer diarization but poor correction UX. Given the user's bad experience, investing here builds trust and becomes a moat.

4. **Public-facing analysis dashboard.** Most transcription tools are private/workspace tools. A public, filterable debate analysis dashboard is a unique positioning.

## Sources

- AssemblyAI product page — speech-to-text, diarization, sentiment, speaker roles via prompting, streaming STT
- Deepgram — STT/TTS/voice agent APIs, batch and real-time, self-hosted option
- Sonix — transcription + translation + AI analysis (topics, sentiment), 99% accuracy claim, collaborative editing
- Otter.ai — meeting transcription, speaker identification, keyword search, summary keywords
- HappyScribe — hybrid AI + human transcription, subtitle editor, glossary support, team collaboration
- Gong — conversation intelligence for sales, topic extraction, deal analytics, coaching insights
- Symbl.ai (now Invoca) — conversation intelligence APIs, sentiment, trackers, call scoring
- Descript — transcription-powered video editing, speaker detection, text-based editing
- VEED — browser-based transcription + video editing, subtitle generation, translation

## Technical Notes on Speaker Diarization

The user flagged bad AI speaker parsing as a concern. Key considerations:

- **2-speaker format is the best case for diarization.** Most APIs achieve 90%+ accuracy with 2 speakers.
- **Parker appears in every video.** His voice can be enrolled as a known speaker, dramatically improving accuracy.
- **YouTube auto-captions don't include speaker labels.** Must use audio-based diarization, not caption parsing.
- **Recommendation:** Use AssemblyAI (supports speaker roles via prompting: `[Speaker:HOST]` / `[Speaker:CALLER]`) or Deepgram (supports speaker enrollment). Build a correction UI as a safety net.

---
*Feature research for: YouTube debate transcription and analysis*
*Researched: 2026-04-09*
