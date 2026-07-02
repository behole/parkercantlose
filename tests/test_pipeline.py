from pathlib import Path
from unittest.mock import MagicMock, patch

from parker.db import get_engine, get_session, init_db
from parker.models import Debate, Utterance, VideoStatus
from parker.pipeline import get_status_summary, process_batch, process_video

# Valid 11-char YouTube IDs for extract_youtube_id compatibility
TEST_YT_ID = "dQw4w9WgXcQ"
TEST_URL = f"https://youtube.com/watch?v={TEST_YT_ID}"
DONE_YT_ID = "xxxxxxxxxxx"
DONE_URL = f"https://youtube.com/watch?v={DONE_YT_ID}"


def test_process_video_creates_debate_and_utterances(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    mock_download_result = MagicMock()
    mock_download_result.youtube_id = TEST_YT_ID
    mock_download_result.title = "Test Debate"
    mock_download_result.url = TEST_URL
    mock_download_result.duration_seconds = 300.0
    mock_download_result.upload_date = "20250101"
    mock_download_result.audio_path = tmp_path / f"{TEST_YT_ID}.wav"

    mock_transcription = MagicMock()
    mock_transcription.segments = [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 5.0, "text": "Hello.", "words": []},
        {"speaker": "SPEAKER_01", "start": 5.0, "end": 10.0, "text": "Hi there.", "words": []},
    ]

    mock_assignment = MagicMock()
    mock_assignment.parker_speaker = "SPEAKER_00"
    mock_assignment.caller_speaker = "SPEAKER_01"
    mock_assignment.confidence = "high"
    mock_assignment.needs_review = False

    with (
        patch("parker.pipeline.download_audio", return_value=mock_download_result),
        patch("parker.pipeline.run_pipeline", return_value=mock_transcription),
        patch("parker.pipeline.identify_parker", return_value=mock_assignment),
        patch("parker.pipeline.extract_utterances") as mock_extract,
    ):
        mock_extract.return_value = [
            Utterance(
                debate_id=1, speaker="parker", speaker_raw="SPEAKER_00",
                text="Hello.", start_time=0.0, end_time=5.0,
            ),
            Utterance(
                debate_id=1, speaker="caller", speaker_raw="SPEAKER_01",
                text="Hi there.", start_time=5.0, end_time=10.0,
            ),
        ]

        debate = process_video(
            url=TEST_URL,
            engine=engine,
            audio_dir=tmp_path / "audio",
            transcript_dir=tmp_path / "transcripts",
            hf_token="fake-token",
        )

    assert debate.status == VideoStatus.COMPLETED
    assert debate.youtube_id == TEST_YT_ID
    assert debate.audio_path is not None

    with get_session(engine) as session:
        from sqlmodel import select

        stmt = select(Utterance).where(Utterance.debate_id == debate.id)
        utterances = session.exec(stmt).all()
        assert len(utterances) == 2
        assert utterances[0].speaker == "parker"
        assert utterances[1].speaker == "caller"


def test_process_video_reports_stage_progress(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    mock_download_result = MagicMock()
    mock_download_result.youtube_id = TEST_YT_ID
    mock_download_result.title = "Test Debate"
    mock_download_result.url = TEST_URL
    mock_download_result.duration_seconds = 300.0
    mock_download_result.upload_date = "20250101"
    mock_download_result.audio_path = tmp_path / f"{TEST_YT_ID}.wav"

    mock_transcription = MagicMock()
    mock_transcription.segments = [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 5.0, "text": "Hello.", "words": []},
    ]

    mock_assignment = MagicMock()
    mock_assignment.parker_speaker = "SPEAKER_00"
    mock_assignment.caller_speaker = "SPEAKER_01"
    mock_assignment.confidence = "high"
    mock_assignment.needs_review = False

    progress_messages = []

    with (
        patch("parker.pipeline.download_audio", return_value=mock_download_result),
        patch("parker.pipeline.run_pipeline", return_value=mock_transcription),
        patch("parker.pipeline.identify_parker", return_value=mock_assignment),
        patch("parker.pipeline.extract_utterances", return_value=[]),
    ):
        process_video(
            url=TEST_URL,
            engine=engine,
            audio_dir=tmp_path / "audio",
            transcript_dir=tmp_path / "transcripts",
            hf_token="fake-token",
            progress_callback=progress_messages.append,
        )

    assert progress_messages == [
        f"Processing {TEST_YT_ID}",
        "[1/4] Downloading audio",
        "[2/4] Transcribing, aligning, and diarizing",
        "[3/4] Identifying speakers",
        "[4/4] Saving transcript",
        f"Completed {TEST_YT_ID}",
    ]


def test_process_video_skips_already_completed(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    with get_session(engine) as session:
        from parker.crud import create_debate, update_debate_status

        create_debate(session, youtube_id=DONE_YT_ID, title="Already Done", url=DONE_URL)
        update_debate_status(session, DONE_YT_ID, VideoStatus.COMPLETED)

    with patch("parker.pipeline.download_audio") as mock_dl:
        debate = process_video(
            url=DONE_URL,
            engine=engine,
            audio_dir=tmp_path / "audio",
            transcript_dir=tmp_path / "transcripts",
            hf_token="fake-token",
        )
        mock_dl.assert_not_called()
        assert debate.status == VideoStatus.COMPLETED


def test_process_video_replaces_existing_utterances_on_retry(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    with get_session(engine) as session:
        from parker.crud import create_debate, update_debate_status

        debate = create_debate(
            session,
            youtube_id=TEST_YT_ID,
            title="Retry Debate",
            url=TEST_URL,
            duration_seconds=300.0,
            upload_date="20250101",
        )
        session.add(
            Utterance(
                debate_id=debate.id,
                speaker="parker",
                speaker_raw="SPEAKER_00",
                text="Old transcript",
                start_time=0.0,
                end_time=1.0,
            )
        )
        session.commit()
        update_debate_status(session, TEST_YT_ID, VideoStatus.FAILED, error_message="transient failure")

    mock_download_result = MagicMock()
    mock_download_result.youtube_id = TEST_YT_ID
    mock_download_result.title = "Retry Debate"
    mock_download_result.url = TEST_URL
    mock_download_result.duration_seconds = 300.0
    mock_download_result.upload_date = "20250101"
    mock_download_result.audio_path = tmp_path / f"{TEST_YT_ID}.wav"

    mock_transcription = MagicMock()
    mock_transcription.segments = [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 5.0, "text": "New one.", "words": []},
        {"speaker": "SPEAKER_01", "start": 5.0, "end": 10.0, "text": "New two.", "words": []},
    ]

    mock_assignment = MagicMock()
    mock_assignment.parker_speaker = "SPEAKER_00"
    mock_assignment.caller_speaker = "SPEAKER_01"
    mock_assignment.confidence = "high"
    mock_assignment.needs_review = False

    with (
        patch("parker.pipeline.download_audio", return_value=mock_download_result),
        patch("parker.pipeline.run_pipeline", return_value=mock_transcription),
        patch("parker.pipeline.identify_parker", return_value=mock_assignment),
        patch("parker.pipeline.extract_utterances") as mock_extract,
    ):
        mock_extract.return_value = [
            Utterance(
                debate_id=debate.id, speaker="parker", speaker_raw="SPEAKER_00",
                text="New one.", start_time=0.0, end_time=5.0,
            ),
            Utterance(
                debate_id=debate.id, speaker="caller", speaker_raw="SPEAKER_01",
                text="New two.", start_time=5.0, end_time=10.0,
            ),
        ]

        process_video(
            url=TEST_URL,
            engine=engine,
            audio_dir=tmp_path / "audio",
            transcript_dir=tmp_path / "transcripts",
            hf_token="fake-token",
        )

    with get_session(engine) as session:
        from sqlmodel import select

        statement = (
            select(Utterance)
            .where(Utterance.debate_id == debate.id)
            .order_by(Utterance.start_time)
        )
        utterances = session.exec(statement).all()
        assert len(utterances) == 2
        assert [u.text for u in utterances] == ["New one.", "New two."]


def test_process_batch_processes_all(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    urls = [
        "https://youtube.com/watch?v=aaaaaaaaaaa",
        "https://youtube.com/watch?v=bbbbbbbbbbb",
    ]

    with patch("parker.pipeline.process_video") as mock_process:
        mock_process.return_value = Debate(
            id=1, youtube_id="aaaaaaaaaaa", title="Test", url=urls[0], status=VideoStatus.COMPLETED
        )

        results = process_batch(
            urls=urls, engine=engine, audio_dir=tmp_path, transcript_dir=tmp_path, hf_token="fake"
        )
        assert len(results) == 2
        assert mock_process.call_count == 2


def test_process_batch_reports_video_progress(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    urls = [
        "https://youtube.com/watch?v=aaaaaaaaaaa",
        "https://youtube.com/watch?v=bbbbbbbbbbb",
    ]
    progress_messages = []

    with patch("parker.pipeline.process_video", return_value=None):
        process_batch(
            urls=urls,
            engine=engine,
            audio_dir=tmp_path,
            transcript_dir=tmp_path,
            hf_token="fake",
            progress_callback=progress_messages.append,
        )

    assert progress_messages == [
        "[1/2] Starting aaaaaaaaaaa",
        "[2/2] Starting bbbbbbbbbbb",
    ]


def test_process_batch_isolates_failures(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    urls = [
        "https://youtube.com/watch?v=good0000001",
        "https://youtube.com/watch?v=bad00000002",
        "https://youtube.com/watch?v=good0000003",
    ]

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return None
        return Debate(
            id=call_count, youtube_id=f"vid{call_count:011d}", title="OK", url="", status=VideoStatus.COMPLETED
        )

    with patch("parker.pipeline.process_video", side_effect=side_effect):
        results = process_batch(
            urls=urls, engine=engine, audio_dir=tmp_path, transcript_dir=tmp_path, hf_token="fake"
        )
        assert len(results) == 3
        assert results[1] is None


def test_get_status_summary(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)

    with get_session(engine) as session:
        from parker.crud import create_debate, update_debate_status

        create_debate(session, youtube_id="s1aaaaaaaaa", title="One", url="https://youtube.com/watch?v=s1aaaaaaaaa")
        create_debate(session, youtube_id="s2aaaaaaaaa", title="Two", url="https://youtube.com/watch?v=s2aaaaaaaaa")
        create_debate(session, youtube_id="s3aaaaaaaaa", title="Three", url="https://youtube.com/watch?v=s3aaaaaaaaa")

    with get_session(engine) as session:
        from parker.crud import update_debate_status

        update_debate_status(session, "s1aaaaaaaaa", VideoStatus.COMPLETED)
        update_debate_status(session, "s3aaaaaaaaa", VideoStatus.FAILED, error_message="test error")

    summary = get_status_summary(engine)
    assert summary["total"] == 3
    assert summary["completed"] == 1
    assert summary["failed"] == 1
    assert summary["pending"] == 1
