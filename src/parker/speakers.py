from __future__ import annotations

import json as json_module
import logging

from pydantic import BaseModel

from parker.models import Utterance

logger = logging.getLogger(__name__)


class SpeakerAssignment(BaseModel):
    parker_speaker: str
    caller_speaker: str
    confidence: str
    needs_review: bool
    method: str = "speaking_time"
    parker_total_seconds: float = 0.0
    caller_total_seconds: float = 0.0


def identify_parker(segments: list[dict]) -> SpeakerAssignment:
    """Identify which speaker is Parker using speaking-time + first-speaker heuristic."""
    if not segments:
        return SpeakerAssignment(
            parker_speaker="SPEAKER_00",
            caller_speaker="SPEAKER_01",
            confidence="low",
            needs_review=True,
        )

    speaker_time: dict[str, float] = {}
    first_speaker: str | None = None

    for seg in segments:
        speaker = seg.get("speaker", "")
        if not speaker:
            continue
        duration = seg.get("end", 0.0) - seg.get("start", 0.0)
        speaker_time[speaker] = speaker_time.get(speaker, 0.0) + duration
        if first_speaker is None:
            first_speaker = speaker

    if not speaker_time:
        return SpeakerAssignment(
            parker_speaker="SPEAKER_00",
            caller_speaker="SPEAKER_01",
            confidence="low",
            needs_review=True,
        )

    speakers = sorted(speaker_time.keys())
    if len(speakers) == 1:
        return SpeakerAssignment(
            parker_speaker=speakers[0],
            caller_speaker="SPEAKER_01" if speakers[0] == "SPEAKER_00" else "SPEAKER_00",
            confidence="low",
            needs_review=True,
            parker_total_seconds=speaker_time[speakers[0]],
        )

    time_parker = max(speaker_time, key=speaker_time.get)  # type: ignore[arg-type]
    time_caller = min(speaker_time, key=speaker_time.get)  # type: ignore[arg-type]

    first_parker = first_speaker or time_parker

    if time_parker == first_parker:
        confidence = "high"
        needs_review = False
    else:
        confidence = "low"
        needs_review = True
        logger.warning(
            "Speaker heuristic disagreement: time=%s vs first=%s",
            time_parker,
            first_parker,
        )

    return SpeakerAssignment(
        parker_speaker=time_parker,
        caller_speaker=time_caller,
        confidence=confidence,
        needs_review=needs_review,
        method="speaking_time",
        parker_total_seconds=speaker_time[time_parker],
        caller_total_seconds=speaker_time[time_caller],
    )


def extract_utterances(
    segments: list[dict],
    assignment: SpeakerAssignment,
    debate_id: int,
) -> list[Utterance]:
    """Convert diarized segments into Utterance records, merging consecutive same-speaker turns."""
    speaker_map = {
        assignment.parker_speaker: "parker",
        assignment.caller_speaker: "caller",
    }

    # Merge consecutive segments from the same speaker
    merged: list[dict] = []
    for seg in segments:
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()
        if not text:
            continue

        if merged and merged[-1].get("speaker") == speaker:
            merged[-1]["text"] += " " + text
            merged[-1]["end"] = seg.get("end", merged[-1]["end"])
            existing_words = merged[-1].get("words", [])
            new_words = seg.get("words", [])
            merged[-1]["words"] = existing_words + new_words
        else:
            merged.append({
                "speaker": speaker,
                "text": text,
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "words": seg.get("words", []),
            })

    utterances: list[Utterance] = []
    for seg in merged:
        speaker_label = speaker_map.get(seg["speaker"], "unknown")
        words = seg.get("words", [])
        confidence = None
        if words:
            scores = [w.get("score", 0.0) for w in words if w.get("score")]
            if scores:
                confidence = sum(scores) / len(scores)

        utterance = Utterance(
            debate_id=debate_id,
            speaker=speaker_label,
            speaker_raw=seg["speaker"],
            text=seg["text"].strip(),
            start_time=seg["start"],
            end_time=seg["end"],
            confidence=confidence,
            words_json=json_module.dumps(words) if words else None,
        )
        utterances.append(utterance)

    return utterances
