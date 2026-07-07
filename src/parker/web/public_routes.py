from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from parker import crud
from parker.analytics import (
    get_confidence_distribution,
    get_dashboard_stats,
    get_debate_timeline,
    get_keyword_comparison,
    get_recent_activity,
    get_speaker_balance,
    get_stance_consistency,
    get_stance_matrix,
    get_topic_frequency,
)
from parker.db import get_session

router = APIRouter()


def _get_engine(request: Request):
    return request.app.state.engine


def _get_templates(request: Request):
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        stats = get_dashboard_stats(session)
        topic_freq = get_topic_frequency(session, limit=10)
        timeline = get_debate_timeline(session)
        recent_activity = get_recent_activity(session, limit=6)
    import json

    return templates.template_response(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "topic_freq_json": json.dumps(topic_freq),
            "timeline_json": json.dumps(timeline),
            "recent_activity": recent_activity,
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
        },
    )


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        balance_data = get_speaker_balance(session)
        stance_data = get_stance_matrix(session)
        topic_freq = get_topic_frequency(session, limit=15)
        consistency_data = get_stance_consistency(session)
        keyword_data = get_keyword_comparison(session, limit=15)
        confidence_data = get_confidence_distribution(session)
    import json

    return templates.template_response(
        "analytics.html",
        {
            "request": request,
            "balance_data": balance_data,
            "balance_json": json.dumps(balance_data),
            "stance_json": json.dumps(stance_data),
            "topic_freq_json": json.dumps(topic_freq),
            "consistency_json": json.dumps(consistency_data),
            "keyword_json": json.dumps(keyword_data),
            "confidence_json": json.dumps(confidence_data),
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
    return templates.template_response(
        "debate_list.html",
        {
            "request": request,
            "debates": debates,
            "all_topics": all_topics,
            "filters": {
                "topic": topic,
                "speaker": speaker,
                "keyword": keyword,
                "stance": stance,
                "date_from": date_from,
                "date_to": date_to,
            },
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
    return templates.template_response(
        "partials/debate_cards.html",
        {
            "request": request,
            "debates": debates,
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
        },
    )
