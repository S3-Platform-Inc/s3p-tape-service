# s3p-tape-service

Backend for the S3 Platform web annotation tool. FastAPI + background
worker. Reads the platform DB (`s3p-database`) read-mostly; keeps its own
state (sessions, tape entries, advisory locks) in Redis.

## Quickstart (dev)

    cp .env.sample .env                       # adjust if needed
    uv sync
    docker compose up -d pg redis             # seeds docs/sql/* on first start
    docker compose up -d --build api worker

API root: http://localhost:8000/health → `{"status":"ok","db":"ok"}`

## Smoke

    # Login as the Alpha test expert (token from docs/sql/05-fake-data.sql)
    curl -sS -c /tmp/c.txt -X POST http://localhost:8000/auth/login \
      -H 'content-type: application/json' \
      -d '{"token":"expert-alpha-token-XXXXXXXXXXXXXXXX"}'

    # Subscribe to both seed sources; worker rebuilds on next tick
    curl -sS -b /tmp/c.txt -X PUT http://localhost:8000/config \
      -H 'content-type: application/json' \
      -d '{"ordering":"asc","display_mode":"detailed","page_size":3,
           "selected_source_ids":[1,2]}'

    # Read the tape after the worker's first interval
    curl -sS -b /tmp/c.txt http://localhost:8000/tape

    # Score a doc — it disappears from the next /tape call
    curl -sS -b /tmp/c.txt -X POST http://localhost:8000/score \
      -H 'content-type: application/json' \
      -d '{"document_id":1,"role_id":1,"verdict":"yes"}'

## Tests

    uv run pytest                     # unit tests (no Docker needed)
    uv run pytest -m integration      # integration tests (uses the running dev stack)

## API

| Method | Path           | Auth     | Notes |
|--------|----------------|----------|-------|
| POST   | `/auth/login`  | —        | Body `{token}`, rate-limited per IP. Sets `s3p_session` cookie. |
| POST   | `/auth/logout` | session  | Revokes the session, clears the cookie. |
| GET    | `/auth/me`     | session  | Returns `{user_id}`. |
| GET    | `/config`      | session  | Tape config + selectable sources. |
| PUT    | `/config`      | session  | Update config; marks tape dirty for the worker. |
| GET    | `/tape`        | session  | Paginated tape page (`?after=N`); state ∈ {ok, empty, preparing}. |
| POST   | `/score`       | session  | Submit a verdict; removes the doc from the tape. |
| GET    | `/health`      | —        | Liveness + DB probe. |

Errors follow `{"error":{"code":"<MACHINE_CODE>","message":"..."}}` with a
JSON content-type. Codes: `UNAUTHORIZED`, `FORBIDDEN`, `INVALID_REQUEST`,
`RATE_LIMITED`, `ALREADY_SCORED`, `INTERNAL`.

## Layout

    src/tape_service/         # package — api tier and worker share this code
        main.py               # FastAPI app factory + /health + lifespan
        worker_entry.py       # `python -m tape_service.worker_entry`
        settings.py           # typed env config (pydantic-settings)
        errors.py             # ErrorCode enum + handler
        db/                   # psycopg pool + read-mostly platform DB wrappers
        store/                # redis-backed tape state (sessions, entries, locks)
        auth/                 # current_user, rate-limit
        api/                  # HTTP routes
        schemas/              # Pydantic request/response models
        worker/               # APScheduler bootstrap, generator, LISTEN listener

## Production deploy

See `docs/DEPLOY.md` for the prod compose overlay, reverse-proxy
snippet, scaling rules, and operational runbook.

## Implementation plan

See `docs/superpowers/plans/2026-05-15-tape-service.md` (gitignored).
