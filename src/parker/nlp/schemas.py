"""Pydantic schemas for LLM structured output responses."""

from enum import StrEnum

from pydantic import BaseModel, Field


class StanceLabel(StrEnum):
    SUPPORTS = "SUPPORTS"
    OPPOSES = "OPPOSES"
    QUALIFIED = "QUALIFIED"
    DEFLECTS = "DEFLECTS"


class ExtractedKeyword(BaseModel):
    phrase: str = Field(description="Keyword or notable phrase used by the speaker")
    speaker: str = Field(description="'parker' or 'caller'")
    count: int = Field(description="Approximate times used in this debate", ge=1)


class ExtractedTopic(BaseModel):
    name: str = Field(description="Short topic label, 3-8 words")
    description: str = Field(description="One-sentence topic description")


class ExtractedStance(BaseModel):
    topic: str = Field(description="Topic name this stance is about")
    speaker: str = Field(description="'parker' or 'caller'")
    stance: StanceLabel
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="0.9+ for explicit statements, 0.5-0.7 for inferred, below 0.5 for ambiguous",
    )
    evidence: str = Field(description="Brief quote or paraphrase supporting this classification")


class KeywordTopicExtraction(BaseModel):
    """First-pass extraction: keywords and topics from transcript."""
    keywords: list[ExtractedKeyword]
    topics: list[ExtractedTopic]


class StanceExtraction(BaseModel):
    """Second-pass extraction: stance per speaker per topic."""
    stances: list[ExtractedStance]


class DebateAnalysis(BaseModel):
    """Combined analysis result (for storage/convenience)."""
    keywords: list[ExtractedKeyword]
    topics: list[ExtractedTopic]
    stances: list[ExtractedStance]
