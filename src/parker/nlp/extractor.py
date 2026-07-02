"""LLM extraction orchestration for debate transcript analysis.

Supports OpenAI and Anthropic providers. Uses structured output (response_format
for OpenAI, tool_use for Anthropic) to get validated Pydantic models back.

Two-pass extraction:
  1. Keywords + Topics
  2. Stances (using topic list from pass 1)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from parker.nlp.prompts import build_keyword_topic_messages, build_stance_messages
from parker.nlp.schemas import (
    DebateAnalysis,
    KeywordTopicExtraction,
    StanceExtraction,
)
from parker.nlp.stopwords import filter_stopwords

if TYPE_CHECKING:
    from sqlmodel import Session

    from parker.config import Settings
    from parker.models import NLPResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM client helpers
# ---------------------------------------------------------------------------


def get_llm_client(settings: Settings):
    """Return an LLM client instance based on the configured provider.

    Returns an OpenAI client for provider="openai" or an Anthropic client
    for provider="anthropic".
    """
    if settings.llm_provider == "anthropic":
        from anthropic import Anthropic

        return Anthropic(api_key=settings.llm_api_key)

    # Default: OpenAI (also works for OpenAI-compatible endpoints)
    from openai import OpenAI

    return OpenAI(api_key=settings.llm_api_key)


def _call_llm_openai(
    messages: list[dict],
    response_model: type[BaseModel],
    settings: Settings,
) -> BaseModel:
    """Call the OpenAI API with structured output (beta parse endpoint)."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.llm_api_key)
    completion = client.beta.chat.completions.parse(
        model=settings.llm_model,
        messages=messages,
        response_format=response_model,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("OpenAI returned no parsed response")
    return parsed


def _call_llm_anthropic(
    messages: list[dict],
    response_model: type[BaseModel],
    settings: Settings,
) -> BaseModel:
    """Call the Anthropic API using tool_use pattern for structured output."""
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.llm_api_key)

    # Separate system message from user messages
    system_prompt = ""
    user_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        else:
            user_messages.append(msg)

    tool_schema = response_model.model_json_schema()
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        system=system_prompt,
        messages=user_messages,
        tools=[
            {
                "name": "extract",
                "description": f"Extract structured data as {response_model.__name__}",
                "input_schema": tool_schema,
            }
        ],
        tool_choice={"type": "tool", "name": "extract"},
    )

    # Find the tool_use content block
    for block in response.content:
        if block.type == "tool_use":
            return response_model.model_validate(block.input)

    raise ValueError("Anthropic returned no tool_use content block")


def call_llm(
    messages: list[dict],
    response_model: type[BaseModel],
    settings: Settings,
) -> BaseModel:
    """Unified LLM call dispatching to the configured provider."""
    if settings.llm_provider == "anthropic":
        return _call_llm_anthropic(messages, response_model, settings)
    return _call_llm_openai(messages, response_model, settings)


# ---------------------------------------------------------------------------
# Two-pass extraction
# ---------------------------------------------------------------------------


def extract_keywords_and_topics(
    transcript_text: str,
    existing_topics: list[str],
    settings: Settings,
) -> KeywordTopicExtraction:
    """Pass 1: Extract keywords and topics from a debate transcript."""
    messages = build_keyword_topic_messages(transcript_text, existing_topics)
    logger.info("Pass 1: Extracting keywords and topics (model=%s)", settings.llm_model)
    result = call_llm(messages, KeywordTopicExtraction, settings)
    logger.info(
        "Pass 1 complete: %d keywords, %d topics",
        len(result.keywords),
        len(result.topics),
    )
    return result


def extract_stances(
    transcript_text: str,
    topics: list[str],
    settings: Settings,
) -> StanceExtraction:
    """Pass 2: Classify stance per speaker per topic."""
    messages = build_stance_messages(transcript_text, topics)
    logger.info("Pass 2: Extracting stances for %d topics (model=%s)", len(topics), settings.llm_model)
    result = call_llm(messages, StanceExtraction, settings)
    logger.info("Pass 2 complete: %d stances", len(result.stances))
    return result


def extract_analysis(
    transcript_text: str,
    existing_topics: list[str],
    settings: Settings,
) -> DebateAnalysis:
    """Orchestrate both extraction passes and combine results.

    1. Extract keywords + topics (Pass 1)
    2. Extract stances using extracted topic names (Pass 2)
    3. Apply stopword filtering to keywords
    4. Combine into a single DebateAnalysis
    """
    # Pass 1
    kt_result = extract_keywords_and_topics(transcript_text, existing_topics, settings)

    # Apply stopword filtering to keyword phrases
    filtered_keywords = [
        kw
        for kw in kt_result.keywords
        if filter_stopwords([kw.phrase])  # Returns non-empty list if not a stopword
    ]
    logger.info(
        "Stopword filter: %d -> %d keywords",
        len(kt_result.keywords),
        len(filtered_keywords),
    )

    # Pass 2 — feed extracted topic names
    topic_names = [t.name for t in kt_result.topics]
    stance_result = extract_stances(transcript_text, topic_names, settings)

    return DebateAnalysis(
        keywords=filtered_keywords,
        topics=kt_result.topics,
        stances=stance_result.stances,
    )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def store_analysis(
    session: Session,
    debate_id: int,
    analysis: DebateAnalysis,
    raw_json: str,
) -> NLPResult:
    """Store extraction results in the database.

    Creates/updates:
      - NLPResult row (status=completed, raw_response_json for auditability)
      - Keyword rows for each extracted keyword
      - Topic rows for each extracted topic
      - Stance rows linked to their Topic by name
    """
    from sqlmodel import select

    from parker.models import Keyword, NLPResult, Stance, Topic

    # Upsert NLPResult
    existing = session.exec(
        select(NLPResult).where(NLPResult.debate_id == debate_id)
    ).first()
    if existing:
        existing.status = "completed"
        existing.raw_response_json = raw_json
        existing.error_message = None
        existing.analyzed_at = datetime.utcnow()
        session.add(existing)
        nlp_result = existing
    else:
        nlp_result = NLPResult(
            debate_id=debate_id,
            status="completed",
            raw_response_json=raw_json,
            analyzed_at=datetime.utcnow(),
        )
        session.add(nlp_result)

    # Store keywords
    for kw in analysis.keywords:
        session.add(
            Keyword(
                debate_id=debate_id,
                phrase=kw.phrase,
                speaker=kw.speaker,
                count=kw.count,
            )
        )

    # Store topics and build name->id map for stances
    topic_map: dict[str, int] = {}
    for t in analysis.topics:
        topic = Topic(
            debate_id=debate_id,
            name=t.name,
            description=t.description,
            status="suggested",
        )
        session.add(topic)
        session.flush()  # Get the ID assigned
        topic_map[t.name] = topic.id  # type: ignore[assignment]

    # Store stances
    for s in analysis.stances:
        topic_id = topic_map.get(s.topic)
        if topic_id is None:
            logger.warning("Stance references unknown topic '%s', skipping", s.topic)
            continue
        session.add(
            Stance(
                debate_id=debate_id,
                topic_id=topic_id,
                speaker=s.speaker,
                label=s.stance.value,
                confidence=s.confidence,
                evidence=s.evidence,
            )
        )

    session.commit()
    session.refresh(nlp_result)
    return nlp_result
