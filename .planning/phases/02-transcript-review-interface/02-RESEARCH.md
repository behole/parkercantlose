# Phase 2: Transcript Review Interface — Research

**Researched:** 2026-04-12
**Status:** RESEARCH COMPLETE

## 1. FastAPI + Jinja2 + HTMX Stack

### FastAPI Web Server
- FastAPI supports Jinja2 templates natively via `fastapi.templating.Jinja2Templates`
- Static files via `fastapi.staticfiles.StaticFiles`
- Add `jinja2` and `python-multipart` to dependencies
- Mount at `/static` for CSS/JS, templates in `src/parker/web/templates/`
- Use `uvicorn` as ASGI server — add to dependencies

### HTMX for Interactivity
- HTMX enables server-rendered HTML with dynamic updates — no JS framework needed
- Key patterns for this phase:
  - `hx-put` on speaker label click → swap speaker attribution, return updated segment HTML
  - `hx-patch` on text blur/submit → save edited text, return updated segment HTML
  - `hx-get` for loading transcript segments on video list click
  - `hx-trigger="click"` on transcript lines for video seek (combined with small JS for YouTube API)
- HTMX swaps: use `hx-swap="outerHTML"` on individual segment `<div>` elements for targeted updates
- Add HTMX via CDN `<script>` tag — no build step needed

### Project Structure
```
src/parker/web/
  __init__.py          # FastAPI app factory
  routes.py            # Route handlers (or split: videos.py, api.py)
  templates/
    base.html          # Layout with HTMX + YouTube API script
    video_list.html    # Dashboard listing all videos with review status
    review.html        # Single video review page
    partials/
      segment.html     # Single utterance segment (HTMX swap target)
      status_badge.html # Review status indicator
  static/
    style.css          # Styles
    review.js          # YouTube IFrame API + transcript sync logic
```

## 2. YouTube IFrame Player API

### Embedding
- Use `<div id="player"></div>` + YouTube IFrame API JS
- Initialize: `new YT.Player('player', { videoId: '{youtube_id}', events: { onStateChange, onReady } })`
- Seek: `player.seekTo(seconds, true)` — called when user clicks a transcript line
- Get current time: `player.getCurrentTime()` — poll this to highlight current segment

### Bidirectional Sync
- **Click transcript → seek video:** Add `onclick` handler on each segment div, call `player.seekTo(segment.start_time)`
- **Video → highlight transcript:** Use `setInterval()` (~250ms) polling `player.getCurrentTime()`, find segment where `start_time <= currentTime < end_time`, add `.active` CSS class, scroll into view
- **Auto-scroll:** Use `element.scrollIntoView({ behavior: 'smooth', block: 'center' })` — toggle with a checkbox so user can pause auto-scroll when manually browsing

### Considerations
- YouTube IFrame API requires `https://www.youtube.com/iframe_api` script loaded
- Works on localhost — no domain restriction for development
- API is async — player ready callback before any seek operations
- Handle edge case: segments with gaps between them (no active segment)

## 3. Data Model Changes

### Debate Model Addition
```python
class ReviewStatus(str, enum.Enum):
    UNREVIEWED = "unreviewed"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"

# Add to Debate model:
review_status: ReviewStatus = Field(default=ReviewStatus.UNREVIEWED)
```

### Utterance Model — Track Edits
Consider adding to Utterance:
```python
original_speaker: Optional[str] = None   # Preserve original diarization result
original_text: Optional[str] = None       # Preserve original transcription
edited_at: Optional[datetime] = None      # When last edited
```

When user edits, copy current values to `original_*` fields (only on first edit), update `speaker`/`text`, set `edited_at`. This preserves the diff between AI output and human correction.

### Schema Migration
- SQLite with SQLModel — use `ALTER TABLE` for new columns
- Since this is pre-production with only 4 videos: simplest approach is drop + recreate tables, re-run pipeline
- Alternative: write a migration script that adds columns with defaults
- Recommended: migration script (preserves existing completed transcripts)

## 4. API Endpoints

### Page Routes
- `GET /` — Video list page (redirect or same as /videos)
- `GET /videos` — List all debates with review status badges
- `GET /videos/{youtube_id}/review` — Review page for a specific video

### HTMX API Routes
- `PUT /api/utterances/{id}/speaker` — Toggle speaker (parker↔caller), return updated segment HTML partial
- `PATCH /api/utterances/{id}/text` — Update transcript text, return updated segment HTML partial
- `POST /api/videos/{youtube_id}/approve` — Mark video as approved
- `POST /api/videos/{youtube_id}/unapprove` — Revert to in_progress (in case of mistake)
- `GET /api/videos/{youtube_id}/segments` — Load all segments (for initial page load or refresh)

### Response Pattern
All HTMX endpoints return HTML partials (rendered Jinja2 templates), not JSON. This is the HTMX pattern — server returns the HTML fragment that replaces the target element.

## 5. Transcript Editing UX Patterns

### Inline Speaker Toggle
- Speaker label rendered as a clickable badge: `<span class="speaker-badge parker" hx-put="/api/utterances/{id}/speaker">`
- Click toggles parker↔caller — binary, no dropdown needed
- Badge color changes immediately (HTMX swaps the segment partial)
- Visual: parker = blue/primary, caller = red/secondary

### Inline Text Editing
- Display mode: static text in a `<span>`
- Edit mode: click text → transforms to `<textarea>` with current text
- Save: blur or Ctrl+Enter → `hx-patch` sends updated text
- Cancel: Escape key reverts to display mode
- Implementation: use HTMX `hx-trigger="blur"` or small JS handler for keyboard shortcuts

### Visual Indicators for Edits
- Edited segments get a subtle left border or background tint
- Show original vs. edited diff on hover (tooltip) if original_* fields populated
- Count of edits shown in video list: "12 edits made"

## 6. Review Workflow

### Status Transitions
```
UNREVIEWED → IN_PROGRESS (auto: when first edit is made on any segment)
IN_PROGRESS → APPROVED (manual: user clicks "Approve Transcript")
APPROVED → IN_PROGRESS (manual: user clicks "Revoke Approval" — allows re-editing)
```

### Phase 3 Gate
- Pipeline or NLP processing checks `debate.review_status == ReviewStatus.APPROVED`
- Unapproved videos are visible but clearly marked — cannot enter NLP pipeline
- Video list shows filter/sort by review status

### Approval UI
- "Approve Transcript" button prominently placed on review page
- Confirmation: brief "Are you sure?" or just direct action (for dozens of videos, fast is better)
- After approval: visual change (green banner, status badge update)

## 7. CSS/Styling Approach

### Recommendation: Pico CSS or Plain CSS
- Pico CSS: classless CSS framework, semantic HTML gets styled automatically — minimal effort
- Alternative: Tailwind via CDN (play CDN) — more control but heavier
- For an internal review tool: Pico CSS is fastest to good-looking results
- Key styles needed: transcript segment layout, speaker badges, active segment highlight, edit states

### Layout
- Review page: two-column — video embed (left/top) + scrollable transcript (right/bottom)
- Responsive: stack vertically on narrow screens
- Video list: simple table or card grid with status badges

## 8. Dependencies to Add

```toml
# pyproject.toml additions
"fastapi>=0.115.0",
"uvicorn[standard]>=0.32.0",
"jinja2>=3.1.0",
"python-multipart>=0.0.12",
```

## 9. CLI Integration

Add `serve` command to existing Typer CLI:
```python
@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    """Launch the transcript review web interface."""
    import uvicorn
    uvicorn.run("parker.web:create_app", host=host, port=port, reload=True, factory=True)
```

## 10. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| YouTube IFrame API loading issues on localhost | Low | API works on any origin; fallback: direct iframe with URL params |
| HTMX learning curve | Low | Patterns are simple for CRUD; plenty of FastAPI+HTMX examples |
| Schema migration breaks existing data | Medium | Write migration script that preserves data; test on copy of DB first |
| Auto-scroll UX annoyance | Medium | Default off, toggle to enable; or smart pause when user scrolls manually |
| Text editing loses formatting | Low | Transcripts are plain text, no rich formatting to preserve |

## Validation Architecture

### Requirement Coverage
| Req ID | Validation Approach |
|--------|-------------------|
| REVW-01 | Load review page, verify transcript segments render with timestamps and speaker labels |
| REVW-02 | Click transcript line, verify video seeks to correct timestamp; play video, verify correct line highlights |
| REVW-03 | Click speaker badge, verify it toggles and persists after page reload |
| REVW-04 | Edit text inline, verify change persists after page reload |
| REVW-05 | Verify unapproved videos show status badge; verify approved check exists for Phase 3 gate |

### Integration Tests
- Start FastAPI test server, use httpx AsyncClient
- Test each API endpoint returns correct HTML partials
- Test DB persistence: edit → reload → verify edit persisted
- Test review status transitions: unreviewed → in_progress → approved

---

*Researched: 2026-04-12*
