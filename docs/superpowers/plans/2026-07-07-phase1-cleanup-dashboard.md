# Phase 1: Data Cleanup & Dashboard Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build automated data cleanup (topic dedup, guest linking, anomaly detection) and a rich sidebar-based dashboard with interactive charts and a cleanup admin page.

**Architecture:** New `analytics.py` module handles all stats aggregation and cleanup logic. A shared `_sidebar.html` partial is injected into every page. Dashboard rewrites the `/` route with Chart.js charts, KPI cards, and activity feed. Admin cleanup page (`/admin/cleanup`) provides a manual review inbox for ambiguous cases.

**Tech Stack:** Python 3.11, FastAPI, Jinja2, SQLModel/SQLAlchemy, Chart.js (CDN), no new Python deps.

---

### Task 1: Create `analytics.py` — stats aggregation functions

**Files:**
- Create: `src/parker/analytics.py`

- [ ] **Step 1: Write the file with dashboard stats, topic frequency, debate timeline**

```python
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import func, select

from parker.models import (
    Debate,
    Guest,
    ReviewStatus,
    Topic,
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
```

- [ ] **Step 2: Run the app to confirm no import errors**

```bash
.venv/bin/python -c "from parker.analytics import get_dashboard_stats; print('OK')"
```
Expected: `OK`

---

### Task 2: Create `test_analytics.py` — tests for aggregation functions

**Files:**
- Create: `tests/test_analytics.py`

- [ ] **Step 1: Write the test file**

```python
from parker.db import get_engine, init_db, get_session
from parker.analytics import (
    get_dashboard_stats,
    get_topic_frequency,
    get_debate_timeline,
    get_recent_activity,
    detect_duplicate_topics,
    detect_unlinked_guests,
    detect_anomalies,
    auto_merge_topics,
    auto_link_guests,
    get_cleanup_inbox,
)
from parker.crud import create_debate, create_guest, link_debate_to_guest
from parker.models import (
    Debate,
    Guest,
    Stance,
    Topic,
    TopicMatch,
    VideoStatus,
    ReviewStatus,
)
from sqlmodel import Session, select


def test_get_dashboard_stats_empty(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        stats = get_dashboard_stats(session)
    assert stats["total_debates"] == 0
    assert stats["total_hours"] == 0


def test_get_dashboard_stats_with_data(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(
            session,
            youtube_id="abc123",
            title="Test Debate 1",
            url="https://youtube.com/watch?v=abc123",
            duration_seconds=3600,
            upload_date="2026-01-15",
        )
        d1.status = VideoStatus.COMPLETED
        session.add(d1)
        d2 = create_debate(
            session,
            youtube_id="def456",
            title="Test Debate 2",
            url="https://youtube.com/watch?v=def456",
            duration_seconds=5400,
            upload_date="2026-02-20",
        )
        d2.status = VideoStatus.COMPLETED
        d2.review_status = ReviewStatus.APPROVED
        session.add(d2)
        create_guest(session, name="Caller One")
        session.commit()

    with get_session(engine) as session:
        stats = get_dashboard_stats(session)
    assert stats["total_debates"] == 2
    assert stats["approved_count"] == 1
    assert stats["total_hours"] == 2.5
    assert stats["unique_guests"] == 1
    assert stats["completion_pct"] == 100


def test_get_topic_frequency_empty(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        freq = get_topic_frequency(session)
    assert freq == []


def test_get_topic_frequency_with_topics(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "Debate 1", "https://youtube.com/watch?v=abc123")
        t1 = Topic(debate_id=d1.id, name="Immigration", status="suggested")
        t2 = Topic(debate_id=d1.id, name="Economy", status="suggested")
        session.add_all([t1, t2])
        session.commit()

    with get_session(engine) as session:
        freq = get_topic_frequency(session, limit=10)
    assert ("Immigration", 1) in freq
    assert ("Economy", 1) in freq


def test_get_debate_timeline(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        create_debate(session, "abc123", "Jan Debate", "https://youtube.com/watch?v=abc123", upload_date="2026-01-10")
        create_debate(session, "def456", "Jan Debate 2", "https://youtube.com/watch?v=def456", upload_date="2026-01-20")
        create_debate(session, "ghi789", "Feb Debate", "https://youtube.com/watch?v=ghi789", upload_date="2026-02-05")
        session.commit()

    with get_session(engine) as session:
        timeline = get_debate_timeline(session)
    assert len(timeline) == 2
    assert ("2026-01", 2) in timeline
    assert ("2026-02", 1) in timeline


def test_get_recent_activity(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        create_debate(session, "abc123", "Test Debate", "https://youtube.com/watch?v=abc123")
        session.commit()

    with get_session(engine) as session:
        activity = get_recent_activity(session, limit=5)
    assert len(activity) == 1
    assert activity[0]["title"] == "Test Debate"
    assert activity[0]["youtube_id"] == "abc123"


def test_detect_duplicate_topics(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "D1", "https://youtube.com/watch?v=abc123")
        d2 = create_debate(session, "def456", "D2", "https://youtube.com/watch?v=def456")
        t1 = Topic(debate_id=d1.id, name="Immigration", status="suggested")
        t2 = Topic(debate_id=d2.id, name="Immigration", status="suggested")
        session.add_all([t1, t2])
        session.flush()
        match = TopicMatch(topic_a_id=t1.id, topic_b_id=t2.id, similarity=0.92, status="suggested")
        session.add(match)
        session.commit()

    with get_session(engine) as session:
        dupes = detect_duplicate_topics(session, threshold=0.85)
    assert len(dupes) == 1
    assert dupes[0].similarity == 0.92


def test_detect_unlinked_guests(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    from parker.models import Utterance
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "Has Caller", "https://youtube.com/watch?v=abc123")
        d1.review_status = ReviewStatus.APPROVED
        session.add(d1)
        u = Utterance(debate_id=d1.id, speaker="caller", text="Hello", start_time=0, end_time=1)
        session.add(u)
        session.commit()

    with get_session(engine) as session:
        unlinked = detect_unlinked_guests(session)
    assert len(unlinked) == 1


def test_detect_unlinked_guests_none_when_linked(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    from parker.models import Utterance
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "Linked Guest", "https://youtube.com/watch?v=abc123")
        d1.review_status = ReviewStatus.APPROVED
        session.add(d1)
        u = Utterance(debate_id=d1.id, speaker="caller", text="Hello", start_time=0, end_time=1)
        session.add(u)
        guest = create_guest(session, name="Bob")
        d1.guest_id = guest.id
        session.add(d1)
        session.commit()

    with get_session(engine) as session:
        unlinked = detect_unlinked_guests(session)
    assert len(unlinked) == 0


def test_detect_anomalies(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "Failed", "https://youtube.com/watch?v=abc123")
        d1.status = VideoStatus.FAILED
        d1.error_message = "download error"
        d2 = create_debate(session, "def456", "Unreviewed", "https://youtube.com/watch?v=def456")
        d2.status = VideoStatus.COMPLETED
        d2.review_status = ReviewStatus.UNREVIEWED
        session.add_all([d1, d2])
        session.commit()

    with get_session(engine) as session:
        anomalies = detect_anomalies(session)
    assert anomalies["failed_pipelines"] == 1
    assert anomalies["unreviewed_count"] == 1


def test_auto_merge_topics(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "D1", "https://youtube.com/watch?v=abc123")
        d2 = create_debate(session, "def456", "D2", "https://youtube.com/watch?v=def456")
        t1 = Topic(debate_id=d1.id, name="Immigration", status="suggested")
        t2 = Topic(debate_id=d2.id, name="Immigration Policy", status="suggested")
        session.add_all([t1, t2])
        session.flush()
        s1 = Stance(debate_id=d1.id, topic_id=t1.id, speaker="parker", label="SUPPORTS", confidence=0.9)
        s2 = Stance(debate_id=d2.id, topic_id=t2.id, speaker="caller", label="OPPOSES", confidence=0.8)
        session.add_all([s1, s2])
        match = TopicMatch(topic_a_id=t1.id, topic_b_id=t2.id, similarity=0.96, status="suggested")
        session.add(match)
        session.commit()

    with get_session(engine) as session:
        count = auto_merge_topics(session, threshold=0.95)
    assert count == 1

    with get_session(engine) as session:
        match = session.get(TopicMatch, match.id)
        assert match.status == "confirmed"
        t2_after = session.get(Topic, t2.id)
        assert t2_after.merged_into_id == t1.id
        stances = session.exec(select(Stance).where(Stance.topic_id == t1.id)).all()
        assert len(stances) == 2


def test_auto_link_guests(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    from parker.models import Utterance
    with get_session(engine) as session:
        g = create_guest(session, name="Alice")
        d = create_debate(session, "abc123", "Alice Debate", "https://youtube.com/watch?v=abc123")
        d.review_status = ReviewStatus.APPROVED
        u = Utterance(debate_id=d.id, speaker="caller", text="Hi", start_time=0, end_time=1)
        session.add_all([d, u])
        session.commit()

    with get_session(engine) as session:
        count = auto_link_guests(session)
    assert count == 0


def test_get_cleanup_inbox(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "D1", "https://youtube.com/watch?v=abc123")
        d2 = create_debate(session, "def456", "D2", "https://youtube.com/watch?v=def456")
        t1 = Topic(debate_id=d1.id, name="Taxes", status="suggested")
        t2 = Topic(debate_id=d2.id, name="Tax Policy", status="suggested")
        session.add_all([t1, t2])
        session.flush()
        match = TopicMatch(topic_a_id=t1.id, topic_b_id=t2.id, similarity=0.88, status="suggested")
        session.add(match)
        session.commit()

    with get_session(engine) as session:
        inbox = get_cleanup_inbox(session)
    assert len(inbox["ambiguous_topics"]) == 1
    assert inbox["ambiguous_topics"][0].similarity == 0.88
```

- [ ] **Step 2: Run tests to verify they fail (module doesn't exist yet)**

```bash
.venv/bin/python -m pytest tests/test_analytics.py -v
```
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'parker.analytics'`

---

### Task 3: Add cleanup functions to `analytics.py`

**Files:**
- Modify: `src/parker/analytics.py`

- [ ] **Step 1: Append cleanup detection and auto-merge functions**

```python
# Append to end of src/parker/analytics.py (after the existing functions):

from parker.models import (
    Keyword,
    NLPResult,
    Stance,
    TopicMatch,
    Utterance,
)


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
```

- [ ] **Step 2: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_analytics.py -v
```
Expected: All tests PASS

---

### Task 4: Commit analytics module

```bash
git add src/parker/analytics.py tests/test_analytics.py
git commit -m "feat: add analytics module with dashboard stats and cleanup logic"
```

---

### Task 5: Add topic merge helpers to `crud.py`

**Files:**
- Modify: `src/parker/crud.py`

- [ ] **Step 1: Add merge and reject helper functions at end of crud.py**

```python
# Append before the last line of src/parker/crud.py


def merge_topic_match(session: Session, match_id: int) -> dict | None:
    match = session.get(TopicMatch, match_id)
    if match is None:
        return None
    topic_a = session.get(Topic, match.topic_a_id)
    topic_b = session.get(Topic, match.topic_b_id)
    if topic_a is None or topic_b is None:
        return None
    stances = session.exec(
        select(Stance).where(Stance.topic_id == topic_b.id)
    ).all()
    for stance in stances:
        stance.topic_id = topic_a.id
        session.add(stance)
    topic_b.merged_into_id = topic_a.id
    topic_b.status = "merged"
    session.add(topic_b)
    match.status = "confirmed"
    session.add(match)
    session.commit()
    return {
        "merged_from": topic_b.name,
        "merged_into": topic_a.name,
        "stances_moved": len(stances),
    }


def reject_topic_match(session: Session, match_id: int) -> bool:
    match = session.get(TopicMatch, match_id)
    if match is None:
        return False
    match.status = "rejected"
    session.add(match)
    session.commit()
    return True


def get_debate_by_id(session: Session, debate_id: int) -> Debate | None:
    return session.get(Debate, debate_id)
```

- [ ] **Step 2: Verify the module imports**

```bash
.venv/bin/python -c "from parker.crud import merge_topic_match, reject_topic_match; print('OK')"
```
Expected: `OK`

---

### Task 6: Add tests for merge helpers

**Files:**
- Modify: `tests/test_crud.py`

- [ ] **Step 1: Add test functions to end of test_crud.py**

```python
# Append to tests/test_crud.py

from parker.models import Topic, TopicMatch, Stance


def test_merge_topic_match(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "D1", "https://youtube.com/watch?v=abc123")
        d2 = create_debate(session, "def456", "D2", "https://youtube.com/watch?v=def456")
        t1 = Topic(debate_id=d1.id, name="Immigration", status="suggested")
        t2 = Topic(debate_id=d2.id, name="Immigration Policy", status="suggested")
        session.add_all([t1, t2])
        session.flush()
        s1 = Stance(debate_id=d1.id, topic_id=t1.id, speaker="parker", label="SUPPORTS", confidence=0.9)
        s2 = Stance(debate_id=d2.id, topic_id=t2.id, speaker="caller", label="OPPOSES", confidence=0.8)
        session.add_all([s1, s2])
        match = TopicMatch(topic_a_id=t1.id, topic_b_id=t2.id, similarity=0.96, status="suggested")
        session.add(match)
        session.commit()

    with get_session(engine) as session:
        result = merge_topic_match(session, match.id)
    assert result is not None
    assert result["stances_moved"] == 1
    assert result["merged_into"] == "Immigration"

    with get_session(engine) as session:
        match_after = session.get(TopicMatch, match.id)
        assert match_after.status == "confirmed"
        t2_after = session.get(Topic, t2.id)
        assert t2_after.merged_into_id == t1.id


def test_reject_topic_match(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "D1", "https://youtube.com/watch?v=abc123")
        d2 = create_debate(session, "def456", "D2", "https://youtube.com/watch?v=def456")
        t1 = Topic(debate_id=d1.id, name="Taxes", status="suggested")
        t2 = Topic(debate_id=d2.id, name="Tax Policy", status="suggested")
        session.add_all([t1, t2])
        session.flush()
        match = TopicMatch(topic_a_id=t1.id, topic_b_id=t2.id, similarity=0.88, status="suggested")
        session.add(match)
        session.commit()

    with get_session(engine) as session:
        result = reject_topic_match(session, match.id)
    assert result is True

    with get_session(engine) as session:
        match_after = session.get(TopicMatch, match.id)
        assert match_after.status == "rejected"
```

- [ ] **Step 2: Run the new tests**

```bash
.venv/bin/python -m pytest tests/test_crud.py::test_merge_topic_match tests/test_crud.py::test_reject_topic_match -v
```
Expected: 2 PASS

---

### Task 7: Commit crud helpers

```bash
git add src/parker/crud.py tests/test_crud.py
git commit -m "feat: add topic merge and reject helpers to CRUD layer"
```

---

### Task 8: Hook cleanup into pipeline post-analysis

**Files:**
- Modify: `src/parker/pipeline.py`

- [ ] **Step 1: Add post-analysis cleanup call**

At the end of `analyze_debate()` in `src/parker/pipeline.py`, after `return result` (line 265), wrap `store_analysis` call site to trigger cleanup. The function is at line 199-265.

Find line 265: `        return result`

Replace with:
```python
        # Post-analysis cleanup: auto-merge topics and link guests
        try:
            from parker.analytics import auto_link_guests, auto_merge_topics

            merged = auto_merge_topics(session, threshold=0.95)
            linked = auto_link_guests(session)
            if merged or linked:
                logger.info(
                    "Post-analysis cleanup: merged %d topics, linked %d guests",
                    merged,
                    linked,
                )
        except Exception as cleanup_err:
            logger.warning("Post-analysis cleanup failed (non-fatal): %s", cleanup_err)

        return result
```

Locate this by finding the last `return result` in the function body. The relevant section (lines 254-265) is:

```python
    # Store results
    with get_session(engine) as session:
        debate = get_debate_by_youtube_id(session, youtube_id)
        result = store_analysis(session, debate.id, analysis, raw_json)
        logger.info(
            "Analysis stored for %s: %d topics, %d keywords, %d stances",
            youtube_id,
            len(analysis.topics),
            len(analysis.keywords),
            len(analysis.stances),
        )
        return result
```

Replace the block with:

```python
    # Store results
    with get_session(engine) as session:
        debate = get_debate_by_youtube_id(session, youtube_id)
        result = store_analysis(session, debate.id, analysis, raw_json)
        logger.info(
            "Analysis stored for %s: %d topics, %d keywords, %d stances",
            youtube_id,
            len(analysis.topics),
            len(analysis.keywords),
            len(analysis.stances),
        )

        try:
            from parker.analytics import auto_link_guests, auto_merge_topics

            merged = auto_merge_topics(session, threshold=0.95)
            linked = auto_link_guests(session)
            if merged or linked:
                logger.info(
                    "Post-analysis cleanup: merged %d topics, linked %d guests",
                    merged,
                    linked,
                )
        except Exception as cleanup_err:
            logger.warning("Post-analysis cleanup failed (non-fatal): %s", cleanup_err)

        return result
```

- [ ] **Step 2: Verify import is valid**

```bash
.venv/bin/python -c "from parker.pipeline import analyze_debate; print('OK')"
```
Expected: `OK`

---

### Task 9: Commit pipeline hook

```bash
git add src/parker/pipeline.py
git commit -m "feat: run auto-cleanup after NLP analysis"
```

---

### Task 10: Create `_sidebar.html` partial

**Files:**
- Create: `src/parker/web/templates/_sidebar.html`

- [ ] **Step 1: Write the sidebar partial**

```html
<nav class="sidebar">
  <div class="sidebar-brand">
    <a href="/"><strong>Parker Debates</strong></a>
  </div>
  <ul class="sidebar-nav">
    {% set current = request.url.path.rstrip('/') %}
    <li><a href="/" class="{% if current == '' %}active{% endif %}">Dashboard</a></li>
    <li><a href="/debates" class="{% if current == '/debates' %}active{% endif %}">Debates</a></li>
    <li><a href="/patterns" class="{% if current == '/patterns' %}active{% endif %}">Patterns</a></li>
    <li><a href="/search" class="{% if current == '/search' %}active{% endif %}">Search</a></li>
  </ul>
  {% if cleanup_count is defined and cleanup_count > 0 %}
  <div class="sidebar-alert">
    <a href="/admin/cleanup">Cleanup: {{ cleanup_count }} items</a>
  </div>
  {% endif %}
  <div class="sidebar-footer">
    <a href="/admin/videos">Admin</a>
  </div>
</nav>
```

---

### Task 11: Rewrite `public_base.html` with sidebar layout

**Files:**
- Modify: `src/parker/web/templates/public_base.html`

- [ ] **Step 1: Rewrite the base template with sidebar**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Parker Debate Dashboard{% endblock %}</title>
    <meta name="description" content="{% block meta_description %}Explore analyzed debate topics, keywords, and patterns across Parker's debates.{% endblock %}">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <link rel="stylesheet" href="/static/style.css">
    <meta property="og:title" content="{% block og_title %}Parker Debate Dashboard{% endblock %}">
    <meta property="og:description" content="{% block og_description %}Explore analyzed debate topics, keywords, and patterns.{% endblock %}">
    <meta property="og:type" content="website">
    {% block extra_head %}{% endblock %}
</head>
<body class="layout-sidebar">
  {% block sidebar %}
    {% include "_sidebar.html" %}
  {% endblock %}
  <main class="main-content">
    {% block content %}{% endblock %}
  </main>
  {% block scripts %}{% endblock %}
</body>
</html>
```

---

### Task 12: Update `base.html` (admin template) with sidebar

**Files:**
- Modify: `src/parker/web/templates/base.html`

- [ ] **Step 1: Add sidebar and update admin nav**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Parker Debate Review{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
</head>
<body class="layout-sidebar">
  <nav class="sidebar">
    <div class="sidebar-brand">
      <a href="/admin/videos"><strong>Admin</strong></a>
    </div>
    <ul class="sidebar-nav">
      {% set current = request.url.path.rstrip('/') %}
      <li><a href="/admin/videos" class="{% if current == '/admin/videos' %}active{% endif %}">Videos</a></li>
      <li><a href="/admin/topic-matches" class="{% if current == '/admin/topic-matches' %}active{% endif %}">Topic Matches</a></li>
      <li><a href="/admin/cleanup" class="{% if current == '/admin/cleanup' %}active{% endif %}">Cleanup</a></li>
    </ul>
    <div class="sidebar-footer">
      <a href="/">Public</a>
    </div>
  </nav>
  <main class="main-content">
    {% block content %}{% endblock %}
  </main>
  {% block scripts %}{% endblock %}
</body>
</html>
```

---

### Task 13: Add sidebar CSS to `style.css`

**Files:**
- Modify: `src/parker/web/static/style.css`

- [ ] **Step 1: Read current CSS then append sidebar styles**

```bash
cat src/parker/web/static/style.css
```

- [ ] **Step 2: Append sidebar layout styles**

```css
/* Sidebar layout */
.layout-sidebar {
  display: flex;
  min-height: 100vh;
  padding: 0;
  margin: 0;
}

.sidebar {
  width: 220px;
  background: var(--pico-card-background-color, #1a1a2e);
  border-right: 1px solid var(--pico-card-border-color, #333);
  display: flex;
  flex-direction: column;
  padding: 1rem 0;
  flex-shrink: 0;
}

.sidebar-brand {
  padding: 0 1rem 1rem;
  border-bottom: 1px solid var(--pico-card-border-color, #333);
  margin-bottom: 0.5rem;
}

.sidebar-brand a {
  text-decoration: none;
  font-size: 1.1rem;
}

.sidebar-nav {
  list-style: none;
  padding: 0;
  margin: 0;
  flex: 1;
}

.sidebar-nav li a {
  display: block;
  padding: 0.5rem 1rem;
  text-decoration: none;
  color: var(--pico-color, #ccc);
  font-size: 0.9rem;
}

.sidebar-nav li a:hover {
  background: var(--pico-primary-hover-background, rgba(255,255,255,0.05));
}

.sidebar-nav li a.active {
  background: var(--pico-primary, #1095c1);
  color: var(--pico-primary-inverse, #fff);
  font-weight: 600;
}

.sidebar-alert {
  padding: 0.75rem 1rem;
  margin: 0.5rem 0;
  background: #fff3cd;
  border-radius: 4px;
  font-size: 0.8rem;
}

.sidebar-alert a {
  color: #856404;
  font-weight: 600;
}

.sidebar-footer {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--pico-card-border-color, #333);
  font-size: 0.8rem;
}

.main-content {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
}

/* Dashboard KPI cards */
.dashboard-kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.kpi-card {
  background: var(--pico-card-background-color);
  border: 1px solid var(--pico-card-border-color);
  border-radius: 8px;
  padding: 1rem;
  text-align: center;
}

.kpi-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--pico-primary, #1095c1);
}

.kpi-label {
  font-size: 0.8rem;
  color: var(--pico-muted-color, #888);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-top: 0.25rem;
}

.kpi-sub {
  font-size: 0.75rem;
  color: var(--pico-muted-color, #666);
  margin-top: 0.15rem;
}

/* Chart containers */
.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.chart-card {
  background: var(--pico-card-background-color);
  border: 1px solid var(--pico-card-border-color);
  border-radius: 8px;
  padding: 1rem;
}

.chart-card h3 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}

.chart-card canvas {
  max-height: 300px;
}

/* Info cards row */
.info-row {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.info-card {
  background: var(--pico-card-background-color);
  border: 1px solid var(--pico-card-border-color);
  border-radius: 8px;
  padding: 1rem;
}

.info-card h3 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}

.activity-item {
  font-size: 0.85rem;
  padding: 0.4rem 0;
  border-bottom: 1px solid var(--pico-card-border-color);
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-time {
  font-weight: 600;
  color: var(--pico-primary, #1095c1);
}

/* Cleanup page */
.cleanup-summary {
  background: var(--pico-card-background-color);
  border: 1px solid var(--pico-card-border-color);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.cleanup-section {
  margin-bottom: 2rem;
}

/* Responsive: stack sidebar on mobile */
@media (max-width: 768px) {
  .layout-sidebar {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
    padding: 0.5rem;
  }
  .sidebar-nav {
    display: flex;
    gap: 0.25rem;
  }
  .sidebar-brand, .sidebar-footer, .sidebar-alert {
    display: none;
  }
  .main-content {
    padding: 1rem;
  }
  .chart-row, .info-row {
    grid-template-columns: 1fr;
  }
}
```

---

### Task 14: Rewrite `dashboard.html` with KPI cards and charts

**Files:**
- Modify: `src/parker/web/templates/dashboard.html`

- [ ] **Step 1: Write the new dashboard template**

```html
{% extends "public_base.html" %}
{% block title %}Parker Debate Dashboard{% endblock %}
{% block og_title %}Parker Debate Dashboard{% endblock %}
{% block og_description %}{{ stats.total_debates }} debates analyzed, {{ stats.total_hours }} hours of content.{% endblock %}

{% block extra_head %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
{% endblock %}

{% block content %}
<hgroup>
  <h1>Dashboard</h1>
  <p>Overview of all analyzed Parker debates</p>
</hgroup>

<div class="dashboard-kpis">
  <div class="kpi-card">
    <div class="kpi-value">{{ stats.total_debates }}</div>
    <div class="kpi-label">Debates</div>
    <div class="kpi-sub">{{ stats.approved_count }} approved</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-value">{{ stats.total_hours }}</div>
    <div class="kpi-label">Content Hours</div>
    {% if stats.total_debates > 0 %}
    <div class="kpi-sub">{{ "%.1f"|format(stats.total_hours / stats.total_debates) }}h avg</div>
    {% endif %}
  </div>
  <div class="kpi-card">
    <div class="kpi-value">{{ stats.completion_pct }}%</div>
    <div class="kpi-label">Complete</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-value">{{ stats.unique_guests }}</div>
    <div class="kpi-label">Guests</div>
  </div>
</div>

<div class="chart-row">
  <div class="chart-card">
    <h3>Top Topics</h3>
    <canvas id="topicChart"></canvas>
  </div>
  <div class="chart-card">
    <h3>Debates Over Time</h3>
    <canvas id="timelineChart"></canvas>
  </div>
</div>

<div class="info-row">
  <div class="info-card">
    <h3>Cleanup Status</h3>
    {% if cleanup_count is defined and cleanup_count > 0 %}
    <p>{{ cleanup_count }} items need attention.</p>
    <a href="/admin/cleanup" role="button" class="contrast">Review Cleanup</a>
    {% else %}
    <p>All clean.</p>
    {% endif %}
    {% if cleanup_anomalies is defined %}
    <ul style="margin-top:0.5rem;font-size:0.85rem">
      <li>{{ cleanup_anomalies.failed_pipelines }} failed pipeline runs</li>
      <li>{{ cleanup_anomalies.unreviewed_count }} unreviewed debates</li>
      <li>{{ cleanup_anomalies.empty_transcripts }} debates with no utterances</li>
    </ul>
    {% endif %}
  </div>
  <div class="info-card">
    <h3>Recent Activity</h3>
    {% if recent_activity %}
    {% for act in recent_activity %}
    <div class="activity-item">
      <span class="activity-time">{{ act.status }}</span>
      &mdash; <a href="/debate/{{ act.youtube_id }}">{{ act.title }}</a>
    </div>
    {% endfor %}
    {% else %}
    <p>No activity yet.</p>
    {% endif %}
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
(function() {
  var topicData = {{ topic_freq_json | safe }};
  var timelineData = {{ timeline_json | safe }};

  new Chart(document.getElementById('topicChart'), {
    type: 'bar',
    data: {
      labels: topicData.map(function(d) { return d[0]; }),
      datasets: [{
        label: 'Debate Count',
        data: topicData.map(function(d) { return d[1]; }),
        backgroundColor: '#1095c1'
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { stepSize: 1 } }
      }
    }
  });

  new Chart(document.getElementById('timelineChart'), {
    type: 'line',
    data: {
      labels: timelineData.map(function(d) { return d[0]; }),
      datasets: [{
        label: 'Debates',
        data: timelineData.map(function(d) { return d[1]; }),
        borderColor: '#1095c1',
        backgroundColor: 'rgba(16, 149, 193, 0.1)',
        fill: true,
        tension: 0.2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { stepSize: 1 }, beginAtZero: true }
      }
    }
  });
})();
</script>
{% endblock %}
```

---

### Task 15: Update dashboard route in `public_routes.py`

**Files:**
- Modify: `src/parker/web/public_routes.py`

- [ ] **Step 1: Rewrite the `dashboard_home` function (around line 18-36)**

Replace the existing `dashboard_home` function with:

```python
@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        stats = get_dashboard_stats(session)
        topic_freq = get_topic_frequency(session, limit=10)
        timeline = get_debate_timeline(session)
        recent_activity = get_recent_activity(session, limit=6)
        inbox = get_cleanup_inbox(session)
        anomalies = detect_anomalies(session)
    import json

    return templates.template_response(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "topic_freq_json": json.dumps(topic_freq),
            "timeline_json": json.dumps(timeline),
            "recent_activity": recent_activity,
            "cleanup_count": len(inbox["ambiguous_topics"]) + len(inbox["unlinked_guests"]),
            "cleanup_anomalies": anomalies,
        },
    )
```

- [ ] **Step 2: Update imports at top of `public_routes.py`**

Add to the imports (between line 3-6):

```python
from parker.analytics import (
    detect_anomalies,
    get_cleanup_inbox,
    get_dashboard_stats,
    get_debate_timeline,
    get_recent_activity,
    get_topic_frequency,
)
```

Replace the existing import block:
```python
from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from parker import crud
from parker.db import get_session
```

With:
```python
from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from parker import crud
from parker.analytics import (
    detect_anomalies,
    get_cleanup_inbox,
    get_dashboard_stats,
    get_debate_timeline,
    get_recent_activity,
    get_topic_frequency,
)
from parker.db import get_session
```

- [ ] **Step 3: Verify import works**

```bash
.venv/bin/python -c "from parker.web.public_routes import router; print('OK')"
```
Expected: `OK`

---

### Task 16: Add `cleanup_count` to all page routes in `public_routes.py`

**Files:**
- Modify: `src/parker/web/public_routes.py`

- [ ] **Step 1: Add a helper function near the top of public_routes.py**

After the existing helper functions `_get_engine` and `_get_templates` (around line 16), add:

```python
def _get_cleanup_count(request: Request) -> int:
    engine = _get_engine(request)
    with get_session(engine) as session:
        inbox = get_cleanup_inbox(session)
    return len(inbox["ambiguous_topics"]) + len(inbox["unlinked_guests"])
```

- [ ] **Step 2: Add `cleanup_count` to every route's context dict**

For each route's `templates.template_response()` call, add `"cleanup_count": _get_cleanup_count(request)` to the context dict. Do this for all routes:

- `debate_detail` (line 39): add `"cleanup_count": _get_cleanup_count(request),`
- `patterns_page` (line 78): add `"cleanup_count": _get_cleanup_count(request),`
- `topic_drilldown` (line 95): add `"cleanup_count": _get_cleanup_count(request),`
- `debate_list` (line 118): add `"cleanup_count": _get_cleanup_count(request),`
- `debate_list_partial` (line 167): add `"cleanup_count": _get_cleanup_count(request),`
- `search_page` (line 205): add `"cleanup_count": _get_cleanup_count(request),`

---

### Task 17: Create `cleanup.html` admin page

**Files:**
- Create: `src/parker/web/templates/cleanup.html`

- [ ] **Step 1: Write the cleanup template**

```html
{% extends "base.html" %}
{% block title %}Cleanup — Parker Admin{% endblock %}

{% block content %}
<hgroup>
  <h1>Data Cleanup</h1>
  <p>Review and resolve duplicate topics, unlinked guests, and anomalies</p>
</hgroup>

<div class="cleanup-summary">
  <form method="post" action="/admin/cleanup/run" style="display:inline">
    <button type="submit">Run Auto-Cleanup</button>
  </form>
  {% if auto_result %}
  <p style="margin-top:0.5rem">Last auto-cleanup: merged {{ auto_result.merged }} topics, linked {{ auto_result.linked }} guests.</p>
  {% endif %}
</div>

<div class="cleanup-section">
  <h2>Duplicate Topics ({{ ambiguous_topics|length }})</h2>
  {% if ambiguous_topics %}
  <table>
    <thead>
      <tr>
        <th>Topic A</th>
        <th>Topic B</th>
        <th>Similarity</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for match in ambiguous_topics %}
      {% set topic_a = topics_by_id.get(match.topic_a_id) %}
      {% set topic_b = topics_by_id.get(match.topic_b_id) %}
      <tr>
        <td>{{ topic_a.name if topic_a else '?' }}</td>
        <td>{{ topic_b.name if topic_b else '?' }}</td>
        <td>{{ "%.2f"|format(match.similarity) }}</td>
        <td>
          <form method="post" action="/admin/cleanup/merge/{{ match.id }}" style="display:inline">
            <button type="submit" class="outline">Merge</button>
          </form>
          <form method="post" action="/admin/cleanup/reject/{{ match.id }}" style="display:inline">
            <button type="submit" class="outline secondary">Reject</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p>No ambiguous topic matches.</p>
  {% endif %}
</div>

<div class="cleanup-section">
  <h2>Unlinked Guests ({{ unlinked_guests|length }})</h2>
  {% if unlinked_guests %}
  <table>
    <thead>
      <tr>
        <th>Debate</th>
        <th>Date</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for debate in unlinked_guests %}
      <tr>
        <td><a href="/admin/videos/{{ debate.youtube_id }}/review">{{ debate.title }}</a></td>
        <td>{{ debate.upload_date or '-' }}</td>
        <td>
          <form method="post" action="/admin/cleanup/link-guest/{{ debate.id }}" style="display:inline">
            <select name="guest_id">
              <option value="">Select guest...</option>
              {% for guest in all_guests %}
              <option value="{{ guest.id }}">{{ guest.name }}</option>
              {% endfor %}
            </select>
            <button type="submit">Link</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p>No unlinked guests.</p>
  {% endif %}
</div>

<div class="cleanup-section">
  <h2>Anomalies</h2>
  <ul>
    <li>{{ anomalies.failed_pipelines }} failed pipeline runs</li>
    <li>{{ anomalies.empty_transcripts }} debates with zero utterances</li>
    <li>{{ anomalies.unreviewed_count }} unreviewed completed debates</li>
  </ul>
</div>
{% endblock %}
```

---

### Task 18: Add `/admin/cleanup` routes to `routes.py`

**Files:**
- Modify: `src/parker/web/routes.py`

- [ ] **Step 1: Add cleanup route handlers at end of routes.py (before the trailing separator comment)**

```python
from parker.analytics import (
    detect_anomalies,
    get_cleanup_inbox,
)
from parker.crud import (
    get_all_guests,
    get_topic_matches,
    link_debate_to_guest,
    merge_topic_match,
    reject_topic_match,
)
from parker.analytics import auto_link_guests, auto_merge_topics
from parker.models import Topic


@router.get("/cleanup", response_class=HTMLResponse)
async def cleanup_page(request: Request):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        inbox = get_cleanup_inbox(session)
        anomalies = detect_anomalies(session)
        guests = get_all_guests(session)
        topics_by_id: dict[int, Topic] = {}
        for match in inbox["ambiguous_topics"]:
            t_a = session.get(Topic, match.topic_a_id)
            t_b = session.get(Topic, match.topic_b_id)
            if t_a:
                topics_by_id[t_a.id] = t_a
            if t_b:
                topics_by_id[t_b.id] = t_b
    return templates.template_response(
        "cleanup.html",
        {
            "request": request,
            "ambiguous_topics": inbox["ambiguous_topics"],
            "unlinked_guests": inbox["unlinked_guests"],
            "anomalies": anomalies,
            "all_guests": guests,
            "topics_by_id": topics_by_id,
        },
    )


@router.post("/cleanup/run", response_class=HTMLResponse)
async def cleanup_run(request: Request):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        merged = auto_merge_topics(session, threshold=0.95)
        linked = auto_link_guests(session)

        inbox = get_cleanup_inbox(session)
        anomalies = detect_anomalies(session)
        guests = get_all_guests(session)
        topics_by_id: dict[int, Topic] = {}
        for match in inbox["ambiguous_topics"]:
            t_a = session.get(Topic, match.topic_a_id)
            t_b = session.get(Topic, match.topic_b_id)
            if t_a:
                topics_by_id[t_a.id] = t_a
            if t_b:
                topics_by_id[t_b.id] = t_b
    return templates.template_response(
        "cleanup.html",
        {
            "request": request,
            "ambiguous_topics": inbox["ambiguous_topics"],
            "unlinked_guests": inbox["unlinked_guests"],
            "anomalies": anomalies,
            "all_guests": guests,
            "topics_by_id": topics_by_id,
            "auto_result": {"merged": merged, "linked": linked},
        },
    )


@router.post("/cleanup/merge/{match_id}", response_class=HTMLResponse)
async def cleanup_merge(request: Request, match_id: int):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        merge_topic_match(session, match_id)
    from starlette.responses import RedirectResponse

    return RedirectResponse(url="/admin/cleanup", status_code=303)


@router.post("/cleanup/reject/{match_id}", response_class=HTMLResponse)
async def cleanup_reject(request: Request, match_id: int):
    engine = _get_engine(request)
    with get_session(engine) as session:
        reject_topic_match(session, match_id)
    from starlette.responses import RedirectResponse

    return RedirectResponse(url="/admin/cleanup", status_code=303)


@router.post("/cleanup/link-guest/{debate_id}", response_class=HTMLResponse)
async def cleanup_link_guest(request: Request, debate_id: int):
    from starlette.responses import RedirectResponse

    engine = _get_engine(request)
    form = await request.form()
    guest_id_str = form.get("guest_id", "")
    if not guest_id_str:
        return RedirectResponse(url="/admin/cleanup", status_code=303)

    with get_session(engine) as session:
        link_debate_to_guest(session, debate_id, int(guest_id_str))
    return RedirectResponse(url="/admin/cleanup", status_code=303)
```

- [ ] **Step 2: Verify app imports with all new routes**

```bash
.venv/bin/python -c "from parker.web.routes import router; print('OK')"
```
Expected: `OK`

---

### Task 19: Add `cleanup_count` to admin routes context

**Files:**
- Modify: `src/parker/web/routes.py`

- [ ] **Step 1: Add `cleanup_count` to the `review_page` route (line 38)**

In `review_page`, add to the context dict:
```python
"cleanup_count": 0,
```

- [ ] **Step 2: Add `cleanup_count` to `video_list` route (line 19)**

Same, add `"cleanup_count": 0` to context. Admin sidebar doesn't need real-time counts, just pass 0 to avoid template errors.

---

### Task 20: Add `parker cleanup` CLI command

**Files:**
- Modify: `src/parker/cli.py`

- [ ] **Step 1: Add cleanup command after the existing commands**

```python
@app.command()
def cleanup() -> None:
    """Run automatic data cleanup: merge duplicate topics, link guests."""
    from parker.analytics import auto_link_guests, auto_merge_topics
    from parker.db import get_session

    settings = get_settings()
    engine = get_engine(settings.db_path)
    init_db(engine)

    with get_session(engine) as session:
        merged = auto_merge_topics(session, threshold=0.95)
        linked = auto_link_guests(session)

    typer.echo(f"Merged {merged} topic(s)")
    typer.echo(f"Linked {linked} guest(s)")
```

Place this after the existing `retry` command (after line 110) and before the `analyze` command.

---

### Task 21: Verify everything works end-to-end

- [ ] **Step 1: Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: All tests pass (previous 69 passed + new ~12 analytics tests + 2 crud tests)

- [ ] **Step 2: Start the server and verify pages load**

```bash
.venv/bin/python -m parker.cli serve
```
Visit:
- `http://127.0.0.1:8000/` — Dashboard with KPIs and charts
- `http://127.0.0.1:8000/debates` — Debate list with sidebar
- `http://127.0.0.1:8000/admin/videos` — Admin with sidebar including cleanup link
- `http://127.0.0.1:8000/admin/cleanup` — Cleanup page

---

### Task 22: Final commit

```bash
git add -A
git commit -m "feat: Phase 1 — data cleanup automation and dashboard overhaul"
```

Run lint:
```bash
ruff check src/ tests/
```

Run tests one final time:
```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: All green.
