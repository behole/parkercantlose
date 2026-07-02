# Phase 2: Transcript Review Interface - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Web interface for viewing timestamped, speaker-labeled transcripts alongside YouTube video playback. Users can correct speaker attribution and transcript text on any segment. Unreviewed transcripts are blocked from NLP analysis (Phase 3) until approved. This is an internal review tool, not the public dashboard (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Web framework
- FastAPI backend serving Jinja2 templates with HTMX for interactivity
- Stays in the Python ecosystem — no separate frontend build step
- This is an internal review tool; the public dashboard (Phase 4) can use a richer frontend if needed
- Static assets (CSS/JS) served directly by FastAPI

### Transcript editing UX
- Inline editing — click segment text to edit in place
- Speaker label click toggles between parker/caller (the only two speakers)
- Each segment shows: timestamp, speaker label, text
- Visual diff or highlight for edited segments (so reviewer can see what changed vs. original)

### Video-transcript sync
- YouTube IFrame Player API embed alongside transcript
- Bidirectional sync: click a transcript line → video seeks to that timestamp; video plays → current line highlights/scrolls into view
- Transcript auto-scrolls to follow video playback (with option to pause auto-scroll when user is manually browsing)

### Review & approval workflow
- Add `review_status` field to Debate model: `unreviewed` | `in_progress` | `approved`
- Per-video approval — mark the entire transcript as approved when review is complete
- Visual status indicators on video list (unreviewed, in progress, approved)
- Phase 3 NLP pipeline checks `review_status == approved` before processing
- No partial approval — keeps the model simple for dozens of videos

### Claude's Discretion
- Page layout and CSS styling choices
- Loading states and error handling UX
- Exact HTMX interaction patterns (swap targets, trigger events)
- Whether to use a CSS framework (Tailwind, Pico, etc.) or plain CSS

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Data models
- `src/parker/models.py` — Debate and Utterance SQLModel schemas; review_status field needs to be added
- `src/parker/crud.py` — Existing CRUD operations for Debate records; will need review-specific operations
- `src/parker/db.py` — Database engine and session management

### Pipeline integration
- `src/parker/pipeline.py` — Pipeline orchestrator; Phase 3 gate will check review_status here
- `src/parker/config.py` — Settings via pydantic-settings; may need web server config additions

### Requirements
- `.planning/REQUIREMENTS.md` — REVW-01 through REVW-05 define acceptance criteria
- `.planning/ROADMAP.md` §Phase 2 — Success criteria and key decisions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Utterance` model: already has speaker, text, start_time, end_time, words_json, confidence — maps directly to transcript display
- `Debate` model: has youtube_id (for embed URL), title, url, status — needs review_status addition
- `crud.py`: has create/read/update/reset debate operations — extend for review workflows
- `config.py`: pydantic-settings pattern — add web server port/host config

### Established Patterns
- SQLModel + SQLite for persistence
- Python 3.11+ with type hints throughout
- Typer for CLI — web server can be a new CLI command (`parker serve`)
- All source in `src/parker/` package

### Integration Points
- New `serve` command in `cli.py` to launch FastAPI dev server
- New `src/parker/web/` package for routes, templates, static assets
- Debate.review_status field addition (schema migration consideration)
- Phase 3 pipeline will gate on review_status — add check in pipeline.py or crud.py

</code_context>

<specifics>
## Specific Ideas

- Speaker diarization has been historically unreliable — the review UX must be robust and make corrections easy, not an afterthought
- Always 1v1 format (Parker vs. caller) — speaker toggle is binary, not a dropdown
- Word-level timestamps available in `words_json` — can be used for fine-grained video sync
- Dozens of videos, not thousands — no need for pagination complexity on the video list

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-transcript-review-interface*
*Context gathered: 2026-04-12*
