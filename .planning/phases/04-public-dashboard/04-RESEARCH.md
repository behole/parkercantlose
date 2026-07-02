# Phase 4 Research: Public Dashboard

**Phase Goal:** Public-facing web interface for browsing, searching, and analyzing all processed debates.
**Researched:** 2026-04-12
**Confidence:** HIGH

## Key Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend framework | Extend existing FastAPI + Jinja2 + HTMX | Single Python stack, no new build tooling, consistent patterns |
| Visualization | CSS-only (progress bars, comparison cards, heatmaps) | No JS libraries, works with Jinja2, add charting later if needed |
| Deployment | Single VPS | SQLite, simple, cheap, serves both admin and public |
| App structure | Same app, different route prefixes | Shared DB session, single deployment |
| SEO | Server-rendered HTML with meta tags | Jinja2 templates already SSR; add OG tags, structured data |

## Existing Infrastructure to Build On

### Data Models (models.py)
- `Debate` — youtube_id, title, url, duration, upload_date, status, review_status
- `Utterance` — debate_id, speaker, text, start_time, end_time, confidence
- `Topic` — debate_id, name, description, status (suggested/accepted/rejected/renamed/merged), embedding_json
- `Stance` — debate_id, topic_id, speaker, label (SUPPORTS/OPPOSES/QUALIFIED/DEFLECTS), confidence, evidence
- `Keyword` — debate_id, phrase, speaker, count
- `TopicMatch` — topic_a_id, topic_b_id, similarity, status (suggested/confirmed/rejected)
- `NLPResult` — debate_id, status, analyzed_at

### Existing CRUD Functions (crud.py)
- `get_all_debates()` — ordered by created_at desc
- `get_debate_by_youtube_id()` — lookup by youtube_id
- `get_utterances_for_debate()` — ordered by start_time
- `get_topics_for_debate()` — excludes rejected
- `get_all_active_topics()` — across all debates
- `get_stances_for_debate()` — all stances for a debate
- `get_stances_for_topic()` — cross-debate stances for a topic
- `get_keywords_for_debate()` — ordered by count desc
- `get_keyword_frequencies(speaker?)` — aggregate across debates
- `get_topic_matches(status?)` — cross-debate matches

### Existing Web Infrastructure
- FastAPI app with Jinja2Templates
- Pico CSS + HTMX base template (base.html)
- Admin routes in `web/routes.py`
- Partials system for HTMX swaps

## What Needs to Be Built

### New CRUD Functions Needed
1. **FTS5 search** — `search_utterances(session, query) → list[Utterance]` with FTS5 virtual table
2. **Cross-debate topic aggregation** — `get_topic_stances_across_debates(session, topic_name?) → dict` grouping stances by topic across debates
3. **Debate metadata for public** — `get_public_debates(session)` — debates that are approved AND have completed NLP
4. **Topic frequency** — `get_topic_frequency(session) → list[tuple[str, int]]` — how many debates each topic appears in
5. **Speaker stance summary** — `get_speaker_stance_summary(session, speaker) → dict` — aggregate stance distribution per speaker
6. **Filtered queries** — `get_debates_filtered(session, topic?, speaker?, keyword?, stance?, date_from?, date_to?) → list[Debate]`

### New Routes Needed

**Public pages (read-only, no auth):**
1. `GET /` or `GET /dashboard` — Dashboard home: debate count, topic count, recent debates, top keywords
2. `GET /debate/{youtube_id}` — Single-debate deep dive
3. `GET /patterns` — Cross-debate pattern analysis
4. `GET /search?q=...` — Full-text search results

### New Templates Needed
1. `public_base.html` — Public-facing base template (no admin nav, SEO meta, public branding)
2. `dashboard.html` — Dashboard home page
3. `debate_detail.html` — Single-debate deep dive
4. `patterns.html` — Cross-debate patterns view
5. `search_results.html` — Search results page

### FTS5 Setup
SQLite FTS5 virtual table on utterances for full-text search. Migration needed to create:
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS utterances_fts USING fts5(text, speaker, debate_id, content='utterance', content_rowid='id');
```
Plus triggers to keep FTS in sync with utterance inserts/updates.

## CSS Visualization Patterns

### Stance Comparison Cards
Two-column layout: Parker on left, Caller on right. Each shows stance label with color coding:
- SUPPORTS → green
- OPPOSES → red
- QUALIFIED → amber
- DEFLECTS → gray

Confidence shown as CSS progress bar.

### Topic Frequency Heatmap
Table rows = topics, columns = debates. Cell color intensity = whether topic appears (binary) or stance color.

### Keyword Frequency
Ordered list with CSS bar widths proportional to count. Max-width bar = highest count.

## SEO Strategy

- All public pages get `<title>`, `<meta description>`, Open Graph tags
- Structured data (JSON-LD) for debates
- Clean URLs: `/debate/{youtube_id}`, `/patterns`, `/search`
- No login required, no JS required (progressive enhancement with HTMX)

## Deployment Checklist
- [ ] Gunicorn or Uvicorn workers
- [ ] Nginx reverse proxy
- [ ] Static file serving (CSS, JS, images)
- [ ] Environment variables for config
- [ ] Database migration for FTS5

## Plan Breakdown

### Plan 04-01: Public Route Foundation
- New `public_routes.py` router
- `public_base.html` template with SEO meta, public nav, Pico CSS
- Dashboard home page: debate list with status indicators, topic count, keyword cloud
- CRUD: `get_public_debates()`, `get_topic_frequency()`
- Mount public router at `/` (or restructure admin to `/admin/*`)

### Plan 04-02: Single-Debate Deep Dive
- Debate detail template with YouTube embed
- Topics section with stance comparison cards (CSS-only)
- Key quotes section (evidence from stances)
- Full transcript with search-within-page
- Side-by-side speaker comparison on shared topics
- CRUD: `get_speaker_stance_summary()`

### Plan 04-03: Cross-Debate Pattern Analysis + Filters
- Cross-debate patterns page: "Parker argued X across N debates"
- Topic drill-down: click a topic, see all debates + stances
- Filter bar: speaker, topic, keyword, stance, date range
- Frequency tables and CSS bar charts
- CRUD: `get_topic_stances_across_debates()`, `get_debates_filtered()`

### Plan 04-04: Full-Text Search + Deployment
- FTS5 virtual table creation + migration
- FTS sync triggers
- Search page with time-coded, speaker-labeled results
- Video jump links (YouTube embed with timestamp)
- Deployment config: gunicorn, nginx template, env setup

---
*Researched: 2026-04-12*
