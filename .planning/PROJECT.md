# Parker Debate Dashboard

## What This Is

A tool that transcribes YouTube debate videos featuring Parker debating individual callers one-at-a-time on defined subjects, then parses speakers, structures the data, and presents a public filterable dashboard for analyzing arguments — keywords, phrases, ideas, sentiment, and topic mapping across all debates.

## Core Value

Topic mapping — understanding the full landscape of arguments on any given subject across all debates. Not just "what was said" but "here's the complete argument map."

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] YouTube video ingestion and transcription (best available method)
- [ ] AI speaker diarization identifying Parker vs. callers
- [ ] Human review/correction interface for speaker attribution accuracy
- [ ] Keyword and phrase extraction from transcripts
- [ ] Idea and topic extraction (hybrid: AI suggests, human refines)
- [ ] Sentiment and position analysis per speaker per topic
- [ ] Frequency measurement of phrases, keywords, and ideas
- [ ] Side-by-side speaker comparison on shared topics
- [ ] Single-debate deep dive view
- [ ] Cross-debate pattern analysis view
- [ ] Filterable dashboard — by entity (debater, topic, keyword), by sentiment, by time period, by metric (frequency, strength)
- [ ] Public-facing web interface

### Out of Scope

- Debate scoring or "who won" judging — this is analytical, not evaluative
- Real-time/streaming processing — batch ingestion is fine
- Mobile app — web-first
- Massive scale (thousands+) — designed for dozens of videos

## Context

- Parker debates individual callers one-at-a-time on defined subjects — always a 1v1 format
- Speaker diarization is a known pain point — previous attempts with AI speaker parsing produced poor results, so the correction/review UX must be robust
- Topics are pre-defined per debate but may need refinement — hybrid AI + manual approach
- Dozens of videos to process, not hundreds or thousands
- Public-facing tool — anyone can browse and analyze the debates

## Constraints

- **Transcription quality**: Must use best available transcription method — accuracy matters since this drives all downstream analysis
- **Speaker attribution**: Historically unreliable with pure AI — must include human verification step as first-class feature
- **Format**: Always Parker vs. one caller, one at a time — this structure should be leveraged to improve diarization

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid topic extraction | AI can surface topics efficiently but human judgment refines accuracy | — Pending |
| AI diarization + human review | Pure AI speaker parsing has failed before; verification layer is essential | — Pending |
| Best available transcription | Downstream analysis quality depends on transcript accuracy | — Pending |
| Public web dashboard | Designed for anyone to browse and analyze, not just internal use | — Pending |

---
*Last updated: 2026-04-09 after initialization*
