from parker.speakers import SpeakerAssignment, extract_utterances, identify_parker


def test_identify_parker_by_speaking_time():
    segments = [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 10.0},
        {"speaker": "SPEAKER_01", "start": 10.0, "end": 15.0},
        {"speaker": "SPEAKER_00", "start": 15.0, "end": 30.0},
        {"speaker": "SPEAKER_01", "start": 30.0, "end": 35.0},
    ]
    result = identify_parker(segments)
    assert result.parker_speaker == "SPEAKER_00"
    assert result.caller_speaker == "SPEAKER_01"
    assert result.confidence == "high"
    assert result.needs_review is False


def test_identify_parker_low_confidence():
    # First speaker (SPEAKER_01) differs from most-speaking-time (SPEAKER_00)
    # -> heuristics disagree -> low confidence
    segments = [
        {"speaker": "SPEAKER_01", "start": 0.0, "end": 5.0},
        {"speaker": "SPEAKER_00", "start": 5.0, "end": 30.0},
        {"speaker": "SPEAKER_01", "start": 30.0, "end": 35.0},
        {"speaker": "SPEAKER_00", "start": 35.0, "end": 47.0},
    ]
    result = identify_parker(segments)
    assert result.confidence == "low"
    assert result.needs_review is True


def test_identify_parker_single_speaker():
    segments = [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 30.0},
    ]
    result = identify_parker(segments)
    assert result.parker_speaker == "SPEAKER_00"
    assert result.caller_speaker == "SPEAKER_01"
    assert result.confidence == "low"
    assert result.needs_review is True


def test_identify_parker_empty_segments():
    result = identify_parker([])
    assert result.parker_speaker == "SPEAKER_00"
    assert result.caller_speaker == "SPEAKER_01"
    assert result.confidence == "low"
    assert result.needs_review is True


def test_speaker_assignment_model():
    assignment = SpeakerAssignment(
        parker_speaker="SPEAKER_00",
        caller_speaker="SPEAKER_01",
        confidence="high",
        needs_review=False,
        method="speaking_time",
        parker_total_seconds=25.0,
        caller_total_seconds=5.0,
    )
    assert assignment.parker_total_seconds == 25.0
    assert assignment.method == "speaking_time"


def test_extract_utterances_basic():
    segments = [
        {
            "speaker": "SPEAKER_00",
            "start": 0.0,
            "end": 5.2,
            "text": "I think that's a really interesting point.",
            "words": [
                {"word": "I", "start": 0.0, "end": 0.12, "score": 0.98},
                {"word": "think", "start": 0.12, "end": 0.45, "score": 0.95},
            ],
        },
        {
            "speaker": "SPEAKER_01",
            "start": 5.2,
            "end": 12.0,
            "text": "Well, I disagree with that.",
            "words": [
                {"word": "Well", "start": 5.2, "end": 5.5, "score": 0.97},
            ],
        },
    ]
    assignment = SpeakerAssignment(
        parker_speaker="SPEAKER_00",
        caller_speaker="SPEAKER_01",
        confidence="high",
        needs_review=False,
    )
    utterances = extract_utterances(segments, assignment, debate_id=1)
    assert len(utterances) == 2
    assert utterances[0].speaker == "parker"
    assert utterances[0].speaker_raw == "SPEAKER_00"
    assert utterances[0].text == "I think that's a really interesting point."
    assert utterances[0].start_time == 0.0
    assert utterances[0].end_time == 5.2
    assert utterances[1].speaker == "caller"
    assert utterances[1].speaker_raw == "SPEAKER_01"


def test_extract_utterances_merges_consecutive_same_speaker():
    segments = [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 5.0, "text": "Hello.", "words": []},
        {"speaker": "SPEAKER_00", "start": 5.0, "end": 10.0, "text": " How are you?", "words": []},
        {"speaker": "SPEAKER_01", "start": 10.0, "end": 15.0, "text": "Fine.", "words": []},
    ]
    assignment = SpeakerAssignment(
        parker_speaker="SPEAKER_00",
        caller_speaker="SPEAKER_01",
        confidence="high",
        needs_review=False,
    )
    utterances = extract_utterances(segments, assignment, debate_id=1)
    assert len(utterances) == 2
    assert utterances[0].speaker == "parker"
    assert "Hello." in utterances[0].text
    assert "How are you?" in utterances[0].text
    assert utterances[0].start_time == 0.0
    assert utterances[0].end_time == 10.0


def test_extract_utterances_skips_empty_text():
    segments = [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 5.0, "text": "", "words": []},
        {"speaker": "SPEAKER_01", "start": 5.0, "end": 10.0, "text": "Content here.", "words": []},
    ]
    assignment = SpeakerAssignment(
        parker_speaker="SPEAKER_00",
        caller_speaker="SPEAKER_01",
        confidence="high",
        needs_review=False,
    )
    utterances = extract_utterances(segments, assignment, debate_id=1)
    assert len(utterances) == 1
    assert utterances[0].text == "Content here."
