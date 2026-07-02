from pathlib import Path

import pytest

from parker.download import (
    DownloadError,
    DownloadResult,
    InvalidURLError,
    RateLimitError,
    VideoUnavailableError,
    extract_youtube_id,
)


def test_download_result_creation():
    result = DownloadResult(
        youtube_id="abc123",
        title="Test Video",
        url="https://youtube.com/watch?v=abc123",
        audio_path=Path("/tmp/abc123.wav"),
        duration_seconds=1800.0,
        upload_date="20250101",
        description="A test video description",
        thumbnail="https://img.youtube.com/vi/abc123/hqdefault.jpg",
    )
    assert result.youtube_id == "abc123"
    assert result.duration_seconds == 1800.0


def test_download_result_defaults():
    result = DownloadResult(
        youtube_id="abc123",
        title="Test",
        url="https://youtube.com/watch?v=abc123",
        audio_path=Path("/tmp/abc123.wav"),
    )
    assert result.duration_seconds is None
    assert result.upload_date is None
    assert result.description == ""
    assert result.thumbnail is None


def test_download_error_hierarchy():
    assert issubclass(VideoUnavailableError, DownloadError)
    assert issubclass(RateLimitError, DownloadError)


def test_video_unavailable_error():
    err = VideoUnavailableError("abc123", "Video unavailable")
    assert "abc123" in str(err)


def test_extract_youtube_id_standard():
    assert extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_youtube_id_short():
    assert extract_youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_youtube_id_embed():
    assert extract_youtube_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_youtube_id_with_params():
    assert extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120") == "dQw4w9WgXcQ"


def test_extract_youtube_id_bare_id():
    assert extract_youtube_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_youtube_id_invalid():
    with pytest.raises(InvalidURLError):
        extract_youtube_id("https://example.com/not-youtube")
