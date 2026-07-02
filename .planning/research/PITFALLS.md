# Pitfalls Research

**Domain:** YouTube debate transcription and analysis
**Researched:** 2026-04-09
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Treating Diarization as a Solved Problem
**What goes wrong:** Assuming an off-the-shelf diarization API (pyannote, Deepgram, AssemblyAI) will reliably distinguish Parker from callers. Results come back with speaker swaps, merged segments, or phantom speakers. The entire downstream analysis — sentiment, argument mapping, topic attribution — becomes unreliable because you're analyzing the wrong speaker's words.
**Why it happens:** Speaker diarization benchmarks look impressive (10-15% DER) but those are measured on clean meeting audio, not compressed YouTube audio with variable call-in phone quality. The caller is often on a phone line with compression artifacts, background noise, and low bitrate. Parker may be on a studio mic. Voice characteristics differ wildly between callers across videos, preventing any speaker-profile persistence. The user has explicitly noted previous AI parsing attempts produced "terrible results."
**How to avoid:**
- Constrain diarization to exactly 2 speakers (`num_speakers=2`) — the format is always 1v1
- Use Parker's voice as a reference embedding: extract a clean sample from one video, compute an embedding (pyannote supports this), and anchor "Speaker A" to Parker. This turns an unsupervised clustering problem into a supervised classification one
- Post-process with heuristic validation: segment lengths should alternate (conversational), rapid speaker flips (< 0.5s) are likely errors, one speaker should appear consistently across all videos (Parker)
- Build the human review interface BEFORE the automated pipeline — treat AI diarization as a first pass that reduces manual work by ~70%, not as the final answer
**Warning signs:**
- Diarization produces 3+ speakers on a 2-person video
- Speaker labels swap mid-sentence or within a single turn
- Parker's segments are inconsistent in length or frequency compared to what you'd expect from a host
- Testing on one video gives acceptable results but a second video falls apart (overfitting to audio conditions)
**Phase to address:** Phase 1 (transcription pipeline) — must be solved before any NLP work begins

### Pitfall 2: Ignoring YouTube Audio Quality Variation
**What goes wrong:** Transcription quality varies wildly between videos because YouTube audio compression, call-in phone quality, background music, and audio normalization differ per video. You build and test on a "good" video, then batch-process and discover 30% of transcripts are garbage — filled with hallucinated text, dropped sentences, or merged words.
**Why it happens:** OpenAI Whisper is known to hallucinate on low-quality audio, especially when there's silence or music. It may "invent" text during dead air. Phone-quality caller audio has a narrow frequency band (300Hz-3.4kHz) that degrades model performance. YouTube's auto-normalization can clip or compress dynamic range. Each video is essentially a different acoustic environment.
**How to avoid:**
- Download YouTube audio at highest available quality (usually opus 160kbps or m4a 128kbps), never use low-bitrate streams
- Pre-process audio: normalize volume, apply noise reduction (rnnoise or similar), split on long silences to prevent Whisper hallucination during dead air
- Use Whisper's `turbo` or `large-v3` model — smaller models degrade significantly on noisy audio
- Set Whisper's `condition_on_previous_text=False` to prevent cascading hallucinations
- Implement per-segment confidence scoring and flag low-confidence segments for human review
- Test on the WORST quality video first, not the best
**Warning signs:**
- Transcripts contain repeated phrases or text that doesn't match the video
- Long silence gaps produce transcribed text (hallucination)
- Word-level confidence scores below 0.7 on significant portions
- Transcription works on studio-quality audio but fails on phone-call segments
**Phase to address:** Phase 1 (transcription pipeline) — audio pre-processing is foundational

### Pitfall 3: Whisper Timestamp Misalignment with Diarization
**What goes wrong:** Whisper produces word-level timestamps with some drift. Pyannote produces speaker segments with its own timestamps. When you align these two outputs, words get assigned to the wrong speaker because the timestamps don't perfectly overlap. A 200ms offset can flip an entire sentence to the wrong speaker.
**Why it happens:** Whisper's timestamps are approximate — it processes audio in 30-second windows and interpolates word positions. Pyannote detects speaker change points independently. Neither system is aware of the other's segmentation. For conversational speech with rapid turn-taking (common in debates), a few hundred milliseconds of offset means the difference between correct and incorrect attribution.
**How to avoid:**
- Use an integrated transcription+diarization service (Deepgram Nova-3 with `diarize=true`, or AssemblyAI with speaker labels) instead of running Whisper and pyannote separately — these handle alignment internally
- If running separately, align using a custom algorithm: map each Whisper word to the pyannote segment with the highest temporal overlap, but add conflict resolution for edge cases (word spans a speaker boundary)
- Validate alignment by checking that segment transitions correlate with expected turn-taking patterns
- Generate a "confidence heatmap" showing which speaker assignments are near segment boundaries (low confidence) vs. deep within segments (high confidence)
**Warning signs:**
- Same speaker appears to talk for 5+ minutes without a break (missed handoff)
- Short interjections ("yeah", "right") are assigned to the wrong speaker
- Speaker changes happen mid-sentence rather than between sentences
- Manual spot-check finds attribution errors concentrated near turn boundaries
**Phase to address:** Phase 1 (transcription pipeline) — alignment logic is part of core data processing

### Pitfall 4: Building NLP Analysis on Unreviewed Transcripts
**What goes wrong:** You build keyword extraction, sentiment analysis, and topic modeling on raw transcripts. Then you discover transcription errors that completely change meaning — "I don't believe in God" transcribed as "I do believe in God" — and every NLP result derived from that segment is wrong. You have to re-run the entire pipeline.
**Why it happens:** The temptation is to build the cool dashboard features first. But transcription errors propagate multiplicatively through NLP pipelines. A single missed negation flips sentiment. A misheard word creates a phantom keyword. Topic modeling clusters around errors. The user's requirement for "best transcription quality" exists precisely because downstream analysis depends on it.
**How to avoid:**
- Enforce a strict pipeline order: Transcribe → Diarize → Human Review → THEN NLP
- Make human review a gate, not an optional step — no transcript enters the NLP pipeline without "reviewed" status
- Store transcript corrections and track which segments were modified (this measures diarization/transcription quality over time)
- Build the review interface as Phase 1 deliverable, not Phase 3
- Consider versioning: raw transcript v1 → corrected transcript v2 → NLP outputs derived from v2
**Warning signs:**
- NLP features are being developed while transcription accuracy is still being measured
- No human review interface exists but dashboard features do
- Keyword extraction surfaces words that don't actually appear in the audio
- Sentiment analysis contradicts what a human listener would assess
**Phase to address:** Phase 1 (human review interface) must be complete before Phase 2 (NLP pipeline) begins

### Pitfall 5: Keyword Extraction That Confuses Noise with Signal
**What goes wrong:** You run TF-IDF or keyword extraction and get a dashboard full of filler words, debate-specific phrases ("I think", "you know", "let me say"), and common argumentative constructions. The keywords don't tell you anything about the TOPIC of the debate — they tell you it's a debate. Users can't filter meaningfully.
**Why it happens:** Debate language has strong domain-specific patterns: hedging phrases, rhetorical questions, agreement/disagreement markers, transition phrases. These dominate frequency counts. Single-word keyword extraction misses multi-word concepts ("free will", "moral responsibility", "burden of proof"). Topic modeling with too few or too many topics produces either trivially broad or uselessly narrow clusters.
**How to avoid:**
- Use a domain-specific stopword list that includes debate discourse markers in addition to standard English stopwords
- Extract n-grams (2-4 word phrases) alongside single keywords — debates revolve around concepts, not individual words
- Use KeyBERT or similar embedding-based extraction that captures semantic importance, not just frequency
- Let the "defined subjects" per debate seed the topic taxonomy rather than discovering topics purely from text
- Validate keyword quality by checking: would a human agree these keywords represent the debate topic?
**Warning signs:**
- Top keywords across all debates look nearly identical (debate markers, not topic markers)
- Keywords are mostly single common words ("thing", "point", "argument")
- Topic clusters don't correspond to the known debate subjects
- Filtering by keyword returns too many or too few results
**Phase to address:** Phase 2 (NLP pipeline) — extraction design should be validated against known debate topics before building dashboard features

### Pitfall 6: Sentiment Analysis That Doesn't Understand Debate Context
**What goes wrong:** Standard sentiment analysis tags debate arguments as "negative" because debaters use combative language, disagreement phrases, and critical tones. It tags sarcasm as positive. It can't distinguish "I disagree with your position" (negative sentiment about the ARGUMENT) from "This is a terrible moral framework" (negative sentiment about the TOPIC). The sentiment dashboard becomes meaningless noise.
**Why it happens:** General-purpose sentiment models (VADER, TextBlob, even transformer-based) are trained on product reviews and social media — not adversarial discourse. In debates, "negative" language is the norm and doesn't indicate negative sentiment toward the topic. Sarcasm is common. Nuanced philosophical arguments use hedging language that confuses polarity classifiers. The concept of "sentiment" in a debate context is fundamentally different from sentiment in a review context.
**How to avoid:**
- Don't use standard sentiment analysis. Instead, build a position-detection system: for each topic, classify each speaker's stance (support/oppose/neutral/qualified)
- If using sentiment, fine-tune on debate-domain data or at minimum validate against human-labeled segments
- Track sentiment RELATIVE TO each speaker's baseline, not as absolute scores — Parker may have an assertive baseline that reads as "negative" to a generic model
- Report stance (pro/con on an argument) alongside tone (hostile/friendly/neutral) as separate dimensions
- Consider using LLM-based classification (GPT-4, Claude) for stance detection on reviewed transcript segments — these understand context better than traditional sentiment models
**Warning signs:**
- All debates show predominantly "negative" sentiment
- Sarcasm is classified as positive
- Sentiment scores don't change meaningfully across different debate topics
- Two speakers arguing the same side of an issue show different sentiment due to speaking style
**Phase to address:** Phase 2 (NLP pipeline) — sentiment/stance model should be validated on a manually labeled test set

### Pitfall 7: Batch Processing Without Per-Video Validation
**What goes wrong:** You process 40 videos in a batch, discover video #3 had a technical issue (corrupted audio, wrong video format, age-restricted unavailable), and the pipeline either crashes silently or produces garbage for that video and all subsequent ones. You have 37 good transcripts and 3 broken ones but don't know which are broken without manually checking all 40.
**Why it happens:** Batch processing is efficient but assumes uniform input. YouTube videos vary in availability (deleted, private, age-restricted, region-locked), audio format, duration, and quality. A single failure can cascade if the pipeline doesn't isolate processing per video. Error handling that works for 1 video (throw exception, debug) doesn't work for 50 (silent failures accumulate).
**How to avoid:**
- Process each video as an isolated unit with its own success/failure state — one video's failure must never affect another's processing
- Implement idempotent processing: re-running the pipeline on an already-processed video should detect and skip (or overwrite with version control), not duplicate
- Store per-video processing metadata: download status, audio quality metrics, transcription confidence, diarization quality score, human review status
- Build a processing dashboard that shows status of all videos: not started / downloading / transcribing / diarizing / needs review / reviewed / ready
- Add circuit breakers: if transcription confidence drops below threshold for a video, pause and flag for manual inspection rather than continuing with garbage data
**Warning signs:**
- Pipeline crashes mid-batch and you don't know which videos succeeded
- No way to resume processing from the point of failure
- Processing metadata isn't stored — can't tell which videos had issues without re-running
- Running the pipeline twice produces duplicate records
**Phase to address:** Phase 1 (pipeline infrastructure) — batch processing architecture is foundational

### Pitfall 8: YouTube API Quota and Rate Limiting
**What goes wrong:** You hit YouTube Data API v3 quota limits (default: 10,000 units/day, video download costs 1-100 units each) or yt-dlp gets rate-limited during batch downloads. Processing stalls mid-batch. You don't handle 429 responses, and the download logic either retries infinitely or gives up permanently.
**Why it happens:** YouTube's API quota is surprisingly restrictive for batch operations. Downloading video metadata + captions + audio for 50 videos can exhaust daily quota. yt-dlp can trigger bot detection if called too rapidly. Age-restricted or members-only content requires authentication. The YouTube API terms of service restrict automated downloading, creating legal risk if the tool is distributed publicly.
**How to avoid:**
- Use yt-dlp for audio download (not the YouTube Data API) — it's more resilient to rate limiting
- Implement exponential backoff with jitter for any API calls
- Cache downloaded audio locally — never re-download
- Separate metadata fetching from audio downloading — fetch all metadata first, then batch download audio
- Monitor quota usage and plan batch sizes accordingly
- Store video metadata (title, description, duration, upload date) alongside transcripts — you'll need it for the dashboard
**Warning signs:**
- Downloads start failing after the 20th video
- HTTP 429 responses in logs
- Processing time varies wildly due to retries
- No local cache means re-processing requires re-downloading
**Phase to address:** Phase 1 (pipeline infrastructure) — download architecture should be designed for batch reliability

### Pitfall 9: Storing Everything in One Big JSON/Database Without Schema Evolution
**What goes wrong:** You start with a simple schema: video → transcript → speakers. Then you add keywords, topics, sentiment, corrections, versions. Each addition mutates the schema. Six months in, you have 15 different transcript "formats" depending on when they were processed, and you can't re-run analysis because the schema is inconsistent. Migrating means re-processing everything.
**Why it happens:** Greenfield projects often start with the simplest storage (JSON files or a single database table) and accumulate fields organically. There's no migration strategy because there's nothing to migrate from initially. Each new NLP feature adds columns or nested objects. By the time you realize you need schema management, you have production data in multiple incompatible formats.
**How to avoid:**
- Design the schema upfront with versioning in mind: each transcript record gets a `schema_version` field
- Use a proper database (PostgreSQL or SQLite at minimum) instead of JSON files — schema enforcement prevents drift
- Separate raw data (immutable: audio, raw transcript) from derived data (mutable: keywords, sentiment, corrections)
- Plan for re-processing: store enough metadata to re-run any NLP step from scratch using only the raw data
- Write migration scripts as you evolve the schema, even early on
**Warning signs:**
- Adding a new feature requires updating all existing records
- Different code paths handle "old format" and "new format" transcripts
- No way to tell which version of the pipeline produced a given result
- Re-processing requires deleting and re-creating data
**Phase to address:** Phase 1 (data model) — schema design before any data is processed

### Pitfall 10: Dashboard Performance with Growing Data
**What goes wrong:** The dashboard is fast with 5 videos but becomes sluggish at 30 and unusable at 50. Cross-debate analysis queries take 10+ seconds. Full-text search across all transcripts times out. The filtering interface makes a request for every keystroke.
**Why it happens:** Full-text search across transcripts, keyword filtering, topic aggregation, and cross-debate comparisons are computationally expensive. Doing this with naive database queries (LIKE %term%, JOINs across many tables, no indices) doesn't scale. Client-side filtering of large datasets causes UI jank. The "dozens of videos" constraint lulls you into thinking performance doesn't matter.
**How to avoid:**
- Use full-text search (PostgreSQL FTS, SQLite FTS5, or Meilisearch/Elasticsearch) from the start — not LIKE queries
- Pre-compute aggregations (keyword frequencies, topic distributions, sentiment summaries) during processing, not at query time
- Index the query patterns the dashboard actually uses (topic, speaker, keyword, date range)
- Implement server-side pagination and filtering, never send the full dataset to the client
- For cross-debate analysis, pre-compute the comparison matrices during pipeline processing
**Warning signs:**
- Dashboard loads in < 1s with 5 videos but > 5s with 20
- Search queries use LIKE or unindexed regex
- Client receives the full dataset and filters in JavaScript
- Cross-debate comparison requires scanning every transcript
**Phase to address:** Phase 3 (dashboard) — but data model in Phase 1 should anticipate query patterns

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip human review, use raw AI diarization | Ship faster, process all videos quickly | Every analysis built on wrong speaker data; must reprocess everything | Never — this is the user's stated pain point |
| Store transcripts as flat text files | Simple, no database setup | Can't query, filter, or aggregate; must load all files for any analysis | Prototype only (first 2-3 videos) |
| Use generic sentiment model | Quick integration, no training needed | Meaningless sentiment scores for debate context | Acceptable for MVP if labeled "experimental" and replaced in Phase 2 |
| Process videos sequentially, no error handling | Simpler code | One failure kills the batch; no resume capability | Never for batch — isolate per-video from day one |
| Single-word keyword extraction only | Easy to implement | Misses multi-word concepts that debates revolve around | Acceptable if n-gram extraction is planned for same phase |
| No audio pre-processing | Faster pipeline | Hallucinations on bad audio; Whisper degrades on phone-quality caller audio | Never — pre-processing is cheap compared to re-transcription |
| Hard-code YouTube URLs | Quick start | Can't handle video deletions, URL changes, or private videos | Acceptable for initial testing only |
| Skip confidence scoring on transcription | Simpler pipeline | No way to prioritize human review — reviewer wastes time on good transcripts | Acceptable only if ALL transcripts are manually reviewed |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| yt-dlp audio download | Downloading mp3 (lossy re-encode) instead of original format | Download best available audio (usually opus/m4a), keep original format |
| Whisper transcription | Using default settings without `condition_on_previous_text=False` | Disable condition_on_previous_text to prevent hallucination cascading; use `word_timestamps=True` for alignment |
| Pyannote diarization | Not setting `num_speakers=2` when format is always 2-person | Always set `num_speakers=2` — prevents phantom speakers and improves accuracy |
| Deepgram diarization | Enabling diarize without utterances | Use `diarize=true&utterances=true&punctuate=true` together for best results |
| Whisper + Pyannote alignment | Naively matching by timestamp overlap | Implement overlap-weighted alignment with conflict resolution at speaker boundaries |
| NLP keyword extraction | Using standard English stopwords only | Add debate-domain stopwords: "think", "mean", "say", "argue", "point", "thing" |
| YouTube Data API | Using API for audio download | Use yt-dlp for downloads; YouTube API only for metadata if needed |
| Database + search | Using LIKE queries for transcript search | Use FTS5 (SQLite) or pg_trgm/gin (PostgreSQL) for full-text search |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Processing 50 videos without checkpointing | Pipeline crash at video #37 means re-running all 37 | Store per-video state; resume from last successful checkpoint | First batch of 10+ videos |
| Full-text search on transcript text without index | Search queries take 5+ seconds | Use FTS index from the start — migration is painful | 10+ videos with transcripts |
| Client-side filtering of all transcript data | Dashboard freezes when loading cross-debate view | Server-side pagination and pre-computed aggregations | 15+ videos |
| Re-running entire NLP pipeline for one changed transcript | Editing one transcript triggers re-processing all 50 videos | Pipeline must support single-video re-processing without affecting others | First time a correction is made |
| No caching of intermediate results | Changing sentiment model requires re-transcribing audio | Cache transcription and diarization results separately from NLP outputs | Phase 2 when NLP models change |
| Loading full audio files into memory | Out-of-memory on long videos (2+ hours) | Stream audio processing in chunks; process Whisper in 30-second windows | First video over 60 minutes |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing YouTube API keys or yt-dlp cookies in code | Keys exposed in git history | Use environment variables; never commit credentials |
| Embedding Deepgram/API keys in frontend dashboard | Anyone can extract and abuse the key | All API calls go through backend; frontend only talks to your API |
| No rate limiting on public dashboard | Scraping of all transcript data; API abuse | Implement rate limiting on public endpoints |
| Serving user-uploaded corrections without sanitization | XSS via transcript text | Sanitize all user input; render transcripts as text, not HTML |
| Storing video URLs with authentication tokens | Exposing private video access | Strip auth tokens from stored URLs; re-authenticate at download time |
| No access control on review interface | Public users can modify transcripts | Review interface is admin-only; public dashboard is read-only |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Dashboard requires knowing video titles | Users can't discover content by topic | Topic-first navigation: browse by subject, then drill into specific debates |
| Showing raw transcript without audio reference | Can't verify accuracy without watching video | Provide timestamped transcript with audio playback at each segment |
| Filtering returns "no results" without explanation | User doesn't know if filter is wrong or data is missing | Show filter match counts; suggest similar terms; explain empty results |
| No way to see what was corrected in review | Can't trust data if corrections are invisible | Show diff view: original transcript vs. corrected version, with highlighted changes |
| Treating all speaker segments equally | Short interjections ("yeah", "right") clutter analysis | Filter by minimum segment length or word count; surface "substantive arguments" vs. "acknowledgments" |
| Cross-debate comparison is a flat table | Hard to see patterns across 30+ debates | Visual topic map: network graph of arguments, heatmap of stance by topic, timeline of positions |
| No progress indication during batch processing | Admin doesn't know if pipeline is running or stuck | Real-time processing status with per-video progress and estimated completion |

## "Looks Done But Isn't" Checklist

- [ ] **Diarization:** Often missing speaker boundary accuracy — verify by spot-checking 5+ rapid turn-taking segments per video against actual audio
- [ ] **Transcription:** Often passes spot-check on clear audio but fails on phone-quality caller segments — verify specifically on caller speech
- [ ] **Human Review:** Often has a UI but no workflow enforcement — verify that unreviewed transcripts CANNOT appear in dashboard analysis
- [ ] **Keyword Extraction:** Often surfaces debate markers instead of topic words — verify top keywords match actual debate subjects
- [ ] **Sentiment Analysis:** Often shows everything as "negative" — verify that two speakers on the same side show similar sentiment on the same topic
- [ ] **Cross-Debate Analysis:** Often works for 3 videos but fails at 20 — verify with full dataset before calling done
- [ ] **Batch Processing:** Often works for happy path but has no error recovery — verify behavior when one video fails mid-batch
- [ ] **Public Dashboard:** Often works for admin but breaks for unauthenticated users — verify as anonymous user, not logged-in admin
- [ ] **Search:** Often works for exact matches but misses partial/similar terms — verify with typos, partial phrases, and semantic equivalents
- [ ] **Audio Download:** Often works for public videos but fails on age-restricted, deleted, or region-locked content — verify error handling for unavailable videos

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Bad diarization on all videos | HIGH | Must re-run diarization with better config + re-review all transcripts; NLP outputs are garbage |
| No human review step built | MEDIUM | Add review interface + flag all existing transcripts as "unreviewed"; don't need to re-transcribe |
| Wrong sentiment model chosen | LOW | Re-run only NLP pipeline on corrected transcripts; transcription and diarization untouched |
| No full-text search index | MEDIUM | Add FTS index; populate from existing transcripts; no re-transcription needed |
| Schema migration needed | MEDIUM | Write migration scripts; run on existing data; test on copy first |
| YouTube video deleted/removed | LOW | Flag as unavailable; keep existing transcript data; mark as "source unavailable" in dashboard |
| Audio pre-processing missing | HIGH | Must re-download audio, pre-process, re-transcribe, re-diarize, re-review |
| No batch error recovery | MEDIUM | Add checkpointing to pipeline; identify last successful video; resume from that point |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Diarization as solved problem | Phase 1 — build review interface first | Spot-check 5+ turn boundaries per video against audio |
| YouTube audio quality variation | Phase 1 — test on worst video first | Transcribe lowest-quality video; verify caller segments |
| Timestamp misalignment | Phase 1 — use integrated service or custom alignment | Verify word-to-speaker mapping at 5+ boundary regions |
| NLP on unreviewed transcripts | Phase 1 — human review gate | Confirm no unreviewed transcript enters NLP pipeline |
| Keyword extraction noise | Phase 2 — domain-specific stopwords + n-grams | Top keywords match known debate subjects |
| Sentiment misunderstanding debates | Phase 2 — stance detection, not generic sentiment | Manually label 20 segments; compare model output |
| Batch processing without validation | Phase 1 — per-video isolation + checkpointing | Inject a bad video; verify pipeline handles it gracefully |
| YouTube API limits | Phase 1 — yt-dlp + backoff + caching | Process 50 videos in one batch without quota exhaustion |
| Schema evolution | Phase 1 — versioned schema from day one | Add a new field; verify migration works on existing data |
| Dashboard performance | Phase 1 (data model) + Phase 3 (dashboard) | Load test with 50 videos; dashboard loads in < 2s |

## Sources

- OpenAI Whisper README and model documentation — hallucination behavior on low-quality audio, timestamp accuracy, model size tradeoffs
- pyannote-audio GitHub and documentation — diarization benchmarks, `num_speakers` constraint, speaker embedding for voice anchoring
- Deepgram Diarization API documentation — `diarize=true` with `utterances=true` for aligned output
- Domain experience: YouTube audio pipeline projects, debate/conversation transcription systems
- User-provided context: previous failed attempts with AI speaker parsing, 1v1 format constraint, "best available" transcription requirement

---
*Pitfalls research for: YouTube debate transcription and analysis*
*Researched: 2026-04-09*
