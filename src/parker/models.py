import enum
from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class ReviewStatus(str, enum.Enum):
    UNREVIEWED = "unreviewed"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"


class VideoStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    DIARIZING = "diarizing"
    COMPLETED = "completed"
    FAILED = "failed"


class Utterance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: int = Field(foreign_key="debate.id", index=True)
    speaker: str
    speaker_raw: Optional[str] = None
    text: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None
    words_json: Optional[str] = None
    original_speaker: Optional[str] = None
    original_text: Optional[str] = None
    edited_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    debate: Optional["Debate"] = Relationship(back_populates="utterances")


class Debate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    youtube_id: str = Field(unique=True, index=True)
    title: str
    url: str
    duration_seconds: Optional[float] = None
    upload_date: Optional[str] = None
    status: VideoStatus = Field(default=VideoStatus.PENDING)
    error_message: Optional[str] = None
    audio_path: Optional[str] = None
    raw_transcript_path: Optional[str] = None
    schema_version: int = Field(default=1)
    review_status: ReviewStatus = Field(default=ReviewStatus.UNREVIEWED)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    utterances: List[Utterance] = Relationship(back_populates="debate")


class NLPStatus(str, enum.Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class StanceLabel(str, enum.Enum):
    SUPPORTS = "SUPPORTS"
    OPPOSES = "OPPOSES"
    QUALIFIED = "QUALIFIED"
    DEFLECTS = "DEFLECTS"


class Topic(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: int = Field(foreign_key="debate.id", index=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    status: str = Field(default="suggested")  # suggested, accepted, rejected, renamed, merged
    merged_into_id: Optional[int] = Field(default=None, foreign_key="topic.id")
    embedding_json: Optional[str] = None  # JSON array of floats for cross-debate matching
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Stance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: int = Field(foreign_key="debate.id", index=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    speaker: str  # "parker" or "caller"
    label: str  # SUPPORTS, OPPOSES, QUALIFIED, DEFLECTS (stored as string for SQLite compat)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Keyword(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: int = Field(foreign_key="debate.id", index=True)
    phrase: str = Field(index=True)
    speaker: str  # "parker" or "caller"
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
    status: str = Field(default="pending")  # pending, analyzing, completed, failed
    raw_response_json: Optional[str] = None  # Full LLM response for auditability
    error_message: Optional[str] = None
    analyzed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
