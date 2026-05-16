from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

# Integration tests target the already-running dev compose stack:
#   docker compose up -d pg redis
# The DSN/URL defaults match compose.yaml's host ports + dev credentials.
# Override via env if your local stack uses different ports or credentials.


def _default_database_url() -> str:
    # docker compose reads REDIS_PASSWORD from the repo's .env to start redis
    # with --requirepass. Mirror that here so tests don't silently skip when
    # the stack runs with a non-default password. DATABASE_URL in .env is
    # intentionally NOT consumed — it may point at a remote DB.
    repo_env = Path(__file__).resolve().parents[2] / ".env"
    file_database_url = dotenv_values(repo_env).get("DATABASE_URL") if repo_env.exists() else None
    database_url = (
        os.environ.get("DATABASE_URL")
        or file_database_url
        or "postgresql://sppadmin:devpass@localhost:15432/s3p"
    )
    return database_url


def _default_redis_url() -> str:
    # docker compose reads REDIS_PASSWORD from the repo's .env to start redis
    # with --requirepass. Mirror that here so tests don't silently skip when
    # the stack runs with a non-default password. DATABASE_URL in .env is
    # intentionally NOT consumed — it may point at a remote DB.
    repo_env = Path(__file__).resolve().parents[2] / ".env"
    file_password = dotenv_values(repo_env).get("REDIS_PASSWORD") if repo_env.exists() else None
    password = os.environ.get("REDIS_PASSWORD") or file_password or "devredis"
    return f"redis://:{password}@localhost:6379/0"


@pytest.fixture(scope="session")
def pg_dsn() -> str:
    """Yield the dev DB DSN, or skip if Postgres isn't reachable.

    Tests rely on docs/sql/*.sql having been applied by docker-entrypoint-initdb.d
    when `pg` first started. If you need to re-seed, recreate the volume:
        docker compose down -v pg && docker compose up -d pg
    """
    import psycopg

    dsn = _default_database_url()
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception as e:
        pytest.skip(f"dev postgres not reachable at {dsn}: {e}")
    return dsn


@pytest.fixture(scope="session")
def redis_url() -> str:
    """Yield the dev Redis URL, or skip if Redis isn't reachable."""
    import redis

    url = os.environ.get("REDIS_URL") or _default_redis_url()
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=2)
        client.ping()
        client.close()
    except Exception as e:
        pytest.skip(f"dev redis not reachable at {url}: {e}")
    return url


@pytest.fixture
def redis_client(redis_url: str):
    """A fresh redis.Redis bound to the dev URL. Caller is responsible for
    namespacing keys it touches so concurrent tests don't collide."""
    import redis

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        yield client
    finally:
        client.close()


def skip_if_no_auth_by_token(conn) -> None:
    from tape_service.db.probe import users_auth_by_token_present

    if not users_auth_by_token_present(conn):
        pytest.skip("users.auth_by_token not present in dev DB (apply docs/sql/04)")
