# Phase 3: NLP Analysis Pipeline - Research

**Researched:** 2026-04-12
**Domain:** LLM-based text extraction, structured outputs, embedding similarity, SQLModel data modeling
**Confidence:** HIGH

## Summary

Phase 3 transforms human-approved debate transcripts into structured analytical data: keywords, topics, stance classifications, frequency counts, and cross-debate topic matching. The decided approach uses LLM-based extraction (Claude or OpenAI API) with prompt engineering rather than traditional NLP libraries -- the right call for debate language where stance nuance and topic framing require contextual understanding that spaCy/NLTK cannot provide at this domain's complexity.

The core technical challenge is designing structured output prompts that reliably extract the four data types (keywords, topics, stances, frequencies) and storing results in SQLModel tables that integrate with the existing Debate/Utterance schema. Cross-debate topic matching adds a second technical dimension: embedding similarity computation between topic strings, stored locally and compared with cosine similarity.

**Primary recommendation:** Use the OpenAI Python SDK with structured outputs (Pydantic response models) for extraction, and `sentence-transformers` with `all-MiniLM-L6-v2` for topic embeddings. Both choices optimize for simplicity and local-first architecture at the project's small scale (dozens of debates).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- LLM-based extraction via prompt engineering (Claude or OpenAI API), not traditional NLP
- Flat list of topics (not hierarchical taxonomy)
- Hybrid seeded + extracted topic approach (seed from titles, extract from content)
- 4-category stance classification: SUPPORTS / OPPOSES / QUALIFIED / DEFLECTS
- Prompt-based LLM extraction for stance (not fine-tuned classifier)
- Stance includes confidence score (0.0-1.0)
- Stance is per-speaker per-topic per-debate
- Human refinement integrated into existing FastAPI + HTMX web interface
- AI suggests topics; user can accept, reject, rename, or merge
- No separate approval gate for NLP results -- topic refinement IS the quality control
- Embedding similarity for cross-debate topic matching with human confirmation
- LLM extracts keywords and notable phrases per speaker per debate
- Domain-specific stopword filtering for debate filler words
- Store raw LLM responses for auditability

### Claude's Discretion
- Exact LLM prompt design and structured output format
- Embedding model choice for cross-debate matching
- Batch processing strategy (all debates at once vs. incremental)
- Database schema for NLP result models (topics, stances, keywords tables)
- Error handling for LLM API failures

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| NLPP-01 | System extracts keywords and phrases per speaker per debate | LLM structured output with KeywordExtraction Pydantic model; domain stopword filter list |
| NLPP-02 | System extracts topics per debate (hybrid AI suggests, human refines) | LLM extraction prompt with seeded topics; Topic SQLModel + refinement UI routes |
| NLPP-03 | System classifies stance per speaker per topic (SUPPORTS/OPPOSES/QUALIFIED/DEFLECTS) | Stance Pydantic enum + confidence float; per-speaker per-topic per-debate granularity |
| NLPP-04 | System measures frequency of phrases, keywords, and ideas across debates | SQL aggregation queries over Keyword table; cross-debate counting |
| NLPP-05 | System matches topics across debates for cross-debate comparison | sentence-transformers embeddings + cosine similarity; TopicMatch model with human confirm/reject |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openai | 2.31.0 | LLM API client for structured extraction | Best structured output support (Pydantic models + `response_format`); works with OpenAI and compatible APIs |
| sentence-transformers | 5.4.0 | Local embedding generation for topic matching | Runs locally, no API cost, good quality for short text similarity |
| sqlmodel | 0.0.22 | Database models for NLP results | Already used project-wide; extends existing Debate/Utterance schema |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | 2.4.3 | Cosine similarity computation | Already installed; needed for embedding vector math |
| pydantic | 2.x | Structured output schemas for LLM responses | Already installed; defines extraction response models |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| openai SDK | anthropic SDK (0.94.0) | Anthropic has structured outputs too (via `output_config`); OpenAI's is more mature and has wider compatible-API ecosystem. Either works -- choose based on which API key the user has. |
| sentence-transformers | OpenAI text-embedding-3-small | API-based, better quality, but adds API cost and dependency. At dozens of topics, local is simpler. |
| all-MiniLM-L6-v2 | nomic-embed-text-v1.5 | Newer and better benchmarks, but MiniLM is sufficient for comparing short topic strings (5-20 words). Overkill to optimize here. |

**Installation:**
```bash
pip install "openai>=2.31.0" "sentence-transformers>=5.0.0"
```

**Note on API choice:** The CONTEXT.md says "Claude or OpenAI API." The implementation should use a thin abstraction layer so the user can configure either. The `openai` SDK is recommended as the primary because:
1. OpenAI structured outputs with Pydantic are the most battle-tested
2. Many Claude-compatible proxies speak the OpenAI protocol
3. The Anthropic SDK also works well if the user prefers Claude

The config should accept `llm_provider` (openai/anthropic), `llm_api_key`, and `llm_model` settings.

## Architecture Patterns

### Recommended Project Structure
```
src/parker/
├── models.py          # Add Topic, Stance, Keyword, TopicMatch, NLPResult models
├── nlp/
│   ├── __init__.py
│   ├── schemas.py     # Pydantic response models for LLM structured output
│   ├── prompts.py     # Prompt templates for extraction
│   ├── extractor.py   # LLM client wrapper + extraction orchestration
│   ├── embeddings.py  # Topic embedding generation + similarity
│   └── stopwords.py   # Domain-specific debate stopword list
├── crud.py            # Extend with NLP CRUD operations
├── pipeline.py        # Extend with analyze_debate() orchestrator
├── cli.py             # Add `parker analyze` command
└── web/
    ├── routes.py      # Add topic refinement routes
    └── templates/
        ├── topics.html           # Topic refinement page
        ├── partials/
        │   ├── topic_card.html   # Single topic with accept/reject/rename
        │   ├── stance_row.html   # Stance display per speaker per topic
        │   └── match_card.html   # Cross-debate match suggestion
        └── topic_matches.html    # Cross-debate matching UI
```

### Pattern 1: LLM Structured Extraction with Pydantic
**What:** Define Pydantic models for expected LLM output, use SDK's structured output feature to guarantee schema compliance.
**When to use:** Every LLM extraction call in this phase.
**Example:**
```python
from pydantic import BaseModel, Field
from enum import Enum

class StanceLabel(str, Enum):
    SUPPORTS = "SUPPORTS"
    OPPOSES = "OPPOSES"
    QUALIFIED = "QUALIFIED"
    DEFLECTS = "DEFLECTS"

class ExtractedKeyword(BaseModel):
    phrase: str = Field(description="Keyword or notable phrase")
    speaker: str = Field(description="'parker' or 'caller'")
    count: int = Field(description="Times used in this debate", ge=1)

class ExtractedTopic(BaseModel):
    name: str = Field(description="Short topic label, 3-8 words")
    description: str = Field(description="One-sentence topic description")
    
class ExtractedStance(BaseModel):
    topic: str = Field(description="Topic name this stance is about")
    speaker: str = Field(description="'parker' or 'caller'")
    stance: StanceLabel
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(description="Brief quote or paraphrase supporting this classification")

class DebateAnalysis(BaseModel):
    keywords: list[ExtractedKeyword]
    topics: list[ExtractedTopic]
    stances: list[ExtractedStance]
```

### Pattern 2: OpenAI Structured Output Call
**What:** Use `client.chat.completions.create()` with `response_format` pointing to Pydantic model.
**When to use:** All extraction calls.
**Example:**
```python
from openai import OpenAI

client = OpenAI(api_key=settings.llm_api_key)

completion = client.beta.chat.completions.parse(
    model=settings.llm_model,  # e.g. "gpt-4o-mini"
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": transcript_text},
    ],
    response_format=DebateAnalysis,
)

result: DebateAnalysis = completion.choices[0].message.parsed
```

### Pattern 3: Anthropic Structured Output (Alternative)
**What:** Use Anthropic's `messages.create()` with tool_use or native structured outputs.
**When to use:** If user configures `llm_provider=anthropic`.
**Example:**
```python
from anthropic import Anthropic

client = Anthropic(api_key=settings.llm_api_key)

response = client.messages.create(
    model=settings.llm_model,  # e.g. "claude-sonnet-4-5-20250514"
    max_tokens=4096,
    messages=[{"role": "user", "content": transcript_text}],
    system=SYSTEM_PROMPT,
    tools=[{
        "name": "analyze_debate",
        "description": "Extract structured analysis from debate transcript",
        "input_schema": DebateAnalysis.model_json_schema(),
    }],
    tool_choice={"type": "tool", "name": "analyze_debate"},
)
# Parse tool_use block from response
```

### Pattern 4: Incremental Processing with Idempotency
**What:** Process one debate at a time, skip already-analyzed debates, store raw responses.
**When to use:** The `parker analyze` CLI command and any batch processing.
**Example:**
```python
def analyze_debate(engine, debate_id: int, force: bool = False) -> NLPResult:
    """Analyze a single approved debate. Idempotent unless force=True."""
    with get_session(engine) as session:
        existing = get_nlp_result(session, debate_id)
        if existing and not force:
            return existing
        
        debate = session.get(Debate, debate_id)
        utterances = get_utterances_for_debate(session, debate_id)
        
        # Build transcript text for LLM
        transcript = format_transcript_for_llm(debate, utterances)
        
        # Extract via LLM
        analysis = extract_analysis(transcript, existing_topics=get_all_topics(session))
        
        # Store results
        store_analysis(session, debate_id, analysis)
```

### Pattern 5: Topic Embedding + Cosine Similarity
**What:** Generate embeddings for topic names+descriptions, compute pairwise similarity for cross-debate matching.
**When to use:** After topics exist for 2+ debates.
**Example:**
```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")

def compute_topic_similarity(topic_a: str, topic_b: str) -> float:
    embeddings = model.encode([topic_a, topic_b])
    similarity = np.dot(embeddings[0], embeddings[1]) / (
        np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
    )
    return float(similarity)

def find_matching_topics(new_topics: list[str], existing_topics: list[str], threshold: float = 0.7):
    """Find potential matches above similarity threshold."""
    new_emb = model.encode(new_topics)
    existing_emb = model.encode(existing_topics)
    # Compute pairwise cosine similarity matrix
    similarities = np.dot(new_emb, existing_emb.T) / (
        np.linalg.norm(new_emb, axis=1, keepdims=True) 
        * np.linalg.norm(existing_emb, axis=1, keepdims=True).T
    )
    matches = []
    for i, new_topic in enumerate(new_topics):
        for j, existing_topic in enumerate(existing_topics):
            if similarities[i][j] >= threshold:
                matches.append((new_topic, existing_topic, float(similarities[i][j])))
    return matches
```

### Anti-Patterns to Avoid
- **Processing unapproved debates:** Always gate on `review_status == APPROVED`. The `get_nlp_ready_debates()` function already exists -- use it.
- **Monolithic extraction prompt:** Don't try to extract keywords + topics + stances in one massive prompt. Split into two passes: (1) keywords + topics, (2) stances (which need the topic list as input).
- **Storing only processed results:** Always store the raw LLM response JSON for auditability. If extraction logic changes, you can re-parse without re-calling the API.
- **Hardcoding the LLM provider:** Abstract behind a simple interface so switching between OpenAI and Anthropic is a config change.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema enforcement from LLM | Regex parsing of freeform LLM text | OpenAI structured outputs / Anthropic tool_use | Schema violations cause silent data corruption; structured outputs guarantee compliance |
| Embedding generation | Custom word2vec or TF-IDF vectors | sentence-transformers | Pre-trained models handle semantic meaning; TF-IDF misses synonyms |
| Cosine similarity | Manual dot product loops | numpy vectorized operations | Correct, fast, handles edge cases (zero vectors) |
| Stopword management | Inline hardcoded lists | Dedicated stopwords.py module with debate-specific terms | Needs iteration; separate module makes it easy to update |
| Database migrations | Manual ALTER TABLE | SQLModel metadata.create_all() for new tables | Project uses this pattern already; SQLite handles additive schema changes |

**Key insight:** The LLM does the hard NLP work (understanding debate context, stance nuance, topic framing). Our code is orchestration and storage -- keep it thin.

## Common Pitfalls

### Pitfall 1: Token Limits on Long Transcripts
**What goes wrong:** A 2-hour debate transcript can be 30k+ tokens. Sending the full transcript in one API call may exceed context limits or produce degraded output at the tail end.
**Why it happens:** LLM attention degrades on very long inputs; also hits token limits.
**How to avoid:** Chunk transcripts into segments (e.g., 10-15 minute blocks or natural conversation breaks). Extract keywords/topics per chunk, then deduplicate. For stance classification, send the full topic list but only relevant transcript chunks.
**Warning signs:** Extraction quality drops for speakers who talk more in the second half of debates.

### Pitfall 2: Topic Drift Across Extraction Calls
**What goes wrong:** The LLM generates slightly different topic names for the same concept across different debates ("gun control" vs "gun regulation" vs "firearms policy").
**Why it happens:** Without context of existing topics, each extraction is independent.
**How to avoid:** Pass the list of existing topics to the extraction prompt. Instruct the LLM: "Reuse these existing topics when semantically equivalent. Only create new topics when no existing topic matches." This is the "hybrid seeded + extracted" approach from the decisions.
**Warning signs:** Topic list grows unboundedly with near-duplicates.

### Pitfall 3: Stance Confidence Miscalibration
**What goes wrong:** LLM confidence scores cluster at 0.8-0.9 for everything, making them useless for filtering.
**Why it happens:** LLMs tend to be overconfident in structured output fields.
**How to avoid:** Include calibration guidance in the prompt: "Use 0.9+ only when the speaker explicitly states their position. Use 0.5-0.7 when stance is inferred from context. Use below 0.5 when the evidence is ambiguous." Also, the human refinement UI makes confidence less critical -- humans verify anyway.
**Warning signs:** All confidence scores within a narrow band.

### Pitfall 4: Embedding Model Loading Latency
**What goes wrong:** First call to `SentenceTransformer("all-MiniLM-L6-v2")` downloads and loads the model, taking 5-30 seconds.
**Why it happens:** Model needs to be downloaded on first use and loaded into memory.
**How to avoid:** Load the model once at application startup (or lazily on first use with caching). Store the model instance in app state or a module-level singleton.
**Warning signs:** First topic matching request is very slow; subsequent ones are fast.

### Pitfall 5: SQLite Concurrent Write Conflicts
**What goes wrong:** If the web server and CLI `analyze` command run simultaneously, SQLite write conflicts occur.
**Why it happens:** SQLite has a single-writer lock.
**How to avoid:** This is not a real concern at this project's scale. The `analyze` command runs offline. If needed, use WAL mode (`PRAGMA journal_mode=WAL`) for better concurrency.
**Warning signs:** "database is locked" errors during analysis.

## Code Examples

### Database Models for NLP Results
```python
# In models.py - new models extending existing schema

class NLPStatus(str, enum.Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"

class Topic(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: int = Field(foreign_key="debate.id", index=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    status: str = Field(default="suggested")  # suggested, accepted, rejected, renamed, merged
    merged_into_id: Optional[int] = Field(default=None, foreign_key="topic.id")
    embedding_json: Optional[str] = None  # JSON array of floats
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Stance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: int = Field(foreign_key="debate.id", index=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    speaker: str  # "parker" or "caller"
    label: str  # SUPPORTS, OPPOSES, QUALIFIED, DEFLECTS
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Keyword(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: int = Field(foreign_key="debate.id", index=True)
    phrase: str = Field(index=True)
    speaker: str
    count: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TopicMatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    topic_a_id: int = Field(foreign_key="topic.id", index=True)
    topic_b_id: int = Field(foreign_key="topic.id", index=True)
    similarity: float
    status: str = Field(default="suggested")  # suggested, confirmed, rejected
    created_at: datetime = Field(default_factory=datetime.utcnow)

class NLPResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: int = Field(foreign_key="debate.id", unique=True, index=True)
    status: NLPStatus = Field(default=NLPStatus.PENDING)
    raw_response_json: Optional[str] = None  # Full LLM response for auditability
    error_message: Optional[str] = None
    analyzed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Config Extension
```python
# In config.py - add LLM settings
class Settings(BaseSettings):
    # ... existing settings ...
    llm_provider: str = "openai"  # "openai" or "anthropic"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"  # or "claude-sonnet-4-5-20250514"
    llm_max_tokens: int = 4096
    embedding_model: str = "all-MiniLM-L6-v2"
    topic_similarity_threshold: float = 0.7
```

### Domain Stopwords
```python
# In nlp/stopwords.py
DEBATE_STOPWORDS = {
    # Common debate filler
    "well", "look", "so", "right", "okay", "yeah", "yes", "no",
    "um", "uh", "like", "actually", "basically", "literally",
    "honestly", "clearly", "obviously", "absolutely",
    # Common debate transitions
    "let me", "hold on", "wait a minute", "the point is",
    "what im saying is", "what youre saying is",
    # Host/caller meta-language
    "thanks for calling", "next caller", "go ahead",
}

def filter_stopwords(keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw.lower().strip() not in DEBATE_STOPWORDS]
```

### CLI Command
```python
# In cli.py - add analyze command
@app.command()
def analyze(
    youtube_id: str = typer.Option(None, help="Analyze a specific debate"),
    all: bool = typer.Option(False, "--all", help="Analyze all approved debates"),
    force: bool = typer.Option(False, help="Re-analyze even if already done"),
) -> None:
    """Run NLP analysis on approved debates."""
    settings = get_settings()
    engine = get_engine(settings.db_path)
    init_db(engine)
    
    if youtube_id:
        if not is_debate_nlp_ready(engine, youtube_id):
            typer.echo(f"Debate {youtube_id} is not approved for analysis", err=True)
            raise typer.Exit(code=1)
        result = analyze_debate(engine, youtube_id, force=force)
        typer.echo(f"Analysis complete: {result.status.value}")
    elif all:
        debates = get_nlp_ready_debates(engine)
        typer.echo(f"Analyzing {len(debates)} approved debates...")
        for debate in debates:
            result = analyze_debate(engine, debate.youtube_id, force=force)
            typer.echo(f"  {debate.youtube_id}: {result.status.value}")
    else:
        typer.echo("Specify --youtube-id or --all", err=True)
        raise typer.Exit(code=1)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| spaCy/NLTK keyword extraction | LLM-based extraction with structured outputs | 2024-2025 | Far better contextual understanding; domain-specific nuance without training |
| Fine-tuned classifiers for stance | Prompt-based LLM classification | 2024-2025 | No training data needed; works out of the box at small scale |
| OpenAI JSON mode | OpenAI Structured Outputs (strict schema) | Aug 2024 | Guaranteed schema compliance vs. best-effort JSON |
| Anthropic tool_use for JSON | Anthropic native structured outputs | Nov 2025 | First-class `output_config` support, no tool workaround needed |
| TF-IDF for topic similarity | Dense embeddings (sentence-transformers) | 2022+ | Semantic meaning captured; synonyms handled correctly |

## Open Questions

1. **Which LLM API key does the user have?**
   - What we know: CONTEXT.md says "Claude or OpenAI API"
   - What's unclear: Which key is available, which model to default to
   - Recommendation: Support both via config. Default to OpenAI (`gpt-4o-mini`) as it has the most mature structured output support. Add `llm_provider` and `llm_api_key` to Settings.

2. **Optimal transcript chunking strategy**
   - What we know: Long debates may exceed token limits
   - What's unclear: Average transcript length for Parker's debates; whether single-pass works
   - Recommendation: Start with single-pass (full transcript). If a debate exceeds 100k characters, chunk by conversation turns (groups of 20-30 utterances with overlap). Test with real data first.

3. **Topic similarity threshold tuning**
   - What we know: Cosine similarity with MiniLM gives 0-1 scores
   - What's unclear: What threshold produces good matches without too many false positives
   - Recommendation: Default to 0.7, make configurable. The human confirmation step catches false positives, so slightly aggressive matching is okay.

## Sources

### Primary (HIGH confidence)
- [OpenAI Structured Outputs Guide](https://developers.openai.com/api/docs/guides/structured-outputs) - Pydantic response_format usage
- [Anthropic Structured Outputs Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) - Native structured output with output_config
- [sentence-transformers/all-MiniLM-L6-v2 on HuggingFace](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) - Model specs and usage

### Secondary (MEDIUM confidence)
- [Best Embedding Models for RAG 2026](https://blog.premai.io/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/) - Embedding model comparison and benchmarks
- [OpenAI Migration to Responses API](https://platform.openai.com/docs/guides/migrate-to-responses) - API evolution context

### Tertiary (LOW confidence)
- Embedding similarity threshold of 0.7 for topic matching -- needs validation with real debate data

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - OpenAI/Anthropic SDKs and sentence-transformers are well-documented, verified versions
- Architecture: HIGH - Follows existing project patterns (SQLModel, Typer CLI, FastAPI+HTMX), extends naturally
- Pitfalls: MEDIUM - Token limit and topic drift concerns are well-known; specific thresholds need real-data validation

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable domain, libraries are mature)
