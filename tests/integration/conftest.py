from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

log = logging.getLogger(__name__)

S3P_DATABASE_REPO = Path(
    os.environ.get(
        "S3P_DATABASE_REPO",
        "/Users/barista/Developer/s3-platform/projects/s3p-database",
    )
)
INIT_SCRIPTS_DIR = S3P_DATABASE_REPO / "init-scripts"


def _init_scripts() -> list[Path]:
    if not INIT_SCRIPTS_DIR.is_dir():
        return []
    return sorted(INIT_SCRIPTS_DIR.glob("*.sql"))


def _seed_database(dsn: str, scripts: list[Path]) -> None:
    """Execute s3p-database init-scripts in order.

    The scripts assume the bootstrap user is `sppadmin` and that two more
    roles (`spptgbot`, `s3pfunc`) exist. We start the container as
    `sppadmin` and let `1-roles.sql` create the other two. Any
    `CREATE ROLE sppadmin` line will raise DuplicateObject — we tolerate
    that error class only and surface anything else as a warning so we
    notice real DDL drift.
    """
    import psycopg
    from psycopg.errors import DuplicateObject

    with psycopg.connect(dsn, autocommit=True) as conn:
        for sql_file in scripts:
            sql = sql_file.read_text()
            try:
                conn.execute(sql)
            except DuplicateObject as e:
                log.warning("init-script %s: duplicate ignored: %s", sql_file.name, e)
            except Exception as e:
                log.warning(
                    "init-script %s failed (%s: %s); dependent tests will skip "
                    "via the schema probe if required objects are missing",
                    sql_file.name, type(e).__name__, e,
                )


@pytest.fixture(scope="session")
def pg_dsn():
    """Start a postgres testcontainer, run s3p-database init-scripts, yield DSN.

    Skips the entire integration suite if Docker isn't reachable.
    """
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")
    try:
        pg = PostgresContainer(
            "postgres:16-alpine",
            username="sppadmin",
            password="testpass",
            dbname="s3p",
        )
        pg.start()
    except Exception as e:
        pytest.skip(f"Docker not reachable for testcontainers: {e}")
    try:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        _seed_database(url, _init_scripts())
        yield url
    finally:
        pg.stop()


def skip_if_no_tape(conn) -> None:
    from tape_service.db.probe import tape_schema_present
    if not tape_schema_present(conn):
        pytest.skip("tape schema not yet present (s3p-database DB-1 not applied)")


def skip_if_no_auth_by_token(conn) -> None:
    from tape_service.db.probe import users_auth_by_token_present
    if not users_auth_by_token_present(conn):
        pytest.skip("users.auth_by_token not yet present (s3p-database DB-1 not applied)")
