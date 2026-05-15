# s3p-tape-service

Backend for the S3 Platform web annotation tool. FastAPI + background worker
over PostgreSQL (s3p-database).

## Run (dev)

    cp .env.sample .env
    uv sync
    docker compose up --build

API: http://localhost:8000/health

## Tests

    uv run pytest                     # unit tests (no Docker needed)
    uv run pytest -m integration      # integration tests (Docker required)

## Layout

    src/tape_service/         # package — api tier and worker share this code
        main.py               # FastAPI app factory + /health + lifespan
        worker_entry.py       # `python -m tape_service.worker_entry`
        settings.py           # typed env config (pydantic-settings)
        db/                   # psycopg pool + DB access layer
        auth/                 # token auth, sessions, rate-limit
        api/                  # HTTP routes
        schemas/              # Pydantic request/response models
        worker/               # APScheduler bootstrap + generation jobs

## Implementation plan

See `docs/superpowers/plans/2026-05-15-tape-service.md` (gitignored).
