from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

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

router = APIRouter()


def _get_engine(request: Request):
    return request.app.state.engine


def _get_templates(request: Request):
    return request.app.state.templates


def _get_cleanup_count(request: Request) -> int:
    engine = _get_engine(request)
    with get_session(engine) as session:
        inbox = get_cleanup_inbox(session)
    return len(inbox["ambiguous_topics"]) + len(inbox["unlinked_guests"])


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


@router.get("/debate/{youtube_id}", response_class=HTMLResponse)
async def debate_detail(request: Request, youtube_id: str):
    from fastapi import HTTPException

    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        debate = crud.get_debate_by_youtube_id(session, youtube_id)
        if debate is None:
            raise HTTPException(status_code=404, detail=f"Debate not found: {youtube_id}")
        topics = crud.get_topics_for_debate(session, debate.id)
        all_stances = crud.get_stances_for_debate(session, debate.id)
        keywords = crud.get_keywords_for_debate(session, debate.id)
        utterances = crud.get_utterances_for_debate(session, debate.id)

        stances_by_topic: dict[int, list] = {}
        for stance in all_stances:
            stances_by_topic.setdefault(stance.topic_id, []).append(stance)

        parker_keywords = [k for k in keywords if k.speaker == "parker"][:10]
        caller_keywords = [k for k in keywords if k.speaker == "caller"][:10]

    return templates.template_response(
        "debate_detail.html",
        {
            "request": request,
            "debate": debate,
            "youtube_id": youtube_id,
            "topics": topics,
            "stances_by_topic": stances_by_topic,
            "parker_keywords": parker_keywords,
            "caller_keywords": caller_keywords,
            "keywords": keywords,
            "utterances": utterances,
            "cleanup_count": _get_cleanup_count(request),
        },
    )


@router.get("/patterns", response_class=HTMLResponse)
async def patterns_page(request: Request):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        patterns = crud.get_cross_debate_patterns(session)
        keyword_freq = crud.get_keyword_frequencies(session, speaker="parker")
        top_keywords = keyword_freq[:20]
    return templates.template_response(
        "patterns.html",
        {
            "request": request,
            "patterns": patterns,
            "top_keywords": top_keywords,
            "cleanup_count": _get_cleanup_count(request),
        },
    )


@router.get("/patterns/topic/{topic_name}", response_class=HTMLResponse)
async def topic_drilldown(request: Request, topic_name: str):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        results = crud.get_topic_stances_across_debates(session, topic_name)
        debates_seen = []
        seen_ids = set()
        for r in results:
            if r["debate_id"] not in seen_ids:
                seen_ids.add(r["debate_id"])
                debates_seen.append(r)
    return templates.template_response(
        "topic_drilldown.html",
        {
            "request": request,
            "topic_name": topic_name,
            "results": results,
            "debates_seen": debates_seen,
            "cleanup_count": _get_cleanup_count(request),
        },
    )


@router.get("/debates", response_class=HTMLResponse)
async def debate_list(
    request: Request,
    topic: str | None = None,
    speaker: str | None = None,
    keyword: str | None = None,
    stance: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        debates = crud.get_debates_filtered(
            session,
            topic=topic,
            speaker=speaker,
            keyword=keyword,
            stance=stance,
            date_from=date_from,
            date_to=date_to,
        )
        topic_freq = crud.get_topic_frequency(session)
        all_topics = sorted(set(t[0] for t in topic_freq))
        debate_topics = {}
        debate_stances = {}
        for debate in debates:
            debate_topics[debate.id] = crud.get_topics_for_debate(session, debate.id)
            debate_stances[debate.id] = crud.get_stances_for_debate(session, debate.id)
    return templates.template_response(
        "debate_list.html",
        {
            "request": request,
            "debates": debates,
            "all_topics": all_topics,
            "debate_topics": debate_topics,
            "debate_stances": debate_stances,
            "filters": {
                "topic": topic,
                "speaker": speaker,
                "keyword": keyword,
                "stance": stance,
                "date_from": date_from,
                "date_to": date_to,
            },
            "cleanup_count": _get_cleanup_count(request),
        },
    )


@router.get("/debates/partials/list", response_class=HTMLResponse)
async def debate_list_partial(
    request: Request,
    topic: str | None = None,
    speaker: str | None = None,
    keyword: str | None = None,
    stance: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        debates = crud.get_debates_filtered(
            session,
            topic=topic,
            speaker=speaker,
            keyword=keyword,
            stance=stance,
            date_from=date_from,
            date_to=date_to,
        )
        debate_topics = {}
        debate_stances = {}
        for debate in debates:
            debate_topics[debate.id] = crud.get_topics_for_debate(session, debate.id)
            debate_stances[debate.id] = crud.get_stances_for_debate(session, debate.id)
    return templates.template_response(
        "partials/debate_cards.html",
        {
            "request": request,
            "debates": debates,
            "debate_topics": debate_topics,
            "debate_stances": debate_stances,
            "cleanup_count": _get_cleanup_count(request),
        },
    )


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = ""):
    templates = _get_templates(request)
    engine = _get_engine(request)
    results = []
    debates_with_matches = {}
    if q.strip():
        with get_session(engine) as session:
            results = crud.search_utterances(session, q.strip())
            for r in results:
                debates_with_matches.setdefault(
                    r["debate_id"],
                    {
                        "title": r["debate_title"],
                        "youtube_id": r["youtube_id"],
                        "matches": [],
                    },
                )["matches"].append(r)
    return templates.template_response(
        "search_results.html",
        {
            "request": request,
            "query": q,
            "results": results,
            "debates_with_matches": debates_with_matches,
            "cleanup_count": _get_cleanup_count(request),
        },
    )
