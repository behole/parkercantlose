
from parker.models import Debate, Utterance, VideoStatus


def test_debate_creation():
    debate = Debate(youtube_id="abc123", title="Test Debate", url="https://youtube.com/watch?v=abc123")
    assert debate.youtube_id == "abc123"
    assert debate.status == VideoStatus.PENDING
    assert debate.schema_version == 1
    assert debate.id is None


def test_debate_status_transitions():
    debate = Debate(youtube_id="abc123", title="Test Debate", url="https://youtube.com/watch?v=abc123")
    assert debate.status == VideoStatus.PENDING
    debate.status = VideoStatus.DOWNLOADING
    assert debate.status == VideoStatus.DOWNLOADING
    debate.status = VideoStatus.DOWNLOADED
    assert debate.status == VideoStatus.DOWNLOADED
    debate.status = VideoStatus.FAILED
    assert debate.status == VideoStatus.FAILED


def test_utterance_creation():
    utterance = Utterance(
        debate_id=1,
        speaker="parker",
        speaker_raw="SPEAKER_00",
        text="I think that's a really interesting point.",
        start_time=0.0,
        end_time=5.2,
        confidence=0.95,
    )
    assert utterance.speaker == "parker"
    assert utterance.start_time == 0.0
    assert utterance.end_time == 5.2


def test_utterance_words_json():
    words = [
        {"word": "I", "start": 0.0, "end": 0.12, "score": 0.98},
        {"word": "think", "start": 0.12, "end": 0.45, "score": 0.95},
    ]
    import json

    utterance = Utterance(
        debate_id=1,
        speaker="parker",
        text="I think",
        start_time=0.0,
        end_time=0.45,
        words_json=json.dumps(words),
    )
    assert json.loads(utterance.words_json) == words


def test_video_status_values():
    assert VideoStatus.PENDING == "pending"
    assert VideoStatus.DOWNLOADING == "downloading"
    assert VideoStatus.DOWNLOADED == "downloaded"
    assert VideoStatus.TRANSCRIBING == "transcribing"
    assert VideoStatus.TRANSCRIBED == "transcribed"
    assert VideoStatus.DIARIZING == "diarizing"
    assert VideoStatus.COMPLETED == "completed"
    assert VideoStatus.FAILED == "failed"
