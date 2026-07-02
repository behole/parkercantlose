import os
from pathlib import Path
from unittest.mock import patch

import pytest

from parker.config import Settings


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    return data


@pytest.fixture
def settings(tmp_data_dir: Path) -> Settings:
    return Settings(
        hf_token="test-token",
        data_dir=tmp_data_dir,
        audio_dir=tmp_data_dir / "audio",
        transcript_dir=tmp_data_dir / "transcripts",
        db_path=tmp_data_dir / "db" / "debates.db",
        whisper_device="cpu",
        whisper_compute_type="int8",
    )


@pytest.fixture(autouse=True)
def env_setup():
    with patch.dict(os.environ, {"HF_TOKEN": "test-token"}):
        yield
