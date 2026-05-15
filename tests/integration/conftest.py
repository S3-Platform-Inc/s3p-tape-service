import pytest


@pytest.fixture(scope="session")
def pg_dsn():
    """Start a vanilla postgres in a testcontainer. Skips the entire integration
    suite if Docker is not reachable. SVC-2 will extend this to seed
    s3p-database init-scripts before yielding the DSN."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")
    try:
        pg = PostgresContainer("postgres:16-alpine")
        pg.start()
    except Exception as e:
        pytest.skip(f"Docker not reachable for testcontainers: {e}")
    try:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        yield url
    finally:
        pg.stop()


def skip_if_no_tape(conn):
    from tape_service.db.probe import tape_schema_present
    if not tape_schema_present(conn):
        pytest.skip("tape schema not yet present (s3p-database DB-1 not applied)")
