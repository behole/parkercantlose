from unittest.mock import patch

from typer.testing import CliRunner

from parker.cli import app
from parker.models import Debate, VideoStatus

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_cli_process_command():
    mock_debate = Debate(
        id=1,
        youtube_id="dQw4w9WgXcQ",
        title="Test",
        url="https://youtube.com/watch?v=dQw4w9WgXcQ",
        status=VideoStatus.COMPLETED,
    )

    def process_with_progress(**kwargs):
        kwargs["progress_callback"]("[1/4] Downloading audio")
        return mock_debate

    with (
        patch("parker.cli.process_video", side_effect=process_with_progress),
        patch("parker.cli.get_settings"),
        patch("parker.cli.get_engine"),
        patch("parker.cli.init_db"),
    ):
        result = runner.invoke(app, ["process", "https://youtube.com/watch?v=dQw4w9WgXcQ"])
        assert result.exit_code == 0
        assert "[1/4] Downloading audio" in result.output
        assert "dQw4w9WgXcQ" in result.output


def test_cli_status_command():
    with (
        patch("parker.cli.get_status_summary", return_value={"total": 5, "completed": 3, "failed": 1, "pending": 1}),
        patch("parker.cli.get_settings"),
        patch("parker.cli.get_engine"),
        patch("parker.cli.init_db"),
    ):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "5" in result.output
