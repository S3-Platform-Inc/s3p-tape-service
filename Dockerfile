FROM python:3.11-slim AS base
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=0 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app
# README.md is required by hatchling because pyproject.toml declares
# readme = "README.md"; copy it alongside the lockfile so `uv sync` can
# build the project metadata.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src"

# Run as an unprivileged user. /app and its venv are world-readable
# (the install step ran as root) so this is the only chown needed.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin svc && \
    chown -R svc:svc /app
USER svc

# Use the console-script entry so our run() function controls uvicorn
# config (log_config=None, host/port). Avoids fighting uvicorn's CLI
# log-config parser.
CMD ["tape-service-api"]
