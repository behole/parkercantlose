# Phase 1 Research: Ingestion & Transcription Pipeline

**Phase:** 1 — Ingestion & Transcription Pipeline
**Researched:** 2026-04-09
**Question:** "What do I need to know to PLAN this phase well?"

---

## Summary

Phase 1 has **5 technical unknowns** that must be resolved before writing an implementation plan:

1. **WhisperX model selection** — which model size for debate audio quality
2. **Diarization accuracy** — will `num_speakers=2` produce usable speaker attribution
3. **GPU availability** — CUDA vs CPU vs API fallback
4. **Speaker identification** — SPEAKER_00/SPEAKER_01 → Parker vs caller assignment
5. **yt-dlp audio quality** — download format and pre-processing needs

Each unknown has a clear validation step. The plan should front-load these validations before building the full pipeline.

---

## 1. WhisperX: Configuration & Tuning

### Model Selection

| Model | VRAM | Speed (RTF) | Accuracy | Recommendation |
|-------|------|-------------|----------|----------------|
| `large-v2` | ~8GB | 70x realtime | Best available | **Start here** |
| `large-v3` | ~8GB | ~65x realtime | Marginally better on some benchmarks | Try if large-v2 insufficient |
| `turbo` | ~8GB | Faster than large-v2 | Nearly as accurate as large-v3 for English | Use if speed matters more |
| `medium` | ~3GB | ~100x realtime | Noticeably worse on noisy audio | Only if GPU memory constrained |
| `small` | ~1.5GB | Very fast | Significant accuracy loss on phone audio | Not recommended |

**Decision: Start with `large-v2`** — the best balance of accuracy and speed for noisy debate audio. `turbo` is a viable alternative if speed becomes an issue. Smaller models degrade noticeably on phone-quality caller audio.

### Critical Configuration Parameters

```python
model = whisperx.load_model(
    "large-v2",
    device="cuda",
    compute_type="float16",   # int8 for CPU or low VRAM
    language="en",            # English — skip language detection
    asr_options={
        "condition_on_previous_text": False,  # PREVENTS hallucination cascading
        "word_timestamps": True,               # Required for forced alignment
    },
    vad_options={
        "vad_on": True,       # Default — reduces hallucination during silence
    },
)

result = model.transcribe(
    audio,
    batch_size=16,            # Reduce to 4-8 if VRAM constrained
    language="en",
)
```

**Key insight:** `condition_on_previous_text=False` is already the default in WhisperX. This is critical for debate audio where silence gaps between speakers could trigger hallucination.

### Forced Alignment (Word-Level Timestamps)

After transcription, run forced alignment:

```python
model_a, metadata = whisperx.load_align_model(
    language_code="en",
    device="cuda",
)
result = whisperx.align(
    result["segments"],
    model_a,
    metadata,
    audio,
    "cuda",
    return_char_alignments=False,
)
```

**English alignment model:** `WAV2VEC2_ASR_LARGE_LV60K_960H` — automatically selected for `language_code="en"`. No manual configuration needed.

### Output Format

After alignment, `result["segments"]` contains:

```python
{
    "segments": [
        {
            "start": 0.0,
            "end": 5.2,
            "text": "I think that's a really interesting point.",
            "words": [
                {"word": "I", "start": 0.0, "end": 0.12, "score": 0.98},
                {"word": "think", "start": 0.12, "end": 0.45, "score": 0.95},
                # ... each word with start, end, and confidence score
            ]
        }
    ]
}
```

### VRAM Management

WhisperX loads three models sequentially: Whisper → alignment → diarization. Only one needs to be in VRAM at a time. The pattern:

```python
# 1. Transcribe
model = whisperx.load_model("large-v2", device="cuda")
result = model.transcribe(audio, batch_size=16)

# Free Whisper model
import gc, torch
gc.collect(); torch.cuda.empty_cache(); del model

# 2. Align
model_a, metadata = whisperx.load_align_model(language_code="en", device="cuda")
result = whisperx.align(result["segments"], model_a, metadata, audio, "cuda")

# Free alignment model
gc.collect(); torch.cuda.empty_cache(); del model_a

# 3. Diarize
diarize_model = whisperx.DiarizationPipeline(token=HF_TOKEN, device="cuda")
diarize_segments = diarize_model(audio, min_speakers=2, max_speakers=2)
result = whisperx.assign_word_speakers(diarize_segments, result)
```

This sequential pattern keeps peak VRAM at ~8GB for `large-v2`.

### Installation

```bash
# Using uv (recommended by WhisperX project)
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install whisperx

# Or for development
git clone https://github.com/m-bain/whisperX.git
cd whisperX
uv sync --all-extras --dev
```

**Dependencies:** Requires CUDA 12.8 for GPU acceleration. Requires ffmpeg system dependency.

---

## 2. Diarization: 2-Speaker Constraint & Accuracy

### pyannote `community-1` Pipeline

**Setup requirements:**
1. `pip install pyannote.audio`
2. Accept user conditions at https://hf.co/pyannote/speaker-diarization-community-1
3. Create HuggingFace access token at https://hf.co/settings/tokens
4. License: CC-BY-4.0 (free, attribution required)

**Performance benchmarks (DER, lower is better):**

| Benchmark | community-1 | precision-2 (premium) |
|-----------|-------------|----------------------|
| AISHELL-4 | 11.7% | 11.4% |
| AMI (IHM) | 17.0% | 12.9% |
| CALLHOME | 26.7% | 16.6% |
| VoxConverse | 11.2% | 8.5% |

**With `num_speakers=2` constraint:** DER drops significantly for 2-speaker scenarios. The constraint eliminates speaker counting errors (a major source of DER) and focuses the model on pure segmentation accuracy.

### Constrained Diarization via WhisperX

```python
from whisperx.diarize import DiarizationPipeline

diarize_model = DiarizationPipeline(token=HF_TOKEN, device="cuda")
diarize_segments = diarize_model(
    audio,
    min_speakers=2,    # Hard constraint: exactly 2 speakers
    max_speakers=2,    # Eliminates phantom speakers
)
result = whisperx.assign_word_speakers(diarize_segments, result)
```

**Output:** Each word gets a `speaker` field: `SPEAKER_00` or `SPEAKER_01`.

### Exclusive Speaker Diarization

`community-1` provides `exclusive_speaker_diarization` — a backported feature from the premium model. This provides non-overlapping speaker segments, making timestamp reconciliation with Whisper output much simpler. No words exist in the gap between speakers.

### Validation: What "Usable" Means

"Usable diarization" for this project means:
- **No phantom speakers** (constrained to 2, this should be solved)
- **Speaker swaps mid-turn** happen less than 5% of turns
- **Short interjections** ("yeah", "right") are attributed correctly at least 80% of the time
- **Turn boundaries** are within 500ms of actual speaker change

**Validation step:** Process 3 test videos. Manually check 10 turn boundaries per video (30 total). If >25/30 are correct, diarization is "usable."

### Parker Voice Embedding (Future Enhancement)

pyannote uses the `wespeaker` embedding model. The approach:

1. Extract 30-60 seconds of clean Parker audio from one video
2. Compute speaker embedding using pyannote's embedding model
3. For each diarized segment, compute similarity to Parker's embedding
4. The speaker with higher average similarity to Parker's embedding = Parker

This converts unsupervised clustering to supervised classification. **Not needed for Phase 1** — the simpler heuristic (more speaking time = Parker) works for initial validation. Voice embedding is a Phase 2+ enhancement.

---

## 3. GPU Availability & Fallback Strategy

### GPU Requirements

| Component | Minimum VRAM | Recommended VRAM | Notes |
|-----------|-------------|------------------|-------|
| Whisper large-v2 | 4GB (batch_size=4, int8) | 8GB (batch_size=16, float16) | Peak during batched transcription |
| Alignment model | ~2GB | ~4GB | Smaller than Whisper |
| pyannote diarization | ~2GB | ~4GB | Runs after Whisper is freed |

**Detection approach:**

```python
import torch

def get_device():
    if torch.cuda.is_available():
        return "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"  # Apple Silicon
    else:
        return "cpu"
```

### CPU Fallback

```python
model = whisperx.load_model("large-v2", device="cpu", compute_type="int8")
```

**CPU performance:** Large-v2 on CPU runs at approximately 1-2x realtime (vs 70x on GPU). A 30-minute video takes 15-30 minutes on CPU vs ~25 seconds on GPU. **Usable but slow.**

### Deepgram API Fallback

If no GPU is available and CPU is too slow, Deepgram Nova-3 with diarization:

| Component | Cost/Min | Notes |
|-----------|----------|-------|
| Nova-3 STT | $0.0077/min | Best quality model |
| Speaker Diarization | +$0.0020/min | Detects multiple speakers |
| **Total** | **$0.0097/min** | |

**Cost estimate:**
- 50 videos × 30 min average = 1500 minutes = ~25 hours
- 25 hours × $0.0097/min × 60 min/hr = **~$14.55**
- With $200 free credit, this is essentially free for the project scale

**Deepgram API call:**

```python
from deepgram import DeepgramClient, PrerecordedOptions

deepgram = DeepgramClient(DEEPGRAM_API_KEY)

options = PrerecordedOptions(
    model="nova-3",
    smart_format=True,
    diarize=True,
    punctuate=True,
    utterances=True,
)

result = deepgram.listen.prerecorded.v("1").transcribe_file(
    {"buffer": audio_bytes},
    options,
)
```

### Recommended Strategy

```
1. Detect GPU → if CUDA available, use WhisperX (local, free, fast)
2. No GPU → if Deepgram API key configured, use Deepgram (paid, fast, accurate)
3. No GPU, no API key → use WhisperX on CPU (free, slow, accurate)
```

**Default assumption: Mac development machine without CUDA.** Plan should support all three paths. The Deepgram fallback should be a configuration option, not a code path change.

---

## 4. Speaker Identification: SPEAKER_00 → Parker

### The Problem

pyannote produces `SPEAKER_00` and `SPEAKER_01`. These are arbitrary labels that may swap between videos. The system needs to identify which speaker is Parker.

### Heuristic Approaches (Phase 1)

**Heuristic 1: Speaking Time**
- Parker, as the host/debater, typically speaks more total time than callers
- For each video, compute total speaking time per speaker
- Longer speaking time = Parker
- **Accuracy estimate:** ~85-90% for debate format where Parker is the primary speaker

**Heuristic 2: First Speaker**
- Parker often opens the debate/introduces the topic
- The first speaker in the video is likely Parker
- **Accuracy estimate:** ~70-80% — depends on video format

**Heuristic 3: Combined**
- Use both heuristics: first speaker AND more speaking time
- If both agree → high confidence assignment
- If they disagree → flag for human review
- **Accuracy estimate:** ~90-95% for agreeing cases, 100% flagged for disagreeing

### Recommended Phase 1 Approach

```python
def identify_parker(diarized_segments):
    # Compute total speaking time per speaker
    speaker_time = {}
    first_speaker = None

    for seg in diarized_segments:
        speaker = seg["speaker"]
        duration = seg["end"] - seg["start"]
        speaker_time[speaker] = speaker_time.get(speaker, 0) + duration

        if first_speaker is None:
            first_speaker = speaker

    # Heuristic: longer speaking time = Parker
    time_parker = max(speaker_time, key=speaker_time.get)
    # Heuristic: first speaker = Parker
    first_parker = first_speaker

    confidence = "high" if time_parker == first_parker else "low"

    return {
        "parker": time_parker,
        "caller": min(speaker_time, key=speaker_time.get),
        "method": "speaking_time",
        "confidence": confidence,
        "needs_review": confidence == "low",
    }
```

### Phase 2 Enhancement: Voice Embedding

Extract Parker's voice embedding from one verified video, then use cosine similarity to identify Parker in all future videos. This is the gold standard but requires:
1. One manually verified transcript with correct Parker labels
2. Code to extract embedding from Parker's segments
3. Similarity comparison at inference time

---

## 5. yt-dlp: Audio Download

### Download Configuration

```python
import yt_dlp

def download_audio(url, output_dir):
    ydl_opts = {
        "format": "bestaudio/best",              # Best available audio quality
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",              # WAV for WhisperX (16kHz mono)
        }],
        "outtmpl": f"{output_dir}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        metadata = {
            "youtube_id": info["id"],
            "title": info["title"],
            "description": info.get("description", ""),
            "duration": info.get("duration", 0),
            "upload_date": info.get("upload_date", ""),
            "thumbnail": info.get("thumbnail", ""),
        }
        return metadata
```

### Audio Format for WhisperX

WhisperX needs **16kHz mono WAV** (loaded via `whisperx.load_audio()` which uses ffmpeg internally). Options:

| Approach | Pros | Cons |
|----------|------|------|
| Download original format, convert to WAV | Preserves original quality | Two-step process |
| Download best audio, post-process to WAV | yt-dlp handles conversion | Single step |
| Download as WAV directly | Simplest | WAV files are large |

**Recommendation:** Download best audio as original format (usually opus or m4a), convert to 16kHz mono WAV for processing. Store original format for potential re-processing.

### Audio Pre-Processing

Before WhisperX, consider:
1. **Normalize volume** — `ffmpeg -i input.wav -af "loudnorm" output.wav`
2. **Noise reduction** — Optional, may help with phone-quality caller audio
3. **Split on long silences** — Not needed; WhisperX VAD handles this

**Recommendation:** Minimal pre-processing. WhisperX's built-in VAD handles silence. Volume normalization may help but test without it first. Add pre-processing only if transcription quality is insufficient.

### Error Handling

```python
# yt-dlp errors to handle:
# - Video unavailable (deleted, private, age-restricted)
# - Rate limiting (HTTP 429)
# - Network timeouts
# - Invalid URL format

try:
    metadata = download_audio(url, output_dir)
except yt_dlp.utils.DownloadError as e:
    if "HTTP Error 429" in str(e):
        # Rate limited — exponential backoff
    elif "Video unavailable" in str(e):
        # Skip this video, mark as failed
    else:
        # Unknown error — log and continue
```

### Installation

```bash
# Recommended: nightly channel
uv pip install --pre "yt-dlp[default]"

# Requires ffmpeg system dependency
# macOS: brew install ffmpeg
# Ubuntu: apt install ffmpeg
```

---

## 6. SQLite Schema & Checkpointing

### Core Tables

```python
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional
import enum

class VideoStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    DIARIZING = "diarizing"
    COMPLETED = "completed"
    FAILED = "failed"

class Debate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    youtube_id: str = Field(unique=True, index=True)
    title: str
    url: str
    duration_seconds: Optional[float] = None
    upload_date: Optional[str] = None
    status: VideoStatus = Field(default=VideoStatus.PENDING)
    error_message: Optional[str] = None
    audio_path: Optional[str] = None
    raw_transcript_path: Optional[str] = None
    schema_version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    utterances: list["Utterance"] = Relationship(back_populates="debate")

class Utterance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debate_id: int = Field(foreign_key="debate.id", index=True)
    speaker: str                     # "parker" or "caller"
    speaker_raw: Optional[str] = None  # "SPEAKER_00" or "SPEAKER_01"
    text: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None
    words_json: Optional[str] = None  # JSON array of word-level data
    created_at: datetime = Field(default_factory=datetime.utcnow)
    debate: Optional[Debate] = Relationship(back_populates="utterances")
```

### Checkpointing Pattern

Each pipeline stage updates the `status` field. If the pipeline crashes, it resumes from the last successful stage:

```python
def process_video(url):
    debate = get_or_create_debate(url)

    if debate.status == VideoStatus.PENDING:
        debate = download_stage(debate)
        if debate.status == VideoStatus.FAILED:
            return debate

    if debate.status == VideoStatus.DOWNLOADED:
        debate = transcribe_stage(debate)
        if debate.status == VideoStatus.FAILED:
            return debate

    if debate.status == VideoStatus.TRANSCRIBED:
        debate = diarize_stage(debate)
        if debate.status == VideoStatus.FAILED:
            return debate

    return debate
```

### Per-Video Isolation

Each video is processed independently. Failure states:
- Store `error_message` on the Debate record
- Continue processing other videos
- Failed videos can be retried by resetting status to PENDING

---

## 7. Pipeline Architecture

### End-to-End Flow

```
YouTube URL
    │
    ▼
[1. DOWNLOAD] ─── yt-dlp downloads best audio
    │                Extract metadata (title, duration, upload_date)
    │                Convert to 16kHz mono WAV
    │                Save to data/audio/{youtube_id}.wav
    │                Status: DOWNLOADED
    │
    ▼
[2. TRANSCRIBE] ── WhisperX loads large-v2 model
    │                Transcribe with batch_size=16
    │                Run forced alignment (word-level timestamps)
    │                Save raw result to data/transcripts/{youtube_id}_raw.json
    │                Status: TRANSCRIBED
    │
    ▼
[3. DIARIZE] ───── pyannote community-1 with num_speakers=2
    │                Assign word-level speakers
    │                Apply Parker identification heuristic
    │                Create Utterance records in SQLite
    │                Status: COMPLETED
    │
    ▼
[Output] ───────── SQLite database with Debate + Utterance records
                    Ready for Phase 2 (human review)
```

### File Organization

```
data/
├── audio/                      # Downloaded audio files
│   ├── {youtube_id}.wav        # Processed audio (16kHz mono)
│   └── {youtube_id}.orig.*     # Original format (optional)
├── transcripts/                # Raw pipeline output
│   ├── {youtube_id}_raw.json   # WhisperX raw output
│   └── {youtube_id}_diarized.json  # After diarization
└── db/
    └── debates.db              # SQLite database
```

### CLI Interface

```bash
# Process single video
just process https://www.youtube.com/watch?v=VIDEO_ID

# Process multiple videos
just batch-process urls.txt

# Check status
just status

# Retry failed videos
just retry-failed
```

---

## 8. Dependencies & Prerequisites

### System Dependencies

| Dependency | Version | Purpose | Install |
|-----------|---------|---------|---------|
| Python | 3.11+ | Runtime | uv/python |
| ffmpeg | Latest | Audio processing | brew/apt install ffmpeg |
| CUDA Toolkit | 12.8 | GPU acceleration | NVIDIA installer (optional) |

### Python Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| whisperx | 3.8.5 | Transcription + alignment + diarization pipeline |
| pyannote.audio | 4.0.4 | Speaker diarization (bundled with whisperx) |
| yt-dlp | Latest (nightly) | YouTube audio download |
| sqlmodel | 0.0.22+ | SQLite ORM |
| pydantic | 2.x | Data validation |
| ffmpeg-python | Latest | Audio processing wrapper |

### API Keys Required

| Key | Purpose | How to Get |
|-----|---------|------------|
| HuggingFace token | pyannote model access | https://hf.co/settings/tokens (read access) |
| Deepgram API key | API fallback (optional) | https://console.deepgram.com/signup ($200 free credit) |

### HuggingFace Setup Steps

1. Create account at https://huggingface.co/join
2. Go to https://hf.co/pyannote/speaker-diarization-community-1
3. Accept user conditions (CC-BY-4.0 license)
4. Create read access token at https://hf.co/settings/tokens

---

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| WhisperX diarization accuracy insufficient on phone-quality audio | HIGH — blocks entire project | MEDIUM | Test on worst-quality video first. Deepgram fallback. |
| No GPU available, CPU too slow | MEDIUM — slow processing | MEDIUM (Mac dev machine) | Deepgram API fallback ($200 free credit covers entire project) |
| yt-dlp blocked by YouTube | MEDIUM — can't download | LOW | Nightly channel for latest fixes. Rate limiting with backoff. |
| pyannote community-1 license issues | LOW — model unavailable | LOW | CC-BY-4.0 is permissive. precision-2 as premium fallback. |
| CUDA installation issues | MEDIUM — no GPU | MEDIUM | CPU fallback + Deepgram. Docker with pre-installed CUDA. |
| Audio quality too poor for Whisper | HIGH — garbage transcripts | LOW | large-v2 handles noisy audio well. Pre-processing if needed. |

---

## 10. Validation Plan (Test Before Building)

Before writing the full pipeline, validate each unknown with minimal code:

### Step 1: Download Test (30 min)
- Download 3 test videos via yt-dlp
- Verify audio quality
- Store metadata

### Step 2: Transcription Test (1 hour)
- Run WhisperX on all 3 test videos
- Inspect transcript quality
- Verify word-level timestamps

### Step 3: Diarization Test (1 hour)
- Run pyannote with `num_speakers=2` on all 3 test videos
- Manually check 10 turn boundaries per video
- If >25/30 correct → proceed with full pipeline
- If <25/30 → evaluate Deepgram or Parker embedding approach

### Step 4: Speaker ID Test (30 min)
- Apply speaking-time heuristic
- Manually verify Parker identification
- If >90% correct → heuristic is sufficient for Phase 1

**Total validation time: ~3 hours** — do this before writing any pipeline code.

---

## 11. What I Know Now That I Didn't Know Before

1. **WhisperX already handles the alignment internally** — no need to wire Whisper + pyannote + alignment separately. The `assign_word_speakers` function does the word-to-speaker mapping.

2. **CPU fallback is viable** — slow (15-30 min per 30-min video) but works. Deepgram API is the better fallback for speed.

3. **`community-1` has exclusive speaker diarization** — this is a newer feature that provides non-overlapping segments, making timestamp reconciliation much simpler than expected.

4. **The Parker identification heuristic is simple** — more speaking time = Parker. This is a reasonable first pass. Voice embedding is an optimization, not a requirement.

5. **Deepgram's free $200 credit covers the entire project** — 50 hours × $0.0097/min × 60 = ~$29. This makes the API fallback essentially free for validation.

6. **yt-dlp nightly is the recommended channel** — not stable. This ensures YouTube compatibility is current.

7. **WhisperX frees models sequentially** — Whisper → alignment → diarization. Peak VRAM is ~8GB, not 8GB × 3. Sequential freeing means consumer GPUs work.

8. **pyannote requires accepting a license agreement** — this is a manual step that can't be automated. Plan for it in setup documentation.

---

## 12. Open Questions for Planning

These questions should be answered during the planning phase (not research):

1. **Should the pipeline be CLI-first or API-first?** Recommendation: CLI-first for Phase 1, wrap in FastAPI later. Simpler to debug.

2. **Should audio files be stored long-term?** Recommendation: Yes — store original + processed audio for re-processing. Storage is cheap (~50 MB per 30-min video × 50 videos = ~2.5 GB).

3. **What's the minimum viable output format?** Recommendation: SQLite with Debate + Utterance tables. JSON export for debugging.

4. **How many test videos before considering Phase 1 complete?** Recommendation: 3 successful end-to-end processes with manually verified diarization quality.

5. **Should the pipeline support incremental updates?** Recommendation: Yes — checkpointing pattern means re-running picks up where it left off. Idempotent: same URL = same result.

---

## Sources

- WhisperX GitHub: https://github.com/m-bain/whisperX (v3.8.5, 21.2k stars)
- WhisperX paper: Bain et al., "WhisperX: Time-Accurate Speech Transcription of Long-Form Audio", INTERSPEECH 2023
- pyannote-audio GitHub: https://github.com/pyannote/pyannote-audio (v4.0.4, 9.7k stars)
- pyannote community-1 model: https://hf.co/pyannote/speaker-diarization-community-1 (CC-BY-4.0)
- yt-dlp GitHub: https://github.com/yt-dlp/yt-dlp (156k stars, nightly recommended)
- Deepgram Pricing: https://deepgram.com/pricing (Nova-3 at $0.0077/min, diarization +$0.0020/min)
- faster-whisper GitHub: https://github.com/SYSTRAN/faster-whisper (CTranslate2 backend)
- Existing project research: `.planning/research/STACK.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md`

---
*Research for Phase 1: Ingestion & Transcription Pipeline*
*Researched: 2026-04-09*
