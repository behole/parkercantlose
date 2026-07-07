from __future__ import annotations

from pathlib import Path

import typer

from parker.config import get_settings
from parker.db import get_engine, get_session, init_db
from parker.models import VideoStatus
from parker.pipeline import get_status_summary, process_batch, process_video, retry_failed

app = typer.Typer(name="parker", help="Parker Debate Pipeline — YouTube debate transcription")


@app.command()
def process(url: str) -> None:
    """Process a single YouTube video through the full pipeline."""
    settings = get_settings()
    settings.ensure_dirs()

    engine = get_engine(settings.db_path)
    init_db(engine)

    result = process_video(
        url=url,
        engine=engine,
        audio_dir=settings.audio_dir,
        transcript_dir=settings.transcript_dir,
        hf_token=settings.hf_token,
        model_name=settings.whisper_model,
        device=settings.whisper_device,
        batch_size=settings.whisper_batch_size,
        progress_callback=typer.echo,
    )

    if result is None:
        typer.echo(f"FAILED: Could not process {url}", err=True)
        raise typer.Exit(code=1)
    elif result.status == VideoStatus.COMPLETED:
        typer.echo(f"COMPLETED: {result.youtube_id} — {result.title}")
    else:
        typer.echo(f"Status: {result.status.value} — {result.youtube_id}")


@app.command()
def batch(file: str) -> None:
    """Process multiple videos from a file (one URL per line)."""
    settings = get_settings()
    settings.ensure_dirs()

    engine = get_engine(settings.db_path)
    init_db(engine)

    url_path = Path(file)
    if not url_path.exists():
        typer.echo(f"File not found: {file}", err=True)
        raise typer.Exit(code=1)

    urls = [line.strip() for line in url_path.read_text().splitlines() if line.strip()]
    typer.echo(f"Processing {len(urls)} videos...")

    results = process_batch(
        urls=urls,
        engine=engine,
        audio_dir=settings.audio_dir,
        transcript_dir=settings.transcript_dir,
        hf_token=settings.hf_token,
        progress_callback=typer.echo,
    )

    succeeded = sum(1 for r in results if r is not None)
    failed = sum(1 for r in results if r is None)
    typer.echo(f"Done: {succeeded} succeeded, {failed} failed")


@app.command()
def status() -> None:
    """Show pipeline status for all videos."""
    settings = get_settings()
    engine = get_engine(settings.db_path)
    init_db(engine)

    summary = get_status_summary(engine)
    typer.echo(f"Total: {summary['total']}")
    typer.echo(f"  Completed:  {summary['completed']}")
    typer.echo(f"  Failed:     {summary['failed']}")
    typer.echo(f"  Pending:    {summary['pending']}")
    other = summary["total"] - summary["completed"] - summary["failed"] - summary["pending"]
    if other > 0:
        typer.echo(f"  In Progress: {other}")


@app.command()
def retry() -> None:
    """Retry all failed videos."""
    settings = get_settings()
    settings.ensure_dirs()

    engine = get_engine(settings.db_path)
    init_db(engine)

    results = retry_failed(
        engine=engine,
        audio_dir=settings.audio_dir,
        transcript_dir=settings.transcript_dir,
        hf_token=settings.hf_token,
        progress_callback=typer.echo,
    )
    succeeded = sum(1 for r in results if r is not None)
    typer.echo(f"Retry complete: {succeeded}/{len(results)} succeeded")


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


@app.command()
def analyze(
    youtube_id: str = typer.Option(None, "--youtube-id", help="Analyze a specific debate by YouTube ID"),
    all_debates: bool = typer.Option(False, "--all", help="Analyze all approved debates"),
    force: bool = typer.Option(False, "--force", help="Re-analyze even if already completed"),
) -> None:
    """Run NLP analysis on approved debate transcripts."""
    from parker.pipeline import analyze_debate as run_analysis
    from parker.pipeline import get_nlp_ready_debates

    settings = get_settings()
    settings.ensure_dirs()
    engine = get_engine(settings.db_path)
    init_db(engine)

    if not settings.llm_api_key:
        typer.echo("ERROR: LLM_API_KEY not set. Add it to .env file.", err=True)
        raise typer.Exit(code=1)

    if youtube_id:
        typer.echo(f"Analyzing debate: {youtube_id}")
        result = run_analysis(engine, youtube_id, settings=settings, force=force)
        typer.echo(f"Result: {result.status}")
        if result.status == "failed":
            typer.echo(f"Error: {result.error_message}", err=True)
            raise typer.Exit(code=1)
    elif all_debates:
        debates = get_nlp_ready_debates(engine)
        if not debates:
            typer.echo("No approved debates found for analysis.")
            return
        typer.echo(f"Analyzing {len(debates)} approved debate(s)...")
        succeeded, failed = 0, 0
        for debate in debates:
            typer.echo(f"  {debate.youtube_id}: {debate.title[:50]}...")
            result = run_analysis(engine, debate.youtube_id, settings=settings, force=force)
            if result.status == "completed":
                succeeded += 1
            else:
                failed += 1
                typer.echo(f"    FAILED: {result.error_message}", err=True)
        typer.echo(f"Done: {succeeded} succeeded, {failed} failed")
    else:
        typer.echo("Specify --youtube-id <id> or --all", err=True)
        raise typer.Exit(code=1)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
) -> None:
    """Launch the transcript review web interface."""
    import uvicorn

    settings = get_settings()
    settings.ensure_dirs()
    engine = get_engine(settings.db_path)
    init_db(engine)
    typer.echo(f"Starting review interface at http://{host}:{port}")
    uvicorn.run("parker.web:create_app", host=host, port=port, reload=True, factory=True)


@app.command()
def rebuild_search() -> None:
    """Rebuild the full-text search index from existing utterances."""
    from parker.search import rebuild_fts

    settings = get_settings()
    engine = get_engine(settings.db_path)
    init_db(engine)
    rebuild_fts(engine)
    typer.echo("FTS index rebuilt.")


@app.command(name="guests")
def list_guests() -> None:
    """List all known guests and their cross-video appearances."""
    from parker.crud import get_all_guests, get_guest_stats

    settings = get_settings()
    engine = get_engine(settings.db_path)
    init_db(engine)

    with get_session(engine) as session:
        guests = get_all_guests(session)
        if not guests:
            typer.echo("No guests yet. Use 'parker guest-link <youtube_id> <name>' to add one.")
            return
        for guest in guests:
            stats = get_guest_stats(session, guest.id)
            typer.echo(
                f"  {guest.id:>3}  {guest.name[:40]:<40}  "
                f"{stats['total_debates']} debates, {stats['total_utterances']} utterances"
            )


@app.command(name="guest-link")
def link_guest(
    youtube_id: str = typer.Argument(help="YouTube ID of the debate"),
    guest_name: str = typer.Argument(help="Guest name (creates if new)"),
) -> None:
    """Link a debate's caller to a guest profile (creates guest if needed)."""
    from parker.crud import create_guest, get_all_guests, get_debate_by_youtube_id, link_debate_to_guest

    settings = get_settings()
    engine = get_engine(settings.db_path)
    init_db(engine)

    with get_session(engine) as session:
        debate = get_debate_by_youtube_id(session, youtube_id)
        if debate is None:
            typer.echo(f"Debate not found: {youtube_id}", err=True)
            raise typer.Exit(code=1)

        existing = next((g for g in get_all_guests(session) if g.name.lower() == guest_name.lower()), None)
        if existing:
            guest = existing
            typer.echo(f"Found existing guest: {guest.name} (id={guest.id})")
        else:
            guest = create_guest(session, name=guest_name)
            typer.echo(f"Created new guest: {guest.name} (id={guest.id})")

        link_debate_to_guest(session, debate.id, guest.id)
        typer.echo(f"Linked {youtube_id} → {guest.name}")


@app.command()
def monitor(
    process: bool = typer.Option(False, "--process", help="Auto-process new videos through the pipeline"),
    watch: bool = typer.Option(False, "--watch", help="Continuously poll for new videos"),
    interval: int = typer.Option(300, help="Poll interval in seconds (with --watch)"),
) -> None:
    """Check Parker's YouTube channel for new videos."""
    from parker.monitor import PARKER_CHANNEL_ID, find_new_videos

    settings = get_settings()
    engine = get_engine(settings.db_path)
    init_db(engine)

    import time

    def _check():
        new = find_new_videos(engine, PARKER_CHANNEL_ID)
        if not new:
            typer.echo("No new videos found.")
            return

        typer.echo(f"Found {len(new)} new video(s):")
        for v in new:
            typer.echo(f"  {v['video_id']}  {v['title'][:60]}  ({v['published'][:10]})")

        if process:
            for v in new:
                typer.echo(f"\nProcessing {v['video_id']}...")
                result = process_video(
                    url=v["url"],
                    engine=engine,
                    audio_dir=settings.audio_dir,
                    transcript_dir=settings.transcript_dir,
                    hf_token=settings.hf_token,
                )
                if result:
                    typer.echo(f"  Completed: {result.youtube_id}")
                else:
                    typer.echo(f"  Failed: {v['video_id']}", err=True)

    if watch:
        typer.echo(f"Watching for new videos every {interval}s. Press Ctrl+C to stop.")
        while True:
            _check()
            time.sleep(interval)
    else:
        _check()


def main():
    app()


if __name__ == "__main__":
    app()
