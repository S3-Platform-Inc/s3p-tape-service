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
| `DATABASE_URL` | yes | `postgresql://user:pw@host:5432/s3p`. Platform's `s3p-database`. |
| `REDIS_URL` | yes | `redis://:PASSWORD@redis.internal:6379/0`. Platform's managed Redis; password is embedded in the URL — no separate `REDIS_PASSWORD` env var. |
| `SESSION_SECRET` | yes | ≥32 chars random. `openssl rand -hex 32`. |
| `SESSION_COOKIE_SECURE` | no (default `true`) | Force `false` only behind a non-TLS dev proxy. |
| `LOG_LEVEL` | no (`INFO`) | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `WORKER_INTERVAL_SECONDS` | no (`60`) | How often the generator + heartbeat fire. |
| `LOGIN_RATE_LIMIT_PER_IP` | no (`10`) | Per-IP login-attempt ceiling. |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | no (`300`) | Rolling window. |
| `SESSION_ABSOLUTE_TTL_DAYS` | no (`30`) | Hard expiry. |
| `SESSION_IDLE_TTL_DAYS` | no (`14`) | Sliding idle expiry. |
| `WORKER_ADVISORY_LOCK_TTL_SECONDS` | no (`600`) | Auto-release if the worker dies mid-job. |
| `TAG` | no (`latest`) | Image tag pulled by `docker-compose.yaml`. |

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

## CI/CD pipeline

Three GitHub Actions workflows form the release-to-stage chain. Every
`feat:` / `fix:` commit pushed to `main` ships to stage automatically.

```
push to main ─► release.yml ──► repository_dispatch "released"
                                          │
                              ┌───────────┴───────────┐
                              ▼                       ▼
                          docker.yml              deploy.yml
                          build + push to         SSH to stage VPS,
                          ghcr.io (semver         compose pull + up,
                          + latest tags)          /health check
```

`repository_dispatch` is the chaining mechanism because tags pushed by
the default `GITHUB_TOKEN` (used by semantic-release) do not trigger
downstream workflows — `repository_dispatch` is the documented escape
hatch and works without a PAT.

### Workflows

- **`.github/workflows/release.yml`** — runs `semantic-release` on every
  push to `main`. Conventional commits drive the bump (`feat`→minor,
  `fix`/`perf`→patch, breaking→major). Side effects: new git tag
  (`v1.2.0`), updated `CHANGELOG.md`, GitHub Release. Emits
  `repository_dispatch: released` with payload `{tag, version, sha}`
  only when a new version was actually cut.
- **`.github/workflows/docker.yml`** — builds the multi-arch image
  (linux/amd64, linux/arm64) and pushes to
  `ghcr.io/s3-platform-inc/s3p-tape-service`. Smoke-tested before
  publish (entry points on PATH, FastAPI app instantiates, runs as uid
  10001). SBOM + build provenance attestation attached. Tag rules:
  - on push to `main` → `latest`, `main`, `sha-<short>`
  - on `repository_dispatch: released` → `1.2.0`, `1.2`, `1`, `latest`, `sha-<short>` (built from the released git tag)
  - on PR → `pr-<N>`, `sha-<short>` (not pushed)
- **`.github/workflows/deploy.yml`** — SSHes into the stage VPS,
  rsyncs `docker-compose.yaml` (same file used in prod), writes
  `/opt/tape/.env` (mode 600) from repository Actions secrets, runs
  `docker compose pull && up -d --remove-orphans`, then polls
  `/health` for up to 2 minutes. Triggers: `repository_dispatch:
  released` (auto) or `workflow_dispatch` (manual, takes a tag input
  like `1.2.0` or `latest`).

### Repository Actions secrets

The deploy job reads secrets directly from the repository (no GitHub
Environment), so add them under **Settings → Secrets and variables
→ Actions → Secrets**. (If you later want a manual-approval gate
or branch-protection on deploys, re-introduce `environment: stage`
on the deploy job and migrate the secrets into that environment;
both work, this is just simpler.)

| Secret | Purpose |
|---|---|
| `VPS_HOST` | Hostname or IP of the stage VPS. |
| `VPS_PORT` | SSH port (typically `22`). |
| `VPS_USER` | SSH user (e.g. `deploy`); must be in the `docker` group. |
| `VPS_SSH_KEY` | Private key (OpenSSH) for `VPS_USER`. |
| `VPS_KNOWN_HOSTS` | Output of `ssh-keyscan -p <port> <host>`. Pins the host key. |
| `GHCR_USER` | GitHub username with `read:packages` on the image. |
| `GHCR_TOKEN` | PAT with `read:packages`. Used on the VPS for `docker login`. |
| `DATABASE_URL` | Stage postgres URL (platform `s3p-database`). |
| `REDIS_URL` | `redis://:<password>@<platform-redis-host>:6379/0`. Password embedded in the URL — no separate `REDIS_PASSWORD`. |
| `SESSION_SECRET` | ≥32 random chars. |

Optional repository **variables** (non-secret, under the same Actions
settings page → Variables tab; falls back to defaults if unset):
`VPS_APP_DIR` (`/opt/tape`), `HEALTH_PATH` (`/health`), `HEALTH_PORT`
(`8000`).

### One-time VPS prep

```sh
# As root or via sudo:
useradd -m -s /bin/bash deploy
usermod -aG docker deploy
install -d -o deploy -g deploy -m 750 /opt/tape

# Authorize the deploy key (public half of VPS_SSH_KEY):
sudo -u deploy mkdir -p ~deploy/.ssh && chmod 700 ~deploy/.ssh
sudo -u deploy tee -a ~deploy/.ssh/authorized_keys < your-deploy-key.pub
```

Smoke-check from your laptop:
`ssh -p <port> deploy@<host> 'docker compose version && id'`.

### Triggering a release

```sh
git commit -m "feat: add foo endpoint"
git push origin main
```

GitHub Actions cuts the tag, publishes the image, deploys to stage, and
health-checks. The deploy job writes a summary block to the run page
with the image ref, target host, and status.

### Rollback

Re-deploy the previous tag manually:

1. **Actions → Deploy (stage) → Run workflow** → tag: `1.1.0`.
2. Verify with `curl https://<stage-host>/api/health` and `docker compose ps` on the VPS.

Backward-incompatible DB migrations break this path — the previous image
expects the previous schema. Keep migrations forward-compatible (add
columns, don't drop; rename in two steps) until the new image has baked.

To revert a bad change that already shipped, push a `fix:` commit that
reverts it. Semantic-release will cut a new patch release through the
same pipeline. Don't move tags by hand — semantic-release tracks the
latest tag and will lose its place.

## Manual deploy (fallback)

Use only when the CI chain is broken (e.g. GitHub Actions outage) and
you have to roll the VPS by hand. The workflow's automatic path is
otherwise identical to these steps.

```sh
# On the VPS, as the deploy user, with /opt/tape/.env already populated:
cd /opt/tape
echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
TAG=1.1.0 docker compose --env-file .env pull
TAG=1.1.0 docker compose --env-file .env up -d --remove-orphans
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=200 api worker
```

For an emergency local build (skipping GHCR entirely):

```sh
docker build -t s3p-tape-service:local .
# Push to your registry, set TAG in .env to match, then roll as above.
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
