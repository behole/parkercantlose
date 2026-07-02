# Phase 4 Context: Public Dashboard

**Phase:** 04-public-dashboard
**Created:** 2026-04-12
**Status:** Planning

## Phase Goal

Public-facing web interface for browsing, searching, and analyzing all processed debates. No login required. SEO-optimized. Built on existing FastAPI + Jinja2 + HTMX stack.

## Requirements

| ID | Description | Plan |
|----|-------------|------|
| DASH-01 | Single-debate deep dive (topics, positions, key quotes, transcript) | 04-02 |
| DASH-02 | Cross-debate pattern analysis ("Parker argued X across N debates") | 04-03 |
| DASH-03 | Side-by-side speaker comparison on shared topics | 04-02 |
| DASH-04 | Filterable by entity (debater, topic, keyword), stance, time period, metric | 04-03 |
| DASH-05 | Full-text search across all transcripts with time-coded results | 04-04 |
| DASH-06 | Public-facing — no login, SEO-optimized | 04-01, 04-04 |

## Success Criteria

1. Any visitor can browse the dashboard and view debate analysis without creating an account or logging in
2. Single-debate view displays topics, speaker positions, key quotes, and full searchable transcript
3. Cross-debate view shows patterns like "Parker argued X across N debates" with drill-down capability
4. Filtering by debater, topic, keyword, stance, time period returns accurate results
5. Full-text search across all transcripts returns time-coded, speaker-labeled results with video jump links

## Architecture Decisions

- **Frontend:** Extend FastAPI + Jinja2 + HTMX (not separate Next.js)
- **Visualization:** CSS-only (no chart libraries)
- **Deployment:** Single VPS with gunicorn + nginx
- **App structure:** Same FastAPI app, public routes alongside admin routes
- **SEO:** Server-rendered HTML with OG meta tags, clean URLs

## Dependencies on Previous Phases

| Dependency | From Phase | Status |
|------------|-----------|--------|
| Debates with completed NLP analysis | Phase 3 | Complete — real data exists |
| Topics with accepted/confirmed status | Phase 3 | Complete |
| Stances with confidence scores | Phase 3 | Complete |
| Keywords with frequency counts | Phase 3 | Complete |
| Cross-debate topic matches | Phase 3 | Complete |
| Utterances with speaker labels | Phase 1-2 | Complete |

## Data Available

Real debate data exists through all 3 phases:
- Debates: transcribed, diarized, reviewed, approved, NLP-analyzed
- Utterances: timestamped, speaker-labeled
- Topics: AI-suggested, human-refined (accepted/renamed)
- Stances: per speaker per topic with confidence
- Keywords: per speaker per debate with counts
- Topic matches: cross-debate similarity with confirmed/rejected status

## Existing Code to Extend

- `src/parker/web/routes.py` — admin routes (keep as-is)
- `src/parker/web/templates/base.html` — admin base template
- `src/parker/crud.py` — existing CRUD functions (extend, don't modify)
- `src/parker/models.py` — data models (add FTS if needed)

## Key Risks

1. **Route collision** — public routes must not conflict with admin routes (/videos, /videos/{id}/review, etc.)
2. **FTS5 availability** — SQLite FTS5 must be compiled in the target Python
3. **Performance** — dashboard queries must be fast with pre-computed aggregations, not live joins
4. **Data exposure** — only show approved+analyzed debates, never raw/unreviewed data

---
*Created: 2026-04-12*
