"""WhisperX transcription and diarization pipeline."""

from __future__ import annotations

import gc
import importlib
import logging
import warnings
from contextlib import contextmanager
from pathlib import Path

import torch
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_PYANNOTE_TORCHCODEC_WARNING = (
    r"\s*torchcodec is not installed correctly so built-in audio decoding will fail\..*"
)


def detect_device(device_pref: str = "auto") -> tuple[str, str]:
    """Detect best available compute device and appropriate compute type.

    Note: ctranslate2 (WhisperX backend) only supports CUDA and CPU.
    MPS (Apple Silicon) is not supported and falls back to CPU.
    """
    if device_pref == "auto":
        if torch.cuda.is_available():
            return "cuda", "float16"
        else:
            return "cpu", "int8"
    elif device_pref == "cuda":
        if not torch.cuda.is_available():
            logger.warning("CUDA requested but not available, falling back to CPU")
            return "cpu", "int8"
        return "cuda", "float16"
    elif device_pref == "mps":
        logger.warning("MPS not supported by ctranslate2, falling back to CPU")
        return "cpu", "int8"
    else:
        return "cpu", "int8"


def get_compute_type(device: str) -> str:
    """Return optimal compute type for the given device."""
    return "float16" if device == "cuda" else "int8"


SPEAKER_LABELS = ("SPEAKER_00", "SPEAKER_01")


class TranscriptionResult(BaseModel):
    """Container for WhisperX transcription output."""

    segments: list[dict]
    language: str = "en"


class DiarizationResult(BaseModel):
    """Container for speaker diarization output."""

    segments: list[dict]


@contextmanager
def _suppress_torchcodec_warning():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=_PYANNOTE_TORCHCODEC_WARNING,
            category=UserWarning,
            module=r"pyannote\.audio\.core\.io",
        )
        yield


def _load_pyannote_pipeline_class():
    """Import pyannote under a narrow warning filter for optional torchcodec probing.

    We pass pyannote a preloaded waveform dict later, so its built-in decoder path is
    intentionally unused in this pipeline.
    """
    with _suppress_torchcodec_warning():
        return importlib.import_module("pyannote.audio").Pipeline


def transcribe_audio(
    audio_path: Path,
    model_name: str = "large-v2",
    device: str = "auto",
    compute_type: str = "float16",
    batch_size: int = 16,
    language: str = "en",
) -> TranscriptionResult:
    """Stage 1: Transcribe audio using WhisperX."""
    import whisperx

    detected_device, detected_compute = detect_device(device)
    compute = detected_compute if detected_device == "cpu" else (compute_type or detected_compute)

    logger.info("Loading WhisperX model: %s on %s with %s", model_name, detected_device, compute)
    with _suppress_torchcodec_warning():
        model = whisperx.load_model(
            model_name,
            device=detected_device,
            compute_type=compute,
            language=language,
            asr_options={
                "condition_on_previous_text": False,
            },
        )

    logger.info("Loading audio: %s", audio_path)
    audio = whisperx.load_audio(str(audio_path))

    logger.info("Transcribing with batch_size=%d", batch_size)
    result = model.transcribe(audio, batch_size=batch_size, language=language)

    logger.info("Transcription complete: %d segments", len(result.get("segments", [])))

    gc.collect()
    if detected_device == "cuda":
        torch.cuda.empty_cache()
    del model

    return TranscriptionResult(
        segments=result.get("segments", []),
        language=result.get("language", language),
    )


def align_transcription(
    transcription: TranscriptionResult,
    audio_path: Path,
    device: str = "auto",
) -> TranscriptionResult:
    """Stage 2: Forced alignment for word-level timestamps via wav2vec2."""
    import whisperx

    detected_device, _ = detect_device(device)
    logger.info("Loading alignment model for: %s", transcription.language)
    model_a, metadata = whisperx.load_align_model(
        language_code=transcription.language,
        device=detected_device,
    )

    audio = whisperx.load_audio(str(audio_path))
    result = whisperx.align(
        transcription.segments,
        model_a,
        metadata,
        audio,
        detected_device,
        return_char_alignments=False,
    )

    logger.info("Alignment complete: %d segments with word-level timestamps", len(result.get("segments", [])))

    gc.collect()
    if detected_device == "cuda":
        torch.cuda.empty_cache()
    del model_a

    return TranscriptionResult(
        segments=result.get("segments", []),
        language=transcription.language,
    )


def diarize_audio(
    audio_path: Path,
    hf_token: str,
    device: str = "auto",
) -> DiarizationResult:
    """Stage 3: Speaker diarization using pyannote directly."""
    pyannote_pipeline_class = _load_pyannote_pipeline_class()

    detected_device, _ = detect_device(device)
    logger.info("Loading diarization pipeline on %s", detected_device)

    diarize_pipeline = pyannote_pipeline_class.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=hf_token,
    )
    diarize_pipeline.to(torch.device(detected_device))

    # Pre-load audio as waveform dict to avoid torchcodec/FFmpeg version issues
    import soundfile as sf

    data, sample_rate = sf.read(str(audio_path))
    waveform = torch.from_numpy(data).float()
    if waveform.ndim == 1:
        waveform = waveform.unsqueeze(0)  # (samples,) -> (1, samples)
    else:
        waveform = waveform.T  # (samples, channels) -> (channels, samples)
    audio_input = {"waveform": waveform, "sample_rate": sample_rate}

    diarization = diarize_pipeline(
        audio_input,
        min_speakers=2,
        max_speakers=2,
    )

    # pyannote 4.x returns DiarizeOutput; extract the Annotation object
    annotation = getattr(diarization, "speaker_diarization", diarization)

    segments = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        segments.append({
            "start": float(turn.start),
            "end": float(turn.end),
            "speaker": str(speaker),
        })

    logger.info("Diarization complete: %d speaker segments", len(segments))

    gc.collect()
    if detected_device == "cuda":
        torch.cuda.empty_cache()
    del diarize_pipeline

    return DiarizationResult(segments=segments)


def assign_speakers(
    transcription: TranscriptionResult,
    diarization: DiarizationResult,
) -> TranscriptionResult:
    """Merge diarization speaker labels into aligned transcription segments."""
    import pandas as pd
    import whisperx

    diarize_df = pd.DataFrame(diarization.model_dump()["segments"])
    result_segments = transcription.segments.copy()

    result = {"segments": result_segments}
    result = whisperx.assign_word_speakers(diarize_df, result)

    return TranscriptionResult(
        segments=result.get("segments", []),
        language=transcription.language,
    )


def run_pipeline(
    audio_path: Path,
    output_dir: Path,
    youtube_id: str,
    hf_token: str,
    model_name: str = "large-v2",
    device: str = "auto",
    batch_size: int = 16,
    language: str = "en",
) -> TranscriptionResult:
    """Run the full 3-stage WhisperX pipeline: transcribe, align, diarize."""
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[Stage 1/3] Transcribing: %s", audio_path)
    transcription = transcribe_audio(
        audio_path=audio_path,
        model_name=model_name,
        device=device,
        batch_size=batch_size,
        language=language,
    )

    logger.info("[Stage 2/3] Aligning word-level timestamps")
    aligned = align_transcription(
        transcription=transcription,
        audio_path=audio_path,
        device=device,
    )

    logger.info("[Stage 3/3] Diarizing with 2-speaker constraint")
    diarization = diarize_audio(
        audio_path=audio_path,
        hf_token=hf_token,
        device=device,
    )

    result = assign_speakers(
        transcription=aligned,
        diarization=diarization,
    )

    raw_path = output_dir / f"{youtube_id}_raw.json"
    raw_path.write_text(result.model_dump_json(indent=2))
    logger.info("Raw output saved: %s", raw_path)

    return result
