set dotenv-load

# Process a single YouTube video
process url:
    python -m parker.cli process "{{url}}"

# Process multiple videos from a file (one URL per line)
batch-process file:
    python -m parker.cli batch "{{file}}"

# Show pipeline status
status:
    python -m parker.cli status

# Retry all failed videos
retry-failed:
    python -m parker.cli retry

# Run tests
test:
    python -m pytest -xvs

# Run linter
lint:
    ruff check src/ tests/

# Format check
fmt:
    ruff format --check src/ tests/

# Format fix
fmt-fix:
    ruff format src/ tests/

# Start the web interface
serve:
    .venv/bin/python -m parker.cli serve

# Start on all interfaces (for network access)
serve-public:
    .venv/bin/python -m parker.cli serve --host 0.0.0.0
