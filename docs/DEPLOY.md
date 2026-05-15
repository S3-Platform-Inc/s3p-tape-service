# Deploying s3p-tape-service

The service runs on a private network. A reverse proxy is the only public
component and also serves the static `s3p-web-annotation` build, same-origin
with this API — so the session cookie is first-party and CORS is not needed.

## Topology

```
                      ┌─────────────────────┐
                      │  reverse proxy      │   public
                      │  (nginx/Caddy/etc)  │   TLS terminator
                      └──────────┬──────────┘
                                 │  private network
              ┌──────────────────┼──────────────────┐
              │                  │                  │
        ┌─────▼─────┐      ┌─────▼──────┐     ┌─────▼─────┐
        │  api      │      │  worker    │     │  redis    │
        │  uvicorn  │      │ apscheduler│     │ (persist) │
        └─────┬─────┘      │ + LISTEN   │     └───────────┘
              │            └─────┬──────┘
              └──────────────────┴──────────► s3p-database (platform DB)
                                              read-mostly (+ score.save)
```

Two compose-managed services + one external dependency (the platform DB).

## Required environment

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql://user:pw@host:5432/s3p` |
| `REDIS_URL` | yes | `redis://:PASSWORD@redis:6379/0` |
| `REDIS_PASSWORD` | yes | Used by the `redis` service's `requirepass` and embedded into `REDIS_URL`. Mint with `openssl rand -hex 32`. |
| `SESSION_SECRET` | yes | ≥32 chars random. `openssl rand -hex 32`. |
| `SESSION_COOKIE_SECURE` | no (default `true`) | Force `false` only behind a non-TLS dev proxy. |
| `LOG_LEVEL` | no (`INFO`) | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `WORKER_INTERVAL_SECONDS` | no (`60`) | How often the generator + heartbeat fire. |
| `LOGIN_RATE_LIMIT_PER_IP` | no (`10`) | Per-IP login-attempt ceiling. |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | no (`300`) | Rolling window. |
| `SESSION_ABSOLUTE_TTL_DAYS` | no (`30`) | Hard expiry. |
| `SESSION_IDLE_TTL_DAYS` | no (`14`) | Sliding idle expiry. |
| `WORKER_ADVISORY_LOCK_TTL_SECONDS` | no (`600`) | Auto-release if the worker dies mid-job. |
| `TAG` | no (`latest`) | Image tag pulled by `compose.prod.yaml`. |

## Reverse proxy

The reverse proxy serves the static frontend and forwards `/api/*` to the
api service. Strip the `/api` prefix:

```nginx
location /api/ {
    proxy_pass http://api:8000/;
    proxy_set_header Host              $host;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location / {
    root /var/www/s3p-web-annotation;
    try_files $uri /index.html;
}
```

The `Host` and `X-Forwarded-*` headers matter: the api reads
`X-Forwarded-For` to key the per-IP login rate-limit.

## Scaling rules

- **api**: safe to scale horizontally for read traffic. Sessions are in
  Redis. The login rate-limit is per-process today — if you run more
  than one api replica behind the proxy, expect ~Nx the effective
  per-IP ceiling. Re-shard via Redis INCR+EXPIRE if that bites.
- **worker**: keep at **exactly one** replica. Per-user advisory locks
  in Redis dedupe concurrent generation, so running >1 worker is safe,
  but the LISTEN thread on each extra replica would re-process every
  notification — costly with no benefit. One worker is enough for the
  expected scoring volume (≪1000 scores/min).
- **redis**: single instance with AOF is sufficient. Tape state is
  rebuildable from the platform DB; lose Redis and the next worker
  tick refills every user's tape (no data loss beyond live sessions
  forcing a re-login).
- **postgres** (the platform DB) is owned by `s3p-database`; this
  service is read-mostly there.

## Database requirements

The tape-service expects two upstream DB objects in `s3p-database`:

1. `users.auth_by_token(_token text) RETURNS TABLE(user_id int, privilege json)` — SHA-256 lookup over `users."user".auth->>'token_hash'`.
2. `AFTER INSERT ON score.score` trigger `score._notify_tape_inserted` emitting `pg_notify('tape_score_inserted', {user_id, document_id})`.

Both are materialised in `docs/sql/` for local dev (so integration tests
have something to hit). Production must apply them via the s3p-database
migration path.

## Score cleanup paths

Tape entries leave Redis via two independent paths:

1. **Web POST /score** — the api handler calls `score.save(...)` and
   then `ZREM tape:entries:<user_id>` inline. Zero observable latency.
2. **Anything-else** (legacy telegram bot, future bulk admin tools) —
   the PG trigger fires `pg_notify('tape_score_inserted', ...)` and the
   worker's LISTEN thread does the `ZREM`. Latency is one TCP roundtrip.

Both paths are idempotent (ZREM on an absent member returns 0). The
`/tape` handler also LEFT JOINs against `score.score` as a final
safety filter so a freshly-scored doc never leaks into a page.

## Redis backup / loss

- AOF persistence is on (`appendonly yes`). A clean redis restart loses
  nothing on top of the AOF.
- A hard loss of `redis-data` means: every session is invalidated
  (re-login required) and every user's `tape:entries:<u>` is empty.
  Re-mark `tape:cfg:<u>.dirty = "1"` for affected users (or wait one
  worker tick if they re-login and touch `/config`); the worker rebuilds
  from `documents.document` ⨝ `score.score`.

## Deploy commands

```sh
# Build & tag
TAG=v0.1.0
docker build -t s3p-tape-service:$TAG .
docker push <registry>/s3p-tape-service:$TAG

# Roll
export TAG DATABASE_URL REDIS_URL REDIS_PASSWORD SESSION_SECRET
docker compose -f compose.prod.yaml up -d
docker compose -f compose.prod.yaml ps
docker compose -f compose.prod.yaml logs --tail=200 api worker
```

## Health endpoints

- `GET /health` returns `200 {"status":"ok","db":"ok"}` when the api can
  reach Postgres. The compose healthcheck uses this.
- The worker emits a `worker.heartbeat` log line every
  `WORKER_INTERVAL_SECONDS`; absence in logs for >2 intervals means it's
  wedged. (No HTTP listener on the worker — `docker compose ps` shows
  its restart count as the operational signal.)

## Known gotchas

- The dev compose maps Postgres on host **15432** to dodge collisions
  with other platform stacks (e.g. `petrolab-db-1`). Production overlay
  does not expose pg at all.
- The worker holds **one dedicated psycopg connection** outside the
  pool, permanently in LISTEN mode. Budget for `pool_max_size + 1`
  connections to the platform DB per worker replica.
- `users.auth_by_token` uses `pgcrypto.digest()`. Ensure the extension
  is present in the production DB.
