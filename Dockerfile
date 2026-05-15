FROM python:3.11-slim AS base
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
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src"

CMD ["uvicorn", "tape_service.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--log-config", "/dev/null"]
