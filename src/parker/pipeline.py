from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from parker.crud import (
    clear_utterances_for_debate,
    create_debate,
    get_debate_by_youtube_id,
    update_debate_status,
)
from parker.db import get_session
from parker.download import DownloadError, download_audio, extract_youtube_id
from parker.models import Debate, ReviewStatus, VideoStatus
from parker.speakers import extract_utterances, identify_parker
from parker.transcribe import run_pipeline

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


def _emit_progress(progress_callback: ProgressCallback | None, message: str) -> None:
    if progress_callback is not None:
        progress_callback(message)


def process_video(
    url: str,
    engine,
    audio_dir: Path,
    transcript_dir: Path,
    hf_token: str,
    model_name: str = "large-v2",
    device: str = "auto",
    batch_size: int = 16,
    progress_callback: ProgressCallback | None = None,
) -> Debate | None:
    """Process a single YouTube video through the full pipeline.

    Stages: download -> transcribe/align/diarize -> speaker ID -> store utterances.
    Skips already-completed videos. Checkpoints status at each stage.
    """
    youtube_id = extract_youtube_id(url)

    with get_session(engine) as session:
        existing = get_debate_by_youtube_id(session, youtube_id)
        if existing and existing.status == VideoStatus.COMPLETED:
            logger.info("Already completed: %s", youtube_id)
            _emit_progress(progress_callback, f"Already completed {youtube_id}")
            return existing

        if existing and existing.status == VideoStatus.FAILED:
            logger.info("Found failed video, will retry: %s", youtube_id)

    try:
        logger.info("=== Processing: %s ===", youtube_id)
        _emit_progress(progress_callback, f"Processing {youtube_id}")

        # Stage 1: Download audio
        logger.info("[1/4] Downloading audio")
        _emit_progress(progress_callback, "[1/4] Downloading audio")
        download_result = download_audio(url, audio_dir)

        with get_session(engine) as session:
            if not get_debate_by_youtube_id(session, youtube_id):
                create_debate(
                    session,
                    youtube_id=youtube_id,
                    title=download_result.title,
                    url=url,
                    duration_seconds=download_result.duration_seconds,
                    upload_date=download_result.upload_date,
                )
            update_debate_status(
                session,
                youtube_id,
                VideoStatus.DOWNLOADED,
                audio_path=str(download_result.audio_path),
            )

        # Stage 2: Transcribe + align + diarize
        logger.info("[2/4] Running WhisperX pipeline (transcribe + align + diarize)")
        _emit_progress(progress_callback, "[2/4] Transcribing, aligning, and diarizing")
        transcription = run_pipeline(
            audio_path=download_result.audio_path,
            output_dir=transcript_dir,
            youtube_id=youtube_id,
            hf_token=hf_token,
            model_name=model_name,
            device=device,
            batch_size=batch_size,
        )

        with get_session(engine) as session:
            update_debate_status(
                session,
                youtube_id,
                VideoStatus.TRANSCRIBED,
                raw_transcript_path=str(transcript_dir / f"{youtube_id}_raw.json"),
            )

        # Stage 3: Speaker identification
        logger.info("[3/4] Identifying speakers")
        _emit_progress(progress_callback, "[3/4] Identifying speakers")
        assignment = identify_parker(transcription.segments)
        logger.info(
            "Speaker assignment: parker=%s, caller=%s, confidence=%s",
            assignment.parker_speaker,
            assignment.caller_speaker,
            assignment.confidence,
        )

        # Stage 4: Extract utterances and store
        logger.info("[4/4] Extracting utterances and storing in database")
        _emit_progress(progress_callback, "[4/4] Saving transcript")
        with get_session(engine) as session:
            debate = get_debate_by_youtube_id(session, youtube_id)
            if debate is None:
                raise ValueError(f"Debate not found after download: {youtube_id}")

            clear_utterances_for_debate(session, debate.id)
            utterances = extract_utterances(transcription.segments, assignment, debate_id=debate.id)
            for utterance in utterances:
                session.add(utterance)

            update_debate_status(session, youtube_id, VideoStatus.COMPLETED)
            debate = get_debate_by_youtube_id(session, youtube_id)

            # Export plain text transcript while session is still open
            txt_path = export_transcript_txt(debate, utterances, transcript_dir)
            logger.info("Transcript saved: %s", txt_path)

        logger.info("=== Completed: %s (%d utterances) ===", youtube_id, len(utterances))
        _emit_progress(progress_callback, f"Completed {youtube_id}")
        return debate

    except DownloadError as e:
        logger.error("Download failed for %s: %s", youtube_id, e)
        with get_session(engine) as session:
            if not get_debate_by_youtube_id(session, youtube_id):
                create_debate(session, youtube_id=youtube_id, title=f"Failed: {youtube_id}", url=url)
            update_debate_status(session, youtube_id, VideoStatus.FAILED, error_message=str(e))
        return None
    except Exception as e:
        logger.error("Pipeline failed for %s: %s", youtube_id, e, exc_info=True)
        with get_session(engine) as session:
            existing = get_debate_by_youtube_id(session, youtube_id)
            if existing:
                update_debate_status(session, youtube_id, VideoStatus.FAILED, error_message=str(e))
            else:
                create_debate(session, youtube_id=youtube_id, title=f"Failed: {youtube_id}", url=url)
                update_debate_status(session, youtube_id, VideoStatus.FAILED, error_message=str(e))
        return None


def export_transcript_txt(debate: Debate, utterances: list, transcript_dir: Path) -> Path:
    """Export a plain text transcript with speaker labels and timestamps."""
    lines = [
        f"# {debate.title}",
        f"# {debate.url}",
        f"# Duration: {debate.duration_seconds:.0f}s | Utterances: {len(utterances)}",
        "",
    ]
    for u in utterances:
        mins = int(u.start_time // 60)
        secs = int(u.start_time % 60)
        lines.append(f"[{mins:02d}:{secs:02d}] {u.speaker.upper()}: {u.text}")
        lines.append("")

    transcript_dir.mkdir(parents=True, exist_ok=True)
    txt_path = transcript_dir / f"{debate.youtube_id}_transcript.txt"
    txt_path.write_text("\n".join(lines))
    return txt_path


def get_nlp_ready_debates(engine) -> list:
    """Return debates that are approved for NLP analysis (Phase 3 gate).

    Only debates with review_status == APPROVED can enter the NLP pipeline.
    This prevents processing transcripts that haven't been human-verified.
    """
    from parker.crud import get_approved_debates
    with get_session(engine) as session:
        return get_approved_debates(session)


def is_debate_nlp_ready(engine, youtube_id: str) -> bool:
    """Check if a specific debate is approved for NLP analysis."""
    from parker.crud import get_debate_by_youtube_id
    with get_session(engine) as session:
        debate = get_debate_by_youtube_id(session, youtube_id)
        if debate is None:
            return False
        return debate.review_status == ReviewStatus.APPROVED


def analyze_debate(engine, youtube_id: str, settings=None, force: bool = False):
    """Analyze a single approved debate with LLM extraction. Idempotent unless force=True.

    Returns the NLPResult row.
    """
    from sqlmodel import select

    from parker.config import get_settings
    from parker.crud import get_debate_by_youtube_id, get_utterances_for_debate
    from parker.models import NLPResult, Topic
    from parker.nlp.extractor import extract_analysis, store_analysis
    from parker.nlp.prompts import format_transcript_for_llm

    if settings is None:
        settings = get_settings()

    if not is_debate_nlp_ready(engine, youtube_id):
        raise ValueError(f"Debate {youtube_id} is not approved for NLP analysis")

    with get_session(engine) as session:
        debate = get_debate_by_youtube_id(session, youtube_id)
        if debate is None:
            raise ValueError(f"Debate not found: {youtube_id}")

        # Check for existing result (idempotency)
        existing = session.exec(
            select(NLPResult).where(NLPResult.debate_id == debate.id)
        ).first()
        if existing and existing.status == "completed" and not force:
            logger.info("Already analyzed: %s (use force=True to re-analyze)", youtube_id)
            return existing

        utterances = get_utterances_for_debate(session, debate.id)
        transcript_text = format_transcript_for_llm(debate, utterances)

        # Get existing topics for deduplication
        all_topics = session.exec(select(Topic).where(Topic.status != "rejected")).all()
        existing_topic_names = [t.name for t in all_topics]

    # Run extraction (outside session to avoid long-held locks)
    logger.info("Extracting analysis for %s", youtube_id)

    try:
        analysis = extract_analysis(transcript_text, existing_topic_names, settings)
        raw_json = analysis.model_dump_json()
    except Exception as e:
        logger.error("LLM extraction failed for %s: %s", youtube_id, e)
        with get_session(engine) as session:
            debate = get_debate_by_youtube_id(session, youtube_id)
            result = NLPResult(debate_id=debate.id, status="failed", error_message=str(e))
            session.add(result)
            session.commit()
            session.refresh(result)
            return result

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


def process_batch(
    urls: list[str],
    engine,
    audio_dir: Path,
    transcript_dir: Path,
    hf_token: str,
    model_name: str = "large-v2",
    device: str = "auto",
    batch_size: int = 16,
    progress_callback: ProgressCallback | None = None,
) -> list[Debate | None]:
    """Process multiple YouTube videos sequentially with per-video isolation."""
    results: list[Debate | None] = []
    total = len(urls)
    for i, url in enumerate(urls, 1):
        logger.info("Processing video %d/%d: %s", i, total, url)
        _emit_progress(progress_callback, f"[{i}/{total}] Starting {extract_youtube_id(url)}")
        result = process_video(
            url=url,
            engine=engine,
            audio_dir=audio_dir,
            transcript_dir=transcript_dir,
            hf_token=hf_token,
            model_name=model_name,
            device=device,
            batch_size=batch_size,
            progress_callback=progress_callback,
        )
        results.append(result)
    return results


def get_status_summary(engine) -> dict[str, int]:
    """Return counts of debates by status."""
    from parker.crud import get_all_debates

    with get_session(engine) as session:
        debates = get_all_debates(session)

    summary: dict[str, int] = {
        "total": len(debates),
        "pending": 0,
        "downloading": 0,
        "downloaded": 0,
        "transcribing": 0,
        "transcribed": 0,
        "diarizing": 0,
        "completed": 0,
        "failed": 0,
    }
    for debate in debates:
        status_key = debate.status.value
        if status_key in summary:
            summary[status_key] += 1

    return summary


def retry_failed(
    engine,
    audio_dir: Path,
    transcript_dir: Path,
    hf_token: str,
    **kwargs,
) -> list[Debate | None]:
    """Retry all failed videos by resetting their status and reprocessing."""
    from parker.crud import get_debates_by_status, reset_failed_debate

    with get_session(engine) as session:
        failed = get_debates_by_status(session, VideoStatus.FAILED)
        urls = [d.url for d in failed]
        for d in failed:
            reset_failed_debate(session, d.youtube_id)

    logger.info("Retrying %d failed videos", len(urls))
    return process_batch(
        urls=urls,
        engine=engine,
        audio_dir=audio_dir,
        transcript_dir=transcript_dir,
        hf_token=hf_token,
        **kwargs,
    )
