---
phase: 03-nlp-analysis-pipeline
plan: 01
subsystem: nlp-foundation
tags: [models, config, schemas, stopwords, nlp]
dependency_graph:
  requires: []
  provides: [nlp-models, nlp-schemas, nlp-config, stopwords]
  affects: [03-02, 03-03, 03-04, 03-05]
tech_stack:
  added: [pydantic-schemas]
  patterns: [two-pass-llm-extraction, domain-stopword-filtering]
key_files:
  created:
    - src/parker/nlp/__init__.py
    - src/parker/nlp/schemas.py
    - src/parker/nlp/stopwords.py
  modified:
    - src/parker/models.py
    - src/parker/config.py
decisions:
  - StanceLabel enum duplicated in models.py (SQLModel) and schemas.py (Pydantic) for layer separation
  - Embedding stored as JSON string in Topic.embedding_json for SQLite compatibility
  - Two-pass extraction schema design (KeywordTopicExtraction then StanceExtraction) for focused LLM prompts
metrics:
  duration_seconds: 125
  completed: "2026-04-12T19:14:20Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 3 Plan 1: NLP Foundation - Data Models, Config, Schemas & Stopwords Summary

NLP data models (Topic, Stance, Keyword, TopicMatch, NLPResult) with LLM config settings, two-pass Pydantic extraction schemas, and debate-domain stopword filter.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add NLP data models and config settings | 200e7da | src/parker/models.py, src/parker/config.py |
| 2 | Create NLP package with Pydantic schemas and stopwords | 80fcbae | src/parker/nlp/__init__.py, src/parker/nlp/schemas.py, src/parker/nlp/stopwords.py |

## What Was Built

### NLP Data Models (models.py)
- **NLPStatus** enum: PENDING, ANALYZING, COMPLETED, FAILED
- **StanceLabel** enum: SUPPORTS, OPPOSES, QUALIFIED, DEFLECTS
- **Topic**: debate topics with embedding support for cross-debate matching
- **Stance**: speaker stance per topic with confidence score and evidence
- **Keyword**: notable phrases per speaker with occurrence count
- **TopicMatch**: cross-debate topic similarity tracking
- **NLPResult**: per-debate analysis status and raw LLM response storage

### LLM Config (config.py)
- llm_provider (openai/anthropic), llm_api_key, llm_model (gpt-4o-mini default)
- llm_max_tokens (4096), embedding_model (all-MiniLM-L6-v2), topic_similarity_threshold (0.7)

### Pydantic Schemas (nlp/schemas.py)
- **KeywordTopicExtraction**: first-pass LLM output (keywords + topics)
- **StanceExtraction**: second-pass LLM output (stances per speaker per topic)
- **DebateAnalysis**: combined convenience model

### Stopwords (nlp/stopwords.py)
- 30+ debate-specific stopwords (filler, transitions, meta-language)
- filter_stopwords() and is_stopword() utility functions

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All 5 verification checks passed:
1. NLP models importable from parker.models
2. Pydantic schemas importable from parker.nlp.schemas
3. Stopwords importable with 20+ entries, filter works correctly
4. Config returns llm_provider=openai, embedding_model=all-MiniLM-L6-v2
5. Existing models (Debate, Utterance) unaffected
