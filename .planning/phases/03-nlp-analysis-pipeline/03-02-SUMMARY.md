---
phase: 03-nlp-analysis-pipeline
plan: 02
subsystem: nlp
tags: [openai, anthropic, llm, structured-output, pydantic, extraction]

requires:
  - phase: 03-01
    provides: "Pydantic schemas (KeywordTopicExtraction, StanceExtraction, DebateAnalysis), NLP models (Topic, Stance, Keyword, NLPResult), LLM config settings, stopword filtering"
provides:
  - "LLM prompt templates for two-pass keyword/topic/stance extraction"
  - "Extractor module with OpenAI and Anthropic dual-provider support"
  - "analyze_debate pipeline orchestrator with idempotency"
  - "parker analyze CLI command (--youtube-id, --all, --force)"
affects: [03-03, 03-04, 04-public-dashboard]

tech-stack:
  added: [openai, anthropic]
  patterns: [two-pass-llm-extraction, structured-output-parsing, tool-use-anthropic]

key-files:
  created:
    - src/parker/nlp/prompts.py
    - src/parker/nlp/extractor.py
  modified:
    - src/parker/pipeline.py
    - src/parker/cli.py

key-decisions:
  - "Two-pass extraction: keywords+topics first, then stances with topic context for better accuracy"
  - "OpenAI uses beta.chat.completions.parse for structured output; Anthropic uses tool_use pattern"
  - "LLM extraction runs outside DB session to avoid long-held locks"
  - "Existing topics passed to LLM for semantic deduplication across debates"

patterns-established:
  - "Two-pass LLM extraction: coarse extraction first, then detailed classification with prior results as context"
  - "Dual-provider LLM support: unified call_llm() dispatches to provider-specific implementations"
  - "Pipeline idempotency: check for existing completed results, skip unless --force"

requirements-completed: [NLPP-01, NLPP-02, NLPP-03]

duration: 5min
completed: 2026-04-12
---

# Phase 3 Plan 02: LLM Extraction Pipeline Summary

**Two-pass LLM extraction pipeline with dual OpenAI/Anthropic support, debate analysis CLI, and raw response auditability**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-12T19:16:48Z
- **Completed:** 2026-04-12T19:22:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Two-pass LLM extraction: keywords+topics first, then stance classification with topic context
- Dual OpenAI and Anthropic provider support via structured output (parse API / tool_use)
- `parker analyze` CLI with --youtube-id, --all, --force flags for single or batch analysis
- Idempotent pipeline that skips already-analyzed debates unless forced
- Raw LLM JSON stored in NLPResult for full auditability
- Stopword filtering applied to extracted keywords before storage

## Task Commits

Each task was committed atomically:

1. **Task 1: Create LLM prompts and extractor module** - `ecbf131` (feat)
2. **Task 2: Add analyze_debate to pipeline and parker analyze CLI** - `b7cc361` (feat)

## Files Created/Modified
- `src/parker/nlp/prompts.py` - System prompts for keyword/topic and stance extraction, transcript formatter, message builders
- `src/parker/nlp/extractor.py` - LLM client factory, call_llm dispatcher, two-pass extraction, DB storage
- `src/parker/pipeline.py` - analyze_debate orchestrator with idempotency and error handling
- `src/parker/cli.py` - parker analyze command with --youtube-id, --all, --force options

## Decisions Made
- Used OpenAI beta.chat.completions.parse for structured output (returns validated Pydantic models directly)
- Used Anthropic tool_use pattern for structured output (tool_choice forced to extract tool)
- LLM extraction runs outside DB session scope to avoid holding locks during potentially slow API calls
- Existing non-rejected topics passed to LLM prompt for cross-debate semantic deduplication

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing openai and anthropic packages**
- **Found during:** Task 1 (extractor module creation)
- **Issue:** Neither openai nor anthropic Python packages were installed in the project venv
- **Fix:** Installed both packages via pip in .venv
- **Files modified:** None (runtime dependency only)
- **Verification:** Import succeeds for both packages
- **Committed in:** N/A (pip install, not code change)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential for LLM client functionality. No scope creep.

## Issues Encountered
None beyond the missing pip packages.

## User Setup Required

External LLM API key required. Users must set `LLM_API_KEY` in their `.env` file:
- For OpenAI: Get key from https://platform.openai.com/api-keys
- For Anthropic: Get key from Anthropic Console API keys
- Set `LLM_PROVIDER=openai` (default) or `LLM_PROVIDER=anthropic`
- Set `LLM_MODEL` to desired model (default: gpt-4o-mini)

## Next Phase Readiness
- Extraction pipeline ready for Plan 03 (topic deduplication and matching)
- analyze_debate returns structured DebateAnalysis with topics for cross-debate comparison
- NLPResult tracking enables Plan 04 dashboard queries

---
*Phase: 03-nlp-analysis-pipeline*
*Completed: 2026-04-12*
