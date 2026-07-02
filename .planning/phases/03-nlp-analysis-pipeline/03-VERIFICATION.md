---
phase: 03-nlp-analysis-pipeline
verified: 2026-04-12T20:00:00Z
status: human_needed
score: 5/5 must-haves verified
human_verification:
  - test: "Topic refinement UI: accept, reject, rename topics via HTMX"
    expected: "Clicking Accept updates topic card to green 'accepted' badge with no action buttons. Clicking Reject removes card from DOM. Typing new name and clicking Rename updates card with new name. All updates occur without page reload."
    why_human: "Plan 04 Task 3 was marked 'Auto-approved checkpoint' in the summary — no human has confirmed the HTMX interactions work end-to-end in a live browser session."
  - test: "Stance display on topic refinement page"
    expected: "Each topic card shows a table of speaker stances with Speaker column (PARKER/CALLER label), Stance column (SUPPORTS/OPPOSES/QUALIFIED/DEFLECTS), Confidence meter (HTML meter element), and Evidence text."
    why_human: "Visual rendering of confidence meter and CSS label classes requires browser verification."
  - test: "Cross-debate topic matches page: confirm and reject via HTMX"
    expected: "Suggested matches show two topic names with their debate titles and a similarity percentage. Clicking Confirm updates match card to show green 'confirmed' badge. Clicking Reject removes card. Both update in-place without page reload."
    why_human: "HTMX outerHTML swap behavior on match cards requires live browser verification."
  - test: "Navigation bar contains working Topic Matches link"
    expected: "Every page shows a 'Topic Matches' link in the nav bar that navigates to /topic-matches."
    why_human: "Link presence in base.html verified programmatically; correct rendering and clickability requires browser check."
---

# Phase 3: NLP Analysis Pipeline Verification Report

**Phase Goal:** Extract structured analysis from reviewed transcripts — topics, keywords, stance, frequency.
**Verified:** 2026-04-12T20:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | System generates keyword and phrase lists per speaker per reviewed debate with domain-specific stopword filtering | VERIFIED | `Keyword` model in models.py (phrase, speaker, count fields); `filter_stopwords` called in `extract_analysis` before storage; `DEBATE_STOPWORDS` set has 30+ entries in stopwords.py |
| 2 | System suggests topics per debate that a human can accept, reject, rename, or merge | VERIFIED | `Topic` model with status field (suggested/accepted/rejected/renamed/merged); routes at `/api/topics/{id}/accept`, `/reject`, `/rename`; topic_card.html renders HTMX action buttons for suggested topics |
| 3 | System classifies stance per speaker per topic with confidence scores | VERIFIED | `Stance` model (speaker, label, confidence, evidence); two-pass extraction in extractor.py calls `extract_stances` with topic list from Pass 1; stance_row.html renders confidence as HTML meter element |
| 4 | System produces frequency counts for phrases and keywords across all approved debates | VERIFIED | `get_keyword_frequencies` in crud.py uses `func.sum(Keyword.count).group_by(Keyword.phrase)` with optional speaker filter; cross-debate aggregation is real SQL, not static |
| 5 | System identifies matching topics across different debates enabling cross-debate comparison | VERIFIED | `find_matching_topics` in embeddings.py computes pairwise cosine similarity matrix via sentence-transformers; `create_topic_matches` stores `TopicMatch` rows with status="suggested"; `/topic-matches` route resolves and displays them |

**Score: 5/5 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/parker/models.py` | Topic, Stance, Keyword, TopicMatch, NLPResult, NLPStatus, StanceLabel | VERIFIED | All 5 table classes and 2 enums present; all fields match plan spec; existing Debate/Utterance/ReviewStatus unchanged |
| `src/parker/config.py` | LLM and embedding config fields | VERIFIED | `llm_provider`, `llm_api_key`, `llm_model`, `llm_max_tokens`, `embedding_model`, `topic_similarity_threshold` all confirmed present with correct defaults |
| `src/parker/nlp/__init__.py` | NLP package init | VERIFIED | File created; package importable |
| `src/parker/nlp/schemas.py` | Pydantic response models for LLM structured output | VERIFIED | `StanceLabel`, `ExtractedKeyword`, `ExtractedTopic`, `ExtractedStance`, `KeywordTopicExtraction`, `StanceExtraction`, `DebateAnalysis` all present |
| `src/parker/nlp/stopwords.py` | Debate-specific stopword filtering | VERIFIED | `DEBATE_STOPWORDS` set with 30+ entries; `filter_stopwords()` and `is_stopword()` functions present |
| `src/parker/nlp/prompts.py` | System prompts and transcript formatter | VERIFIED | `KEYWORD_TOPIC_SYSTEM_PROMPT`, `STANCE_SYSTEM_PROMPT`, `format_transcript_for_llm`, `build_keyword_topic_messages`, `build_stance_messages` all present and substantive |
| `src/parker/nlp/extractor.py` | LLM client, two-pass extraction, storage | VERIFIED | `get_llm_client`, `call_llm`, `extract_keywords_and_topics`, `extract_stances`, `extract_analysis`, `store_analysis` all present; dual OpenAI/Anthropic support implemented |
| `src/parker/nlp/embeddings.py` | Topic embedding generation and similarity matching | VERIFIED | `_model` singleton, `_get_model`, `generate_embedding`, `compute_cosine_similarity`, `embed_topic`, `store_topic_embedding`, `get_topic_embedding`, `find_matching_topics`, `create_topic_matches` all present |
| `src/parker/crud.py` | 13 NLP CRUD functions and frequency aggregation | VERIFIED | All 13 functions present: `get_nlp_result`, `create_or_update_nlp_result`, `get_topics_for_debate`, `get_all_active_topics`, `update_topic_status`, `get_stances_for_debate`, `get_stances_for_topic`, `get_keywords_for_debate`, `get_keyword_frequencies`, `get_topic_matches`, `update_topic_match_status`, `delete_nlp_results_for_debate`; `func` imported from sqlmodel |
| `src/parker/pipeline.py` | `analyze_debate` orchestrator | VERIFIED | `analyze_debate(engine, youtube_id, settings, force)` present; checks `is_debate_nlp_ready`; idempotency guard for completed results; calls `extract_analysis` and `store_analysis`; stores failed NLPResult on exception |
| `src/parker/cli.py` | `parker analyze` CLI command | VERIFIED | `analyze` command with `--youtube-id`, `--all`, `--force` options; API key guard; single and batch modes; imports `analyze_debate` and `get_nlp_ready_debates` from pipeline |
| `src/parker/web/routes.py` | 8 topic refinement and matching routes | VERIFIED | All 8 routes registered: `/videos/{id}/topics`, `/api/topics/{id}/accept`, `/api/topics/{id}/reject`, `/api/topics/{id}/rename`, `/topic-matches`, `/api/topic-matches/{id}/confirm`, `/api/topic-matches/{id}/reject`; imports `Topic, Stance, Keyword, TopicMatch, NLPResult, Debate` from models |
| `src/parker/web/templates/topics.html` | Topic refinement page | VERIFIED | Extends base.html; NLP status guard message; topic loop with `{% include "partials/topic_card.html" %}`; keyword table with Phrase/Speaker/Count columns |
| `src/parker/web/templates/topic_matches.html` | Cross-debate matching page | VERIFIED | Extends base.html; suggested and confirmed sections; `{% include "partials/match_card.html" %}` |
| `src/parker/web/templates/partials/topic_card.html` | Topic card with HTMX actions | VERIFIED | `id="topic-{{ topic.id }}"` present; `hx-post` for accept/reject/rename; stance table with `{% include "partials/stance_row.html" %}`; action buttons only shown when `topic.status == "suggested"` |
| `src/parker/web/templates/partials/stance_row.html` | Stance display row | VERIFIED | Speaker label with parker/caller CSS class; `<strong>{{ stance.label }}</strong>`; `<meter>` element for confidence; evidence text |
| `src/parker/web/templates/partials/match_card.html` | Match card with confirm/reject | VERIFIED | `id="match-{{ item.match.id }}"` present; `hx-post` for confirm/reject; topic names, debate titles, similarity percentage displayed |
| `src/parker/web/templates/base.html` | Navigation link to topic matches | VERIFIED | `<a href="/topic-matches">Topic Matches</a>` confirmed at line 17 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `nlp/schemas.py` | `models.py` | `StanceLabel` enum shared (layer-separated) | VERIFIED | Both files define `StanceLabel` independently by design (Pydantic vs SQLModel layer separation — documented in 03-01-SUMMARY decisions) |
| `nlp/extractor.py` | `nlp/schemas.py` | `KeywordTopicExtraction`, `StanceExtraction`, `DebateAnalysis` imported | VERIFIED | Lines 21-25 of extractor.py import all three schema classes |
| `nlp/extractor.py` | `nlp/stopwords.py` | `filter_stopwords` imported and applied | VERIFIED | Line 26 imports `filter_stopwords`; line 183-186 applies it to keyword list before combining into `DebateAnalysis` |
| `nlp/extractor.py` | `models.py` | Stores `Keyword`, `Topic`, `Stance`, `NLPResult` rows | VERIFIED | `store_analysis` creates all 4 model instances; `session.flush()` used to get Topic IDs for Stance foreign keys |
| `pipeline.py` | `nlp/extractor.py` | `analyze_debate` calls `extract_analysis` and `store_analysis` | VERIFIED | Lines 189, 223, 238 of pipeline.py import and call both functions |
| `cli.py` | `pipeline.py` | `analyze` command calls `analyze_debate` | VERIFIED | Line 117 imports `analyze_debate as run_analysis`; called at lines 130 and 144 |
| `web/routes.py` | `crud.py` | Routes call NLP CRUD functions | VERIFIED | `topic_refinement` calls `get_nlp_result`, `get_topics_for_debate`, `get_stances_for_debate`, `get_keywords_for_debate`; accept/reject/rename call `update_topic_status`; matches page calls `get_topic_matches`, `update_topic_match_status` |
| `templates/topics.html` | `web/routes.py` | HTMX calls to `/api/topics/{id}/accept|reject|rename` | VERIFIED | `hx-post="/api/topics/{{ topic.id }}/accept"` etc. in topic_card.html; routes registered at those paths |
| `templates/topic_matches.html` | `web/routes.py` | HTMX calls to `/api/topic-matches/{id}/confirm|reject` | VERIFIED | `hx-post="/api/topic-matches/{{ item.match.id }}/confirm"` in match_card.html; routes registered |
| `nlp/embeddings.py` | `models.py` | Stores embeddings in `Topic.embedding_json`, creates `TopicMatch` rows | VERIFIED | `store_topic_embedding` writes to `topic.embedding_json`; `create_topic_matches` creates `TopicMatch(topic_a_id, topic_b_id, similarity, status="suggested")` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| NLPP-01 | 03-01, 03-02, 03-03 | System extracts keywords and phrases per speaker per debate | SATISFIED | `Keyword` model stores phrase/speaker/count; `extract_keywords_and_topics` in extractor.py; `get_keyword_frequencies` aggregates across debates; stopword filter applied |
| NLPP-02 | 03-01, 03-02, 03-04 | System extracts topics per debate (AI suggests, human refines) | SATISFIED | `Topic` model with status workflow (suggested→accepted/rejected/renamed/merged); LLM extraction via `KeywordTopicExtraction`; accept/reject/rename routes in routes.py; topic_card.html HTMX UI |
| NLPP-03 | 03-01, 03-02, 03-04 | System classifies stance per speaker per topic (SUPPORTS/OPPOSES/QUALIFIED/DEFLECTS) | SATISFIED | `Stance` model with label/confidence/evidence; `StanceExtraction` second-pass LLM call; `STANCE_SYSTEM_PROMPT` with domain-specific instructions; stance_row.html displays confidence meter |
| NLPP-04 | 03-01, 03-03 | System measures frequency of phrases, keywords, and ideas across debates | SATISFIED | `get_keyword_frequencies` uses `func.sum(Keyword.count).group_by(Keyword.phrase)` across all debates with optional speaker filter; keyword table on topics.html page |
| NLPP-05 | 03-01, 03-03, 03-04 | System matches topics across debates for cross-debate comparison | SATISFIED | `find_matching_topics` computes cosine similarity matrix via sentence-transformers; `create_topic_matches` creates `TopicMatch` rows above threshold; `/topic-matches` UI with confirm/reject workflow |

**Coverage: 5/5 requirements satisfied — 0 orphaned**

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `nlp/embeddings.py` | 86 | `return []` | Info | Valid early-return guard: triggered only when `new_topics` or `existing_topics` is empty — not a stub |

No blockers or warnings found. No TODO/FIXME/PLACEHOLDER/stub patterns in any Phase 3 files.

---

### Commit Verification

All 8 task commits from SUMMARYs verified present in git log:

| Commit | Plan | Description |
|--------|------|-------------|
| `200e7da` | 03-01 Task 1 | feat(03-01): add NLP data models and LLM config settings |
| `80fcbae` | 03-01 Task 2 | feat(03-01): create NLP package with Pydantic schemas and stopwords |
| `ecbf131` | 03-02 Task 1 | feat(03-02): add LLM prompts and two-pass extraction pipeline |
| `b7cc361` | 03-02 Task 2 | feat(03-02): add analyze_debate pipeline and parker analyze CLI command |
| `324d866` | 03-03 Task 1 | feat(03-03): add NLP CRUD operations and frequency aggregation queries |
| `d089c1a` | 03-03 Task 2 | feat(03-03): add topic embedding generation and cross-debate similarity matching |
| `c2d3d52` | 03-04 Task 1 | feat(03-04): add topic refinement and cross-debate matching web routes |
| `7cd8513` | 03-04 Task 2 | feat(03-04): create topic refinement and matching templates |

---

### Human Verification Required

All automated checks pass. The following items require live browser verification because Plan 04 Task 3 (the blocking human-verify checkpoint) was marked "Auto-approved checkpoint" in the summary without evidence of actual human testing.

#### 1. Topic Refinement HTMX Actions

**Test:** Start `parker serve`. Navigate to `/videos/{youtube_id}/topics` for a debate that has been analyzed. Click "Accept" on a suggested topic. Click "Reject" on another. Type a new name and click "Rename" on a third.

**Expected:** Accept updates card in-place with green "[accepted]" badge and removes action buttons. Reject removes card from DOM entirely. Rename updates card with new name and blue "[renamed]" badge. No page reload occurs for any action.

**Why human:** HTMX `hx-swap="outerHTML"` behavior, CSS badge rendering, and DOM removal require a browser to confirm.

#### 2. Stance Display Per Topic

**Test:** On the topics page for an analyzed debate, verify each topic card shows a stance table.

**Expected:** Table has Speaker / Stance / Confidence / Evidence columns. Speaker shows "PARKER" or "CALLER" with colored label. Stance shows one of SUPPORTS/OPPOSES/QUALIFIED/DEFLECTS in bold. Confidence shows an HTML meter element with a percentage.

**Why human:** CSS class rendering (`parker-label`, `caller-label`) and `<meter>` element display are visual.

#### 3. Cross-Debate Topic Matches HTMX Actions

**Test:** Navigate to `/topic-matches`. If no matches exist, run NLP analysis on a second approved debate first (`parker analyze --all`). Click "Confirm" on a suggested match. Click "Reject" on another.

**Expected:** Confirm updates card in-place with "[confirmed]" badge and hides action buttons. Reject removes card from DOM. Both occur without page reload.

**Why human:** HTMX outerHTML swap behavior requires browser verification.

#### 4. Navigation Bar

**Test:** On any page, verify the nav bar contains a clickable "Topic Matches" link.

**Expected:** Link is visible in the nav bar and navigates to `/topic-matches` when clicked.

**Why human:** Link is confirmed in base.html source; rendering and click behavior require browser check.

---

### Gaps Summary

No gaps found. All 5 observable truths are verified. All 18 required artifacts exist, are substantive, and are correctly wired. All 5 NLPP requirements are satisfied. The single open item is human verification of the HTMX-powered UI — the automated checks confirm the routes are registered, templates have correct HTMX attributes and targets, and CRUD functions are called correctly, but actual browser interaction was not human-verified during execution (Plan 04 Task 3 was auto-approved).

---

_Verified: 2026-04-12T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
