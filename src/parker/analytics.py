from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import func, select

from parker.models import (
    Debate,
    Guest,
    ReviewStatus,
    Stance,
    Topic,
    TopicMatch,
    Utterance,
    VideoStatus,
)

if TYPE_CHECKING:
    from sqlmodel import Session


def get_dashboard_stats(session: Session) -> dict:
    total = session.exec(
        select(func.count()).select_from(Debate)
    ).one()

    approved = session.exec(
        select(func.count())
        .select_from(Debate)
        .where(Debate.review_status == ReviewStatus.APPROVED)
    ).one()

    total_hours_row = session.exec(
        select(func.sum(Debate.duration_seconds))
        .select_from(Debate)
    ).one()
    total_hours = round((total_hours_row or 0) / 3600, 1)

    unique_guests = session.exec(
        select(func.count()).select_from(Guest)
    ).one()

    completed = session.exec(
        select(func.count())
        .select_from(Debate)
        .where(Debate.status == VideoStatus.COMPLETED)
    ).one()

    completion_pct = round(completed / total * 100) if total > 0 else 0

    return {
        "total_debates": total,
        "approved_count": approved,
        "total_hours": total_hours,
        "unique_guests": unique_guests,
        "completion_pct": completion_pct,
    }


def get_topic_frequency(session: Session, limit: int = 10) -> list[tuple[str, int]]:
    rows = session.exec(
        select(Topic.name, func.count(func.distinct(Topic.debate_id)).label("cnt"))
        .where(Topic.status != "rejected")
        .group_by(Topic.name)
        .order_by(func.count(func.distinct(Topic.debate_id)).desc())
        .limit(limit)
    ).all()
    return [(r[0], r[1]) for r in rows]


def get_debate_timeline(session: Session) -> list[tuple[str, int]]:
    rows = session.exec(
        select(
            func.substr(Debate.upload_date, 1, 7).label("month"),
            func.count(),
        )
        .where(Debate.upload_date.isnot(None))
        .group_by("month")
        .order_by("month")
    ).all()
    return [(r[0], r[1]) for r in rows]


def get_recent_activity(session: Session, limit: int = 8) -> list[dict]:
    debates = session.exec(
        select(Debate)
        .order_by(Debate.updated_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "title": d.title,
            "youtube_id": d.youtube_id,
            "status": d.status.value,
            "review_status": d.review_status.value,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        }
        for d in debates
    ]


def detect_duplicate_topics(session: Session, threshold: float = 0.85) -> list[TopicMatch]:
    return list(
        session.exec(
            select(TopicMatch)
            .where(TopicMatch.similarity >= threshold, TopicMatch.status == "suggested")
            .order_by(TopicMatch.similarity.desc())
        ).all()
    )


def detect_unlinked_guests(session: Session) -> list[Debate]:
    caller_debate_ids = list(
        session.exec(
            select(func.distinct(Utterance.debate_id))
            .where(Utterance.speaker == "caller")
        ).all()
    )
    if not caller_debate_ids:
        return []
    caller_ids = set(r[0] for r in caller_debate_ids)
    return list(
        session.exec(
            select(Debate)
            .where(
                Debate.id.in_(caller_ids),
                Debate.guest_id.is_(None),
                Debate.review_status == ReviewStatus.APPROVED,
            )
        ).all()
    )


def detect_anomalies(session: Session) -> dict:
    failed = session.exec(
        select(func.count())
        .select_from(Debate)
        .where(Debate.status == VideoStatus.FAILED)
    ).one()

    empty = session.exec(
        select(func.count())
        .select_from(Debate)
        .where(
            Debate.id.notin_(
                select(Utterance.debate_id).where(Utterance.debate_id.isnot(None))
            ),
            Debate.status == VideoStatus.COMPLETED,
        )
    ).one()

    unreviewed = session.exec(
        select(func.count())
        .select_from(Debate)
        .where(
            Debate.review_status == ReviewStatus.UNREVIEWED,
            Debate.status == VideoStatus.COMPLETED,
        )
    ).one()

    return {
        "failed_pipelines": failed,
        "empty_transcripts": empty,
        "unreviewed_count": unreviewed,
    }


def auto_merge_topics(session: Session, threshold: float = 0.95) -> int:
    matches = detect_duplicate_topics(session, threshold=threshold)
    merged = 0
    for match in matches:
        topic_a = session.get(Topic, match.topic_a_id)
        topic_b = session.get(Topic, match.topic_b_id)
        if topic_a is None or topic_b is None:
            continue
        stances_for_b = session.exec(
            select(Stance).where(Stance.topic_id == topic_b.id)
        ).all()
        for stance in stances_for_b:
            stance.topic_id = topic_a.id
            session.add(stance)
        topic_b.merged_into_id = topic_a.id
        topic_b.status = "merged"
        session.add(topic_b)
        match.status = "confirmed"
        session.add(match)
        merged += 1
    if merged > 0:
        session.commit()
    return merged


def auto_link_guests(session: Session) -> int:
    unlinked = detect_unlinked_guests(session)
    if not unlinked:
        return 0
    guests = session.exec(select(Guest)).all()
    guest_names_lower = {g.name.lower(): g for g in guests}
    linked = 0
    for debate in unlinked:
        if debate.title.lower() in guest_names_lower:
            debate.guest_id = guest_names_lower[debate.title.lower()].id
        elif " - " in debate.title:
            guest_name = debate.title.split(" - ")[-1].strip()
            if guest_name.lower() in guest_names_lower:
                debate.guest_id = guest_names_lower[guest_name.lower()].id
                debate.updated_at = datetime.utcnow()
                session.add(debate)
                linked += 1
    if linked > 0:
        session.commit()
    return linked


def get_cleanup_inbox(session: Session) -> dict:
    all_matches = detect_duplicate_topics(session, threshold=0.85)
    ambiguous = [m for m in all_matches if m.similarity < 0.95]
    return {
        "ambiguous_topics": ambiguous,
        "unlinked_guests": detect_unlinked_guests(session),
        "anomalies": detect_anomalies(session),
    }
