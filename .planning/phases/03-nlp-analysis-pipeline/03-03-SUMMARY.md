---
phase: 03-nlp-analysis-pipeline
plan: 03
subsystem: database, nlp
tags: [sqlmodel, numpy, sentence-transformers, cosine-similarity, embeddings, crud]

# Dependency graph
requires:
  - phase: 03-nlp-analysis-pipeline/01
    provides: "NLP data models (Topic, Stance, Keyword, TopicMatch, NLPResult)"
provides:
  - "13 NLP CRUD functions for all NLP models"
  - "Cross-debate keyword frequency aggregation queries"
  - "Topic embedding generation with lazy-loaded sentence-transformers"
  - "Cross-debate topic similarity matching via cosine similarity"
  - "TopicMatch creation with duplicate detection"
affects: [03-nlp-analysis-pipeline/02, 03-nlp-analysis-pipeline/04, 04-public-dashboard]

# Tech tracking
tech-stack:
  added: [numpy, sentence-transformers]
  patterns: [lazy-loaded model singleton, batch embedding encode, pairwise similarity matrix]

key-files:
  created:
    - src/parker/nlp/embeddings.py
  modified:
    - src/parker/crud.py

key-decisions:
  - "Used module-level singleton for sentence-transformers model to avoid repeated 5-30s load times"
  - "Batch encode topics for efficiency rather than one-by-one embedding"
  - "Bidirectional duplicate check on TopicMatch creation to prevent mirrored entries"

patterns-established:
  - "NLP CRUD pattern: grouped by model (NLPResult, Topic, Stance, Keyword, TopicMatch) with section headers"
  - "Embedding singleton: lazy-load on first use, cache globally"
  - "Cross-debate matching: skip same-debate comparisons, threshold-based filtering"

requirements-completed: [NLPP-04, NLPP-05]

# Metrics
duration: 2min
completed: 2026-04-12
---

# Phase 3 Plan 03: NLP CRUD & Cross-Debate Matching Summary

**13 NLP CRUD functions with frequency aggregation, topic embedding generation via sentence-transformers, and cross-debate cosine similarity matching**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-12T19:16:59Z
- **Completed:** 2026-04-12T19:19:11Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- 13 new CRUD functions covering all NLP models: NLPResult, Topic, Stance, Keyword, TopicMatch
- Cross-debate keyword frequency aggregation with optional speaker filter using SQL group_by/sum
- Topic embedding module with lazy-loaded sentence-transformers singleton, cosine similarity, and configurable threshold matching
- Duplicate-aware TopicMatch creation with bidirectional check

## Task Commits

Each task was committed atomically:

1. **Task 1: Add NLP CRUD operations and frequency queries to crud.py** - `324d866` (feat)
2. **Task 2: Create topic embedding generation and cross-debate similarity matching** - `d089c1a` (feat)

## Files Created/Modified
- `src/parker/crud.py` - 13 NLP CRUD functions: NLPResult create/read, Topic CRUD with status management, Stance queries, Keyword frequency aggregation, TopicMatch CRUD, bulk delete
- `src/parker/nlp/embeddings.py` - Topic embedding generation with lazy-loaded model, cosine similarity, cross-debate matching, TopicMatch creation

## Decisions Made
- Used module-level singleton for sentence-transformers model to avoid repeated load times
- Batch encode topics for efficiency in find_matching_topics rather than embedding one-by-one
- Bidirectional duplicate check on TopicMatch creation prevents both (A,B) and (B,A) duplicates
- Same-debate topic pairs skipped in matching since they are already distinct within a debate

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CRUD layer ready for Plan 02 (LLM analysis pipeline) and Plan 04 (NLP API routes)
- Embedding module ready for cross-debate topic matching after NLP analysis runs
- All existing CRUD functions verified unchanged

## Self-Check: PASSED

All files and commits verified:
- src/parker/crud.py: FOUND
- src/parker/nlp/embeddings.py: FOUND
- SUMMARY.md: FOUND
- Commit 324d866: FOUND
- Commit d089c1a: FOUND

---
*Phase: 03-nlp-analysis-pipeline*
*Completed: 2026-04-12*
