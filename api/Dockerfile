FROM python:3.12-slim

RUN useradd -m -u 1001 app

WORKDIR /app

# curl is used by the container healthcheck (GET /health).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (the project's Python toolchain).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Avoid uv touching the lockfile / re-resolving at runtime.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1

# Install dependencies first (cached layer; project itself installed below).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the application + migrations, then install the project (editable, so
# quid_api.cli resolves REPO_ROOT to /app and finds /app/alembic.ini at runtime).
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

# The SQLite database and logs live under /app/.data (mount this as a volume).
RUN mkdir -p .data && chown -R app:app /app

USER app

EXPOSE 8000

# Apply migrations, then serve. create_app() does NOT migrate on startup, so the
# migrate step is required before the server can answer requests.
CMD ["sh", "-c", "uv run quid-api migrate && uv run quid-api serve --host 0.0.0.0 --port 8000"]
