from __future__ import annotations

import logging
import re
from pathlib import Path

import yt_dlp
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    def __init__(self, youtube_id: str, message: str):
        self.youtube_id = youtube_id
        super().__init__(f"[{youtube_id}] {message}")


class VideoUnavailableError(DownloadError):
    pass


class RateLimitError(DownloadError):
    pass


class InvalidURLError(DownloadError):
    pass


class DownloadResult(BaseModel):
    youtube_id: str
    title: str
    url: str
    audio_path: Path
    duration_seconds: float | None = None
    upload_date: str | None = None
    description: str = ""
    thumbnail: str | None = None

    model_config = {"arbitrary_types_allowed": True}


def extract_youtube_id(url: str) -> str:
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise InvalidURLError("", f"Cannot extract YouTube ID from URL: {url}")


def download_audio(url: str, output_dir: Path) -> DownloadResult:
    youtube_id = extract_youtube_id(url)
    output_dir.mkdir(parents=True, exist_ok=True)

    wav_path = output_dir / f"{youtube_id}.wav"

    if wav_path.exists():
        logger.info("Audio already exists: %s", wav_path)
        ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": "drop"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return _build_result(youtube_id, url, wav_path, info)

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            },
        ],
        "postprocessor_args": {
            "FFmpegExtractAudio": ["-ar", "16000", "-ac", "1"],
        },
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "drop",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        error_str = str(e)
        if "HTTP Error 429" in error_str:
            raise RateLimitError(youtube_id, f"Rate limited: {error_str}") from e
        elif "Video unavailable" in error_str or "Private video" in error_str:
            raise VideoUnavailableError(youtube_id, f"Unavailable: {error_str}") from e
        else:
            raise DownloadError(youtube_id, f"Download failed: {error_str}") from e

    if not wav_path.exists():
        raise DownloadError(youtube_id, f"WAV file not found after download: {wav_path}")

    return _build_result(youtube_id, url, wav_path, info)


def _build_result(youtube_id: str, url: str, wav_path: Path, info: dict) -> DownloadResult:
    return DownloadResult(
        youtube_id=youtube_id,
        url=url,
        audio_path=wav_path,
        title=info.get("title", ""),
        duration_seconds=info.get("duration"),
        upload_date=info.get("upload_date"),
        description=info.get("description", ""),
        thumbnail=info.get("thumbnail"),
    )
