from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from parker import crud
from parker.db import get_session
from parker.models import Debate, Topic

router = APIRouter()


def _get_engine(request: Request):
    return request.app.state.engine


def _get_templates(request: Request):
    return request.app.state.templates


@router.get("/videos", response_class=HTMLResponse)
async def video_list(request: Request):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        debates = crud.get_all_debates(session)
        edit_counts = {}
        for debate in debates:
            edit_counts[debate.id] = crud.count_edits_for_debate(session, debate.id)
    return templates.template_response(
        "video_list.html",
        {
            "request": request,
            "debates": debates,
            "edit_counts": edit_counts,
        },
    )


@router.get("/videos/{youtube_id}/review", response_class=HTMLResponse)
async def review_page(request: Request, youtube_id: str):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        debate = crud.get_debate_by_youtube_id(session, youtube_id)
        if debate is None:
            raise HTTPException(status_code=404, detail=f"Debate not found: {youtube_id}")
        utterances = crud.get_utterances_for_debate(session, debate.id)
    return templates.template_response(
        "review.html",
        {
            "request": request,
            "debate": debate,
            "utterances": utterances,
            "youtube_id": youtube_id,
        },
    )


@router.put("/api/utterances/{utterance_id}/speaker", response_class=HTMLResponse)
async def toggle_speaker(request: Request, utterance_id: int):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        utterance = crud.toggle_utterance_speaker(session, utterance_id)
        if utterance is None:
            raise HTTPException(status_code=404, detail="Utterance not found")
    return templates.template_response(
        "partials/segment.html",
        {
            "request": request,
            "u": utterance,
        },
    )


@router.patch("/api/utterances/{utterance_id}/text", response_class=HTMLResponse)
async def update_text(request: Request, utterance_id: int, text: str = Form(...)):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        utterance = crud.update_utterance_text(session, utterance_id, text)
        if utterance is None:
            raise HTTPException(status_code=404, detail="Utterance not found")
    return templates.template_response(
        "partials/segment.html",
        {
            "request": request,
            "u": utterance,
        },
    )


@router.post("/api/videos/{youtube_id}/approve", response_class=HTMLResponse)
async def approve_video(request: Request, youtube_id: str):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        debate = crud.approve_debate(session, youtube_id)
        if debate is None:
            raise HTTPException(status_code=404, detail="Debate not found")
    return templates.template_response(
        "partials/approval_bar.html",
        {
            "request": request,
            "debate": debate,
            "youtube_id": youtube_id,
        },
    )


@router.post("/api/videos/{youtube_id}/unapprove", response_class=HTMLResponse)
async def unapprove_video(request: Request, youtube_id: str):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        debate = crud.unapprove_debate(session, youtube_id)
        if debate is None:
            raise HTTPException(status_code=404, detail="Debate not found")
    return templates.template_response(
        "partials/approval_bar.html",
        {
            "request": request,
            "debate": debate,
            "youtube_id": youtube_id,
        },
    )


# ---------------------------------------------------------------------------
# Topic Refinement Routes
# ---------------------------------------------------------------------------


@router.get("/videos/{youtube_id}/topics", response_class=HTMLResponse)
async def topic_refinement(request: Request, youtube_id: str):
    """Topic refinement page for a debate -- accept, reject, rename AI-suggested topics."""
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        debate = crud.get_debate_by_youtube_id(session, youtube_id)
        if debate is None:
            raise HTTPException(status_code=404, detail=f"Debate not found: {youtube_id}")
        nlp_result = crud.get_nlp_result(session, debate.id)
        topics = crud.get_topics_for_debate(session, debate.id)
        stances = crud.get_stances_for_debate(session, debate.id)
        keywords = crud.get_keywords_for_debate(session, debate.id)
        # Group stances by topic_id for template
        stances_by_topic = {}
        for stance in stances:
            stances_by_topic.setdefault(stance.topic_id, []).append(stance)
    return templates.template_response(
        "topics.html",
        {
            "request": request,
            "debate": debate,
            "youtube_id": youtube_id,
            "nlp_result": nlp_result,
            "topics": topics,
            "stances_by_topic": stances_by_topic,
            "keywords": keywords,
        },
    )


@router.post("/api/topics/{topic_id}/accept", response_class=HTMLResponse)
async def accept_topic(request: Request, topic_id: int):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        topic = crud.update_topic_status(session, topic_id, "accepted")
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")
        stances = crud.get_stances_for_topic(session, topic_id)
    return templates.template_response(
        "partials/topic_card.html",
        {
            "request": request,
            "topic": topic,
            "stances": stances,
        },
    )


@router.post("/api/topics/{topic_id}/reject", response_class=HTMLResponse)
async def reject_topic(request: Request, topic_id: int):
    engine = _get_engine(request)
    with get_session(engine) as session:
        topic = crud.update_topic_status(session, topic_id, "rejected")
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")
    # Return empty string to remove the card from DOM (HTMX swap outerHTML)
    return HTMLResponse("")


@router.post("/api/topics/{topic_id}/rename", response_class=HTMLResponse)
async def rename_topic(request: Request, topic_id: int, name: str = Form(...)):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        topic = crud.update_topic_status(session, topic_id, "renamed", new_name=name.strip())
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")
        stances = crud.get_stances_for_topic(session, topic_id)
    return templates.template_response(
        "partials/topic_card.html",
        {
            "request": request,
            "topic": topic,
            "stances": stances,
        },
    )


# ---------------------------------------------------------------------------
# Cross-Debate Topic Matching Routes
# ---------------------------------------------------------------------------


@router.get("/topic-matches", response_class=HTMLResponse)
async def topic_matches_page(request: Request):
    """Cross-debate topic matching page -- confirm or reject suggested matches."""
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        suggested = crud.get_topic_matches(session, status="suggested")
        confirmed = crud.get_topic_matches(session, status="confirmed")
        # Resolve topic objects for display
        suggested_with_topics = []
        for match in suggested:
            topic_a = session.get(Topic, match.topic_a_id)
            topic_b = session.get(Topic, match.topic_b_id)
            debate_a = session.get(Debate, topic_a.debate_id) if topic_a else None
            debate_b = session.get(Debate, topic_b.debate_id) if topic_b else None
            suggested_with_topics.append(
                {"match": match, "topic_a": topic_a, "topic_b": topic_b, "debate_a": debate_a, "debate_b": debate_b}
            )
        confirmed_with_topics = []
        for match in confirmed:
            topic_a = session.get(Topic, match.topic_a_id)
            topic_b = session.get(Topic, match.topic_b_id)
            debate_a = session.get(Debate, topic_a.debate_id) if topic_a else None
            debate_b = session.get(Debate, topic_b.debate_id) if topic_b else None
            confirmed_with_topics.append(
                {"match": match, "topic_a": topic_a, "topic_b": topic_b, "debate_a": debate_a, "debate_b": debate_b}
            )
    return templates.template_response(
        "topic_matches.html",
        {
            "request": request,
            "suggested": suggested_with_topics,
            "confirmed": confirmed_with_topics,
        },
    )


@router.post("/api/topic-matches/{match_id}/confirm", response_class=HTMLResponse)
async def confirm_match(request: Request, match_id: int):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        match = crud.update_topic_match_status(session, match_id, "confirmed")
        if match is None:
            raise HTTPException(status_code=404, detail="Match not found")
        topic_a = session.get(Topic, match.topic_a_id)
        topic_b = session.get(Topic, match.topic_b_id)
        debate_a = session.get(Debate, topic_a.debate_id) if topic_a else None
        debate_b = session.get(Debate, topic_b.debate_id) if topic_b else None
    return templates.template_response(
        "partials/match_card.html",
        {
            "request": request,
            "item": {
                "match": match,
                "topic_a": topic_a,
                "topic_b": topic_b,
                "debate_a": debate_a,
                "debate_b": debate_b,
            },
        },
    )


@router.post("/api/topic-matches/{match_id}/reject", response_class=HTMLResponse)
async def reject_match(request: Request, match_id: int):
    engine = _get_engine(request)
    with get_session(engine) as session:
        crud.update_topic_match_status(session, match_id, "rejected")
    return HTMLResponse("")
