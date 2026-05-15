import psycopg
import pytest

from tape_service.db.documents import fetch_by_ids

pytestmark = pytest.mark.integration


def test_fetch_by_ids_empty_input(pg_dsn):
    with psycopg.connect(pg_dsn) as conn:
        assert fetch_by_ids(conn, ids=[]) == {}


def test_fetch_by_ids_seed_documents(pg_dsn):
    with psycopg.connect(pg_dsn) as conn:
        docs = fetch_by_ids(conn, ids=[1, 3, 5])
    assert set(docs.keys()) == {1, 3, 5}
    d1 = docs[1]
    assert d1.id == 1
    assert d1.sourceid == 1
    assert d1.title.startswith("Test doc")
    assert d1.weblink.startswith("https://example.test/")


def test_fetch_by_ids_skips_missing(pg_dsn):
    with psycopg.connect(pg_dsn) as conn:
        docs = fetch_by_ids(conn, ids=[1, 99_999])
    assert set(docs.keys()) == {1}
