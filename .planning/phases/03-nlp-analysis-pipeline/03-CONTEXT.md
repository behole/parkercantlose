# Phase 3: NLP Analysis Pipeline - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract structured analysis from human-reviewed transcripts — keywords, topics, stance classification, frequency measurement, and cross-debate topic matching. Only approved debates (review_status == APPROVED) enter the NLP pipeline. This phase builds the analytical data layer; the public dashboard for browsing results is Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Extraction approach
- LLM-based extraction via prompt engineering (Claude or OpenAI API)
- Debate language requires contextual understanding — traditional NLP (spaCy, NLTK) would miss stance nuance and topic framing
- Scale is dozens of videos, not thousands — API costs are negligible
- Process per-debate: send reviewed transcript segments to LLM with structured output prompts
- Store raw LLM responses for auditability

### Topic taxonomy
- Flat list of topics, not hierarchical taxonomy
- Hybrid seeded + extracted: seed initial topics from debate titles/descriptions, then LLM extracts additional topics from transcript content
- Topics are strings with optional description — no complex ontology
- Deduplication at extraction time: LLM prompted to reuse existing topics when semantically equivalent

### Stance classification
- 4 categories per requirements: SUPPORTS / OPPOSES / QUALIFIED / DEFLECTS
- Prompt-based LLM extraction, not a fine-tuned classifier (overkill at this scale)
- Each stance includes a confidence score (0.0–1.0) from the LLM
- Stance is per-speaker per-topic per-debate — granular enough for cross-debate comparison

### Human refinement workflow
- Integrated into the existing FastAPI + HTMX web interface (same tool as Phase 2 review)
- AI suggests topics per debate; user can accept, reject, rename, or merge topics
- Topic refinement page accessible after transcript is approved
- Stance classifications shown alongside topics for user verification
- No separate approval gate for NLP results — topic refinement is the quality control step

### Cross-debate topic matching
- Embedding similarity to suggest topic matches across debates
- Human confirms or rejects suggested matches
- Matching UI shows suggested pairs with similarity score, user clicks to confirm/reject
- Confirmed matches enable the cross-debate comparison views in Phase 4

### Keyword and phrase extraction
- LLM extracts keywords and notable phrases per speaker per debate
- Domain-specific stopword filtering (remove common debate filler: "well", "look", "so")
- Frequency counting across all approved debates for phrase/keyword popularity metrics

### Claude's Discretion
- Exact LLM prompt design and structured output format
- Embedding model choice for cross-debate matching
- Batch processing strategy (all debates at once vs. incremental)
- Database schema for NLP result models (topics, stances, keywords tables)
- Error handling for LLM API failures

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Data models & pipeline
- `src/parker/models.py` — Debate and Utterance SQLModel schemas; ReviewStatus enum; new NLP models will extend this
- `src/parker/crud.py` — CRUD operations including get_approved_debates(), toggle/edit operations; extend for NLP results
- `src/parker/pipeline.py` — Pipeline orchestrator with get_nlp_ready_debates() and is_debate_nlp_ready() gate already implemented
- `src/parker/db.py` — Database engine and session management

### Web interface (for human refinement UI)
- `src/parker/web/routes.py` — Existing FastAPI routes for review interface; extend for topic refinement
- `src/parker/web/templates/` — Jinja2 + HTMX templates; add topic refinement views
- `src/parker/web/static/` — Static assets; existing HTMX patterns to follow

### Configuration
- `src/parker/config.py` — Pydantic-settings pattern; will need LLM API key and model config

### Requirements
- `.planning/REQUIREMENTS.md` — NLPP-01 through NLPP-05 define acceptance criteria
- `.planning/ROADMAP.md` §Phase 3 — Success criteria, research flags, key decisions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_nlp_ready_debates(engine)` in pipeline.py: Phase 3 gate already implemented — returns only APPROVED debates
- `is_debate_nlp_ready(engine, youtube_id)` in pipeline.py: per-debate approval check
- `get_approved_debates(session)` in crud.py: query for approved debates
- `get_utterances_for_debate(session, debate_id)` in crud.py: fetch transcript segments for NLP input
- Utterance model has speaker, text, start_time, end_time, words_json — all available for NLP extraction
- FastAPI + HTMX web framework from Phase 2 — extend for topic refinement UI

### Established Patterns
- SQLModel + SQLite for all persistence
- Python 3.11+ with type hints throughout
- Typer CLI for commands — add `parker analyze` command
- HTMX for interactive UI without frontend build step
- Pydantic-settings for configuration

### Integration Points
- New NLP models (Topic, Stance, Keyword) as SQLModel tables with foreign keys to Debate
- New CLI command (`parker analyze`) to trigger NLP pipeline on approved debates
- New web routes for topic refinement UI
- pipeline.py already has the approval gate — NLP processing plugs in after it

</code_context>

<specifics>
## Specific Ideas

- Stance detection is critical — generic sentiment analysis would tag everything "negative" since debate language is inherently combative. The 4-category schema (SUPPORTS/OPPOSES/QUALIFIED/DEFLECTS) captures what actually matters.
- "AI suggests, human refines" is the core pattern — same philosophy as Phase 2's diarization review. AI does the heavy lifting, humans catch errors.
- Cross-debate topic matching enables the killer feature: "Parker argued X across N debates" — this is the core value proposition from PROJECT.md.
- Always Parker vs. one caller — this 1v1 structure means stance is always relative to a single topic per exchange.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-nlp-analysis-pipeline*
*Context gathered: 2026-04-12*
