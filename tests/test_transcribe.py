"""Tests for parker.transcribe — WhisperX pipeline."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import parker.transcribe as transcribe_module
from parker.transcribe import (
    SPEAKER_LABELS,
    DiarizationResult,
    TranscriptionResult,
    _load_pyannote_pipeline_class,
    _suppress_torchcodec_warning,
    detect_device,
    get_compute_type,
    run_pipeline,
)


def test_detect_device_cpu_fallback():
    device, compute_type = detect_device("auto")
    assert device in ("cuda", "cpu")
    assert compute_type in ("float16", "int8")


def test_detect_device_cpu_forced():
    device, compute_type = detect_device("cpu")
    assert device == "cpu"
    assert compute_type == "int8"


def test_get_compute_type():
    assert get_compute_type("cuda") == "float16"
    assert get_compute_type("cpu") == "int8"
    assert get_compute_type("mps") == "int8"


def test_transcription_result_model():
    result = TranscriptionResult(
        segments=[
            {
                "start": 0.0,
                "end": 5.2,
                "text": "I think that's a really interesting point.",
                "words": [
                    {"word": "I", "start": 0.0, "end": 0.12, "score": 0.98},
                    {"word": "think", "start": 0.12, "end": 0.45, "score": 0.95},
                ],
            }
        ],
        language="en",
    )
    assert result.language == "en"
    assert len(result.segments) == 1
    assert result.segments[0]["text"] == "I think that's a really interesting point."


def test_diarization_result_model():
    result = DiarizationResult(
        segments=[
            {"start": 0.0, "end": 5.2, "speaker": "SPEAKER_00"},
            {"start": 5.2, "end": 12.0, "speaker": "SPEAKER_01"},
        ],
    )
    assert len(result.segments) == 2
    assert result.segments[0]["speaker"] == "SPEAKER_00"
    assert result.segments[1]["speaker"] == "SPEAKER_01"


def test_speaker_labels():
    assert SPEAKER_LABELS == ("SPEAKER_00", "SPEAKER_01")


def test_load_pyannote_pipeline_class_suppresses_torchcodec_warning():
    fake_pipeline = object()
    fake_module = SimpleNamespace(Pipeline=fake_pipeline)

    with (
        patch("parker.transcribe.importlib.import_module", return_value=fake_module) as import_module,
        patch.object(transcribe_module.warnings, "filterwarnings") as filterwarnings,
    ):
        result = _load_pyannote_pipeline_class()

    assert result is fake_pipeline
    import_module.assert_called_once_with("pyannote.audio")
    filterwarnings.assert_called_once_with(
        "ignore",
        message=r"\s*torchcodec is not installed correctly so built-in audio decoding will fail\..*",
        category=UserWarning,
        module=r"pyannote\.audio\.core\.io",
    )


def test_suppress_torchcodec_warning_applies_expected_filter():
    with patch.object(transcribe_module.warnings, "filterwarnings") as filterwarnings:
        with _suppress_torchcodec_warning():
            pass

    filterwarnings.assert_called_once_with(
        "ignore",
        message=r"\s*torchcodec is not installed correctly so built-in audio decoding will fail\..*",
        category=UserWarning,
        module=r"pyannote\.audio\.core\.io",
    )


def test_run_pipeline_saves_raw_output(tmp_path):
    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"fake audio")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    mock_transcription = TranscriptionResult(
        segments=[{"start": 0.0, "end": 5.0, "text": "Hello", "words": []}],
        language="en",
    )

    with (
        patch("parker.transcribe.transcribe_audio", return_value=mock_transcription),
        patch("parker.transcribe.align_transcription", return_value=mock_transcription),
        patch(
            "parker.transcribe.diarize_audio",
            return_value=DiarizationResult(
                segments=[{"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"}]
            ),
        ),
        patch("parker.transcribe.assign_speakers", return_value=mock_transcription),
    ):
        result = run_pipeline(
            audio_path=audio_path,
            output_dir=output_dir,
            youtube_id="test123",
            hf_token="fake-token",
        )

    assert result is not None
    raw_json = output_dir / "test123_raw.json"
    assert raw_json.exists()
    data = json.loads(raw_json.read_text())
    assert "segments" in data
