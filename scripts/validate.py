"""Validation script for Phase 1 — process test videos and generate quality report.

Usage:
    python scripts/validate.py [--urls URL1 URL2 URL3]

If no URLs provided, uses default test videos.
Outputs a quality report to data/validation_report.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parker.config import get_settings
from parker.db import get_engine, get_session, init_db
from parker.models import VideoStatus
from parker.pipeline import process_video


DEFAULT_TEST_URLS = [
    "https://www.youtube.com/watch?v=jNQXAC9IVRw",
]


def validate(urls: list[str]) -> dict:
    settings = get_settings()
    settings.ensure_dirs()

    engine = get_engine(settings.db_path)
    init_db(engine)

    results: list[dict] = []

    for i, url in enumerate(urls, 1):
        print(f"\n{'='*60}")
        print(f"Processing video {i}/{len(urls)}: {url}")
        print(f"{'='*60}\n")

        debate = process_video(
            url=url,
            engine=engine,
            audio_dir=settings.audio_dir,
            transcript_dir=settings.transcript_dir,
            hf_token=settings.hf_token,
            model_name=settings.whisper_model,
            device=settings.whisper_device,
            batch_size=settings.whisper_batch_size,
        )

        if debate is None:
            results.append({"url": url, "status": "FAILED"})
            print(f"FAILED: {url}")
            continue

        with get_session(engine) as session:
            from sqlmodel import select
            from parker.models import Utterance

            stmt = select(Utterance).where(Utterance.debate_id == debate.id)
            utterances = session.exec(stmt).all()

        total_duration = sum(u.end_time - u.start_time for u in utterances)
        parker_count = sum(1 for u in utterances if u.speaker == "parker")
        caller_count = sum(1 for u in utterances if u.speaker == "caller")
        avg_confidence = (
            sum(u.confidence for u in utterances if u.confidence) / len([u for u in utterances if u.confidence])
            if any(u.confidence for u in utterances)
            else None
        )

        video_result = {
            "url": url,
            "youtube_id": debate.youtube_id,
            "title": debate.title,
            "status": "COMPLETED",
            "duration_seconds": debate.duration_seconds,
            "utterance_count": len(utterances),
            "parker_utterances": parker_count,
            "caller_utterances": caller_count,
            "total_speech_seconds": round(total_duration, 1),
            "avg_confidence": round(avg_confidence, 3) if avg_confidence else None,
            "sample_utterances": [
                {
                    "speaker": u.speaker,
                    "text": u.text[:100],
                    "start": u.start_time,
                    "end": u.end_time,
                }
                for u in utterances[:10]
            ],
            "turn_boundaries": _extract_turn_boundaries(utterances[:30]),
        }

        results.append(video_result)

        print(f"\nResults for {debate.youtube_id}:")
        print(f"  Title: {debate.title}")
        print(f"  Duration: {debate.duration_seconds}s")
        print(f"  Utterances: {len(utterances)} (Parker: {parker_count}, Caller: {caller_count})")
        print(f"  Avg confidence: {avg_confidence:.3f}" if avg_confidence else "  Avg confidence: N/A")
        print(f"\n  First 5 utterances:")
        for u in utterances[:5]:
            print(f"    [{u.start_time:.1f}-{u.end_time:.1f}] {u.speaker}: {u.text[:80]}...")

    report = {
        "videos_processed": len(urls),
        "videos_completed": sum(1 for r in results if r["status"] == "COMPLETED"),
        "videos_failed": sum(1 for r in results if r["status"] == "FAILED"),
        "results": results,
    }

    report_path = settings.data_dir / "validation_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\n\nValidation report saved to: {report_path}")

    return report


def _extract_turn_boundaries(utterances: list) -> list[dict]:
    boundaries = []
    for i in range(1, len(utterances)):
        if utterances[i].speaker != utterances[i - 1].speaker:
            boundaries.append({
                "time": round(utterances[i].start_time, 2),
                "from_speaker": utterances[i - 1].speaker,
                "to_speaker": utterances[i].speaker,
                "context_before": utterances[i - 1].text[-80:],
                "context_after": utterances[i].text[:80],
            })
    return boundaries


def main():
    parser = argparse.ArgumentParser(description="Validate Phase 1 pipeline on test videos")
    parser.add_argument("--urls", nargs="+", help="YouTube URLs to process", default=DEFAULT_TEST_URLS)
    args = parser.parse_args()

    report = validate(args.urls)

    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Processed: {report['videos_processed']}")
    print(f"Completed: {report['videos_completed']}")
    print(f"Failed:    {report['videos_failed']}")

    if report["videos_completed"] > 0:
        print(f"\nNext step: Manually verify turn boundaries in validation_report.json")
        print(f"Check at least 10 turn boundaries per video (30 total for 3 videos)")
        print(f"Target: >25/30 correct turn boundaries")


if __name__ == "__main__":
    main()
