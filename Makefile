.PHONY: install install-dev dev test lint format clean seed reset-db celery celery-worker celery-beat celery-dev setup-billing

# Install dependencies (normal packages only)
install:
	uv sync

# Install dependencies (including dev packages)
install-dev:
	uv sync --dev

# Run tests (migrations first, then others)
test:
	uv run pytest tests/

# Run tests with coverage (migrations first)
test-cov:
	uv run coverage run -m pytest tests/
	uv run coverage report
	uv run coverage xml -o coverage.xml

# Lint code
lint:
	uv run --active ruff check .
	uv run --active ruff format --check .

# Format code
format:
	uv run --active ruff check --fix .
	uv run --active ruff format .

# Run web server
web:
	uv run python tcintercom/run.py web
