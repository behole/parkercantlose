# Public Debate Page Redesign — Design

**Date:** 2026-07-08
**Status:** Approved
**Scope:** Public debate detail page (`/debate/{slug}`), slug system, synced transcript layout

## Goals

1. **Natural-language URLs** — replace raw YouTube-ID URLs with readable slugs derived from debate titles
2. **Remove gradient background** — drop the colored banner behind the YouTube embed and title
3. **Synced transcript playback** — replicate the review page's video+transcript sync on the public page

## Design Decisions

### Slug System

- **Source:** debate title, truncated to ~50 characters
- **Format:** lowercase, hyphenated, stopwords/pronouns stripped (e.g. "Parker vs. John on Immigration Policy" → `parker-john-immigration-policy`)
- **Collision handling:** append last 6 chars of YouTube ID on collision (e.g. `parker-john-immigration-policy-abc123`)
- **Storage:** `slug` column on `Debate` model (nullable string), generated on creation, updated on title change
- **Routing:** `/debate/{slug}` is canonical; `/debate/{youtube_id}` becomes a 301 redirect to the slug URL (backward compat for existing links and admin review page)
- **Backfill:** one-time CLI command populates slugs for existing debates

### Synced Two-Panel Layout

- **Layout:** CSS grid two-panel (reuses `.review-layout` pattern): video left (sticky), transcript right (scrollable, max-height 80vh)
- **Video panel:** YouTube IFrame API player (not raw `<iframe>`) for `getCurrentTime()` / `seekTo()` access. Auto-scroll checkbox below player (checked by default).
- **Transcript panel:** each utterance is a `.segment` with `data-start` / `data-end`. Sync loop polls every 250ms, highlights active segment (`.segment--active`), auto-scrolls if enabled. Click timestamp → `seekTo()` + play. Read-only — no editing, no speaker toggle.
- **Text search:** existing transcript text-search input stays, sits above transcript panel, filters by text content (independent of video sync).
- **JS:** new `public-debate.js` (~80 lines) with sync + seek + search-filter. `review.js` unchanged (keeps editing functions). Small duplication of sync core, avoids coupling public page to admin code.

### Page Structure (top to bottom)

1. Breadcrumb nav (Home / Debate Title)
2. Title + meta (date, duration) — clean, no gradient banner
3. Two-panel: synced video (left, sticky) + transcript (right, scrollable)
4. Topics & Stances section (unchanged)
5. Key Phrases section (unchanged)

### Background Cleanup

- Remove `.debate-header` gradient background and related overrides
- Remove `.debate-embed` border/background rules (embed moves into `.video-panel` with `#player-wrap`)
- Remove old `.public-transcript`, `.transcript-entry`, `.transcript-time`, `.transcript-text` rules (replaced by `.segment` / `.segment--active`)

## Files Touched

| File | Change |
|------|--------|
| `src/parker/models.py` | Add `slug: str \| None` field to Debate |
| `src/parker/crud.py` | Slug generation + collision check helpers |
| `src/parker/web/public_routes.py` | New `/debate/{slug}` route; old route → 301 redirect |
| `src/parker/web/templates/debate_detail.html` | Full rewrite of top section |
| `src/parker/web/static/style.css` | Remove gradient/old-transcript styles |
| `src/parker/web/static/public-debate.js` | New sync JS file |
| `src/parker/cli.py` | Backfill slugs command |
| `tests/test_crud.py` | Slug generation/collision tests |

## Constraints

- No new Python dependencies
- No new JS dependencies (YouTube IFrame API via CDN, already used in review)
- SQLite migration is a simple `ALTER TABLE` (nullable column)
- Existing `/debate/{youtube_id}` links must still work (301 redirect)
- Read-only public page — no editing/HTMX on transcript

## Out of Scope

- Admin review page changes (review.js and review.html stay as-is)
- Changes to Topics/Stances or Key Phrases rendering
- Analytics page changes
- Deployment config changes
