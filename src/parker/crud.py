from datetime import datetime

from sqlmodel import Session, delete, func, select

from parker.models import (
    Debate,
    Keyword,
    NLPResult,
    ReviewStatus,
    Stance,
    Topic,
    TopicMatch,
    Utterance,
    VideoStatus,
)


def create_debate(
    session: Session,
    youtube_id: str,
    title: str,
    url: str,
    duration_seconds: float | None = None,
    upload_date: str | None = None,
) -> Debate:
    debate = Debate(
        youtube_id=youtube_id,
        title=title,
        url=url,
        duration_seconds=duration_seconds,
        upload_date=upload_date,
    )
    session.add(debate)
    session.commit()
    session.refresh(debate)
    return debate


def get_debate_by_youtube_id(session: Session, youtube_id: str) -> Debate | None:
    statement = select(Debate).where(Debate.youtube_id == youtube_id)
    return session.exec(statement).first()


def update_debate_status(
    session: Session,
    youtube_id: str,
    status: VideoStatus,
    error_message: str | None = None,
    audio_path: str | None = None,
    raw_transcript_path: str | None = None,
) -> Debate | None:
    debate = get_debate_by_youtube_id(session, youtube_id)
    if debate is None:
        return None
    debate.status = status
    debate.updated_at = datetime.utcnow()
    if error_message is not None:
        debate.error_message = error_message
    if audio_path is not None:
        debate.audio_path = audio_path
    if raw_transcript_path is not None:
        debate.raw_transcript_path = raw_transcript_path
    session.add(debate)
    session.commit()
    session.refresh(debate)
    return debate


def get_debates_by_status(session: Session, status: VideoStatus) -> list[Debate]:
    statement = select(Debate).where(Debate.status == status)
    return list(session.exec(statement).all())


def get_all_debates(session: Session) -> list[Debate]:
    statement = select(Debate).order_by(Debate.created_at.desc())
    return list(session.exec(statement).all())


def reset_failed_debate(session: Session, youtube_id: str) -> Debate | None:
    debate = get_debate_by_youtube_id(session, youtube_id)
    if debate is None or debate.status != VideoStatus.FAILED:
        return None
    debate.status = VideoStatus.PENDING
    debate.error_message = None
    debate.updated_at = datetime.utcnow()
    session.add(debate)
    session.commit()
    session.refresh(debate)
    return debate


def get_utterances_for_debate(session: Session, debate_id: int) -> list[Utterance]:
    """Get all utterances for a debate, ordered by start_time."""
    statement = select(Utterance).where(Utterance.debate_id == debate_id).order_by(Utterance.start_time)
    return list(session.exec(statement).all())


def clear_utterances_for_debate(session: Session, debate_id: int) -> None:
    """Remove stored utterances for a debate before reprocessing."""
    session.exec(delete(Utterance).where(Utterance.debate_id == debate_id))
    session.commit()


def get_utterance_by_id(session: Session, utterance_id: int) -> Utterance | None:
    return session.get(Utterance, utterance_id)


def toggle_utterance_speaker(session: Session, utterance_id: int) -> Utterance | None:
    """Toggle speaker between 'parker' and 'caller'. Preserves original on first edit."""
    utterance = session.get(Utterance, utterance_id)
    if utterance is None:
        return None
    # Preserve original on first edit
    if utterance.original_speaker is None:
        utterance.original_speaker = utterance.speaker
    # Toggle
    utterance.speaker = "caller" if utterance.speaker == "parker" else "parker"
    utterance.edited_at = datetime.utcnow()
    session.add(utterance)
    session.commit()
    session.refresh(utterance)
    # Auto-transition debate to in_progress
    _auto_transition_review_status(session, utterance.debate_id)
    return utterance


def update_utterance_text(session: Session, utterance_id: int, new_text: str) -> Utterance | None:
    """Update utterance text. Preserves original on first edit."""
    utterance = session.get(Utterance, utterance_id)
    if utterance is None:
        return None
    # Preserve original on first edit
    if utterance.original_text is None:
        utterance.original_text = utterance.text
    utterance.text = new_text.strip()
    utterance.edited_at = datetime.utcnow()
    session.add(utterance)
    session.commit()
    session.refresh(utterance)
    # Auto-transition debate to in_progress
    _auto_transition_review_status(session, utterance.debate_id)
    return utterance


def approve_debate(session: Session, youtube_id: str) -> Debate | None:
    """Mark a debate as approved for NLP analysis."""
    debate = get_debate_by_youtube_id(session, youtube_id)
    if debate is None:
        return None
    debate.review_status = ReviewStatus.APPROVED
    debate.updated_at = datetime.utcnow()
    session.add(debate)
    session.commit()
    session.refresh(debate)
    return debate


def unapprove_debate(session: Session, youtube_id: str) -> Debate | None:
    """Revoke approval, returning debate to in_progress."""
    debate = get_debate_by_youtube_id(session, youtube_id)
    if debate is None:
        return None
    debate.review_status = ReviewStatus.IN_PROGRESS
    debate.updated_at = datetime.utcnow()
    session.add(debate)
    session.commit()
    session.refresh(debate)
    return debate


def get_approved_debates(session: Session) -> list[Debate]:
    """Get all debates with approved review status (for Phase 3 NLP gate)."""
    statement = select(Debate).where(Debate.review_status == ReviewStatus.APPROVED)
    return list(session.exec(statement).all())


def count_edits_for_debate(session: Session, debate_id: int) -> int:
    """Count utterances that have been edited for a debate."""
    statement = select(Utterance).where(
        Utterance.debate_id == debate_id,
        Utterance.edited_at.isnot(None),  # type: ignore[union-attr]
    )
    return len(list(session.exec(statement).all()))


def _auto_transition_review_status(session: Session, debate_id: int) -> None:
    """Auto-transition debate from UNREVIEWED to IN_PROGRESS on first edit."""
    debate = session.get(Debate, debate_id)
    if debate and debate.review_status == ReviewStatus.UNREVIEWED:
        debate.review_status = ReviewStatus.IN_PROGRESS
        debate.updated_at = datetime.utcnow()
        session.add(debate)
        session.commit()


# ---------------------------------------------------------------------------
# NLP Result CRUD
# ---------------------------------------------------------------------------


def get_nlp_result(session: Session, debate_id: int) -> NLPResult | None:
    """Get NLP analysis result for a debate."""
    statement = select(NLPResult).where(NLPResult.debate_id == debate_id)
    return session.exec(statement).first()


def create_or_update_nlp_result(
    session: Session,
    debate_id: int,
    status: str,
    raw_response_json: str | None = None,
    error_message: str | None = None,
) -> NLPResult:
    """Create or update NLP result for a debate. Replaces existing on re-analysis."""
    existing = get_nlp_result(session, debate_id)
    if existing:
        existing.status = status
        existing.raw_response_json = raw_response_json
        existing.error_message = error_message
        if status == "completed":
            existing.analyzed_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    result = NLPResult(
        debate_id=debate_id,
        status=status,
        raw_response_json=raw_response_json,
        error_message=error_message,
    )
    if status == "completed":
        result.analyzed_at = datetime.utcnow()
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


# ---------------------------------------------------------------------------
# Topic CRUD
# ---------------------------------------------------------------------------


def get_topics_for_debate(session: Session, debate_id: int) -> list[Topic]:
    """Get all topics for a debate, excluding rejected ones."""
    statement = select(Topic).where(Topic.debate_id == debate_id, Topic.status != "rejected").order_by(Topic.name)
    return list(session.exec(statement).all())


def get_all_active_topics(session: Session) -> list[Topic]:
    """Get all non-rejected topics across all debates."""
    statement = select(Topic).where(Topic.status != "rejected").order_by(Topic.name)
    return list(session.exec(statement).all())


def update_topic_status(
    session: Session,
    topic_id: int,
    status: str,
    new_name: str | None = None,
    merged_into_id: int | None = None,
) -> Topic | None:
    """Update topic status (accept, reject, rename, merge)."""
    topic = session.get(Topic, topic_id)
    if topic is None:
        return None
    topic.status = status
    if new_name is not None:
        topic.name = new_name
    if merged_into_id is not None:
        topic.merged_into_id = merged_into_id
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


# ---------------------------------------------------------------------------
# Stance CRUD
# ---------------------------------------------------------------------------


def get_stances_for_debate(session: Session, debate_id: int) -> list[Stance]:
    """Get all stances for a debate."""
    statement = select(Stance).where(Stance.debate_id == debate_id)
    return list(session.exec(statement).all())


def get_stances_for_topic(session: Session, topic_id: int) -> list[Stance]:
    """Get all stances across debates for a topic (for cross-debate comparison)."""
    statement = select(Stance).where(Stance.topic_id == topic_id)
    return list(session.exec(statement).all())


# ---------------------------------------------------------------------------
# Keyword CRUD and Frequency Aggregation
# ---------------------------------------------------------------------------


def get_keywords_for_debate(session: Session, debate_id: int) -> list[Keyword]:
    """Get all keywords for a debate."""
    statement = select(Keyword).where(Keyword.debate_id == debate_id).order_by(Keyword.count.desc())
    return list(session.exec(statement).all())


def get_keyword_frequencies(session: Session, speaker: str | None = None) -> list[tuple[str, int]]:
    """Get aggregate keyword/phrase frequencies across all debates.

    Returns list of (phrase, total_count) tuples sorted by frequency descending.
    Optionally filter by speaker ('parker' or 'caller').
    """
    statement = select(Keyword.phrase, func.sum(Keyword.count).label("total"))
    if speaker:
        statement = statement.where(Keyword.speaker == speaker)
    statement = statement.group_by(Keyword.phrase).order_by(func.sum(Keyword.count).desc())
    results = session.exec(statement).all()
    return [(row[0], row[1]) for row in results]


# ---------------------------------------------------------------------------
# TopicMatch CRUD
# ---------------------------------------------------------------------------


def get_topic_matches(session: Session, status: str | None = None) -> list[TopicMatch]:
    """Get topic matches, optionally filtered by status (suggested/confirmed/rejected)."""
    statement = select(TopicMatch)
    if status:
        statement = statement.where(TopicMatch.status == status)
    statement = statement.order_by(TopicMatch.similarity.desc())
    return list(session.exec(statement).all())


def update_topic_match_status(session: Session, match_id: int, status: str) -> TopicMatch | None:
    """Confirm or reject a suggested topic match."""
    match = session.get(TopicMatch, match_id)
    if match is None:
        return None
    match.status = status
    session.add(match)
    session.commit()
    session.refresh(match)
    return match


def delete_nlp_results_for_debate(session: Session, debate_id: int) -> None:
    """Delete all NLP results for a debate (for re-analysis)."""
    for model_class in [Stance, Keyword, Topic, NLPResult]:
        statement = select(model_class).where(model_class.debate_id == debate_id)
        for row in session.exec(statement).all():
            session.delete(row)
    session.commit()


# ---------------------------------------------------------------------------
# Public Dashboard CRUD
# ---------------------------------------------------------------------------


def get_public_debates(session: Session) -> list[Debate]:
    approved_ids = select(Debate.id).where(Debate.review_status == ReviewStatus.APPROVED)
    completed_nlp_ids = select(NLPResult.debate_id).where(NLPResult.status == "completed")
    statement = (
        select(Debate)
        .where(Debate.id.in_(approved_ids))
        .where(Debate.id.in_(completed_nlp_ids))
        .order_by(Debate.created_at.desc())
    )
    return list(session.exec(statement).all())


def get_topic_frequency(session: Session) -> list[tuple[str, int]]:
    statement = (
        select(Topic.name, func.count(func.distinct(Topic.debate_id)).label("debate_count"))
        .where(Topic.status != "rejected")
        .group_by(Topic.name)
        .order_by(func.count(func.distinct(Topic.debate_id)).desc())
    )
    results = session.exec(statement).all()
    return [(row[0], row[1]) for row in results]


def get_dashboard_stats(session: Session) -> dict:
    public_debates = get_public_debates(session)
    public_ids = [d.id for d in public_debates]

    if not public_ids:
        return {"total_debates": 0, "total_topics": 0, "total_keywords": 0}

    topic_count = session.exec(
        select(func.count()).select_from(Topic).where(Topic.debate_id.in_(public_ids)).where(Topic.status != "rejected")
    ).one()

    keyword_count = session.exec(
        select(func.count()).select_from(Keyword).where(Keyword.debate_id.in_(public_ids))
    ).one()

    return {
        "total_debates": len(public_debates),
        "total_topics": topic_count,
        "total_keywords": keyword_count,
    }


def get_speaker_stance_summary(session: Session, debate_id: int) -> dict[str, list[Stance]]:
    stances = get_stances_for_debate(session, debate_id)
    summary: dict[str, list[Stance]] = {}
    for stance in stances:
        summary.setdefault(stance.speaker, []).append(stance)
    return summary


def get_key_quotes(session: Session, debate_id: int, top_n: int = 5) -> list[Stance]:
    statement = (
        select(Stance)
        .where(Stance.debate_id == debate_id, Stance.evidence.isnot(None), Stance.evidence != "")  # type: ignore[union-attr]
        .order_by(Stance.confidence.desc())
        .limit(top_n)
    )
    return list(session.exec(statement).all())


def get_cross_debate_patterns(session: Session, speaker: str | None = None) -> list[dict]:
    topics = get_all_active_topics(session)
    topic_map: dict[str, list[Topic]] = {}
    for topic in topics:
        topic_map.setdefault(topic.name, []).append(topic)

    patterns = []
    for topic_name, topic_entries in sorted(topic_map.items()):
        debate_ids = {t.debate_id for t in topic_entries}
        if len(debate_ids) < 1:
            continue
        stance_dist: dict[str, dict[str, int]] = {}
        for topic_obj in topic_entries:
            stances = get_stances_for_topic(session, topic_obj.id)
            for s in stances:
                if speaker and s.speaker != speaker:
                    continue
                stance_dist.setdefault(s.speaker, {})
                stance_dist[s.speaker][s.label] = stance_dist[s.speaker].get(s.label, 0) + 1
        patterns.append(
            {
                "topic": topic_name,
                "debate_count": len(debate_ids),
                "stance_distribution": stance_dist,
            }
        )
    return patterns


def get_topic_stances_across_debates(session: Session, topic_name: str) -> list[dict]:
    topics = session.exec(select(Topic).where(Topic.name == topic_name, Topic.status != "rejected")).all()
    results = []
    for topic in topics:
        debate = session.get(Debate, topic.debate_id)
        if debate is None:
            continue
        stances = get_stances_for_topic(session, topic.id)
        for stance in stances:
            results.append(
                {
                    "debate_id": debate.id,
                    "debate_title": debate.title,
                    "debate_youtube_id": debate.youtube_id,
                    "debate_upload_date": debate.upload_date,
                    "speaker": stance.speaker,
                    "stance_label": stance.label,
                    "confidence": stance.confidence,
                    "evidence": stance.evidence,
                }
            )
    return results


def get_debates_filtered(
    session: Session,
    topic: str | None = None,
    speaker: str | None = None,
    keyword: str | None = None,
    stance: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Debate]:
    debate_ids: set[int] | None = None

    if topic:
        topic_debate_ids = set(
            row[0]
            for row in session.exec(
                select(Topic.debate_id).where(Topic.name == topic, Topic.status != "rejected")
            ).all()
        )
        debate_ids = topic_debate_ids

    if keyword:
        kw_debate_ids = set(
            row[0] for row in session.exec(select(Keyword.debate_id).where(Keyword.phrase == keyword)).all()
        )
        debate_ids = kw_debate_ids if debate_ids is None else debate_ids & kw_debate_ids

    if stance and speaker:
        stance_debate_ids = set(
            row[0]
            for row in session.exec(
                select(Stance.debate_id).where(Stance.label == stance, Stance.speaker == speaker)
            ).all()
        )
        debate_ids = stance_debate_ids if debate_ids is None else debate_ids & stance_debate_ids
    elif stance:
        stance_debate_ids = set(
            row[0] for row in session.exec(select(Stance.debate_id).where(Stance.label == stance)).all()
        )
        debate_ids = stance_debate_ids if debate_ids is None else debate_ids & stance_debate_ids
    elif speaker:
        speaker_debate_ids = set(
            row[0] for row in session.exec(select(Stance.debate_id).where(Stance.speaker == speaker)).all()
        )
        debate_ids = speaker_debate_ids if debate_ids is None else debate_ids & speaker_debate_ids

    statement = select(Debate).where(
        Debate.review_status == ReviewStatus.APPROVED,
        Debate.status == VideoStatus.COMPLETED,
    )
    if debate_ids is not None:
        statement = statement.where(Debate.id.in_(debate_ids))
    if date_from:
        statement = statement.where(Debate.upload_date >= date_from)
    if date_to:
        statement = statement.where(Debate.upload_date <= date_to)
    statement = statement.order_by(Debate.upload_date.desc())
    return list(session.exec(statement).all())


def search_utterances(session: Session, query: str, limit: int = 50) -> list[dict]:
    from sqlalchemy import text as sa_text

    escaped = query.replace('"', '""')
    fts_query = f'"{escaped}"'
    sql = sa_text("""
        SELECT
            u.id,
            u.text,
            u.speaker,
            u.start_time,
            u.end_time,
            u.debate_id,
            d.title AS debate_title,
            d.youtube_id,
            highlight(utterances_fts, 0, '<mark>', '</mark>') AS snippet
        FROM utterances_fts AS fts
        JOIN utterance u ON u.id = fts.rowid
        JOIN debate d ON d.id = u.debate_id
        WHERE utterances_fts MATCH :q
        ORDER BY rank
        LIMIT :lim
    """)
    rows = session.execute(sql, {"q": fts_query, "lim": limit}).fetchall()
    return [
        {
            "id": row.id,
            "text": row.text,
            "snippet": row.snippet,
            "speaker": row.speaker,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "debate_id": row.debate_id,
            "debate_title": row.debate_title,
            "youtube_id": row.youtube_id,
        }
        for row in rows
    ]
