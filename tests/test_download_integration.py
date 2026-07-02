import os

import pytest

from parker.download import download_audio

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)


def test_download_real_video(tmp_path):
    result = download_audio(
        url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
        output_dir=tmp_path,
    )
    assert result.youtube_id == "jNQXAC9IVRw"
    assert result.audio_path.exists()
    assert result.audio_path.stat().st_size > 0
    assert result.title != ""
    assert result.duration_seconds is not None
    assert result.duration_seconds > 0
