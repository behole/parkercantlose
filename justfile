set dotenv-load

# Process a single YouTube video
process url:
    .venv/bin/python -m parker.cli process "{{url}}"

# Import transcript directly from YouTube (fast, no WhisperX)
import-yt url:
    .venv/bin/python -m parker.cli import-yt "{{url}}"

# Process multiple videos from a file (one URL per line)
batch-process file:
    .venv/bin/python -m parker.cli batch "{{file}}"

# Show pipeline status
status:
    .venv/bin/python -m parker.cli status

# Retry all failed videos
retry-failed:
    .venv/bin/python -m parker.cli retry

# Run tests
test:
    .venv/bin/python -m pytest -xvs

# Run linter
lint:
    .venv/bin/ruff check src/ tests/

# Format check
fmt:
    .venv/bin/ruff format --check src/ tests/

# Format fix
fmt-fix:
    .venv/bin/ruff format src/ tests/

# Start the web interface
serve:
    .venv/bin/python -m parker.cli serve

# Start on all interfaces (for network access)
serve-public:
    .venv/bin/python -m parker.cli serve --host 0.0.0.0
