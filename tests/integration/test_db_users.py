import psycopg
import pytest

from tape_service.db.probe import users_auth_by_token_present
from tape_service.db.users import auth_by_token, roles_for, sources_for

pytestmark = pytest.mark.integration


def test_auth_by_token_returns_none_for_unknown(pg_dsn):
    with psycopg.connect(pg_dsn) as conn:
        if not users_auth_by_token_present(conn):
            pytest.skip("users.auth_by_token not yet present (DB-1)")
        user = auth_by_token(conn, token="definitely-not-a-real-token-ZZZZZZZZ")
        assert user is None


def test_sources_returns_list_of_ints(pg_dsn):
    with psycopg.connect(pg_dsn) as conn:
        res = sources_for(conn, user_id=1)
        assert isinstance(res, list)
        for x in res:
            assert isinstance(x, int)


def test_roles_returns_list_of_ints(pg_dsn):
    with psycopg.connect(pg_dsn) as conn:
        res = roles_for(conn, user_id=1)
        assert isinstance(res, list)
        for x in res:
            assert isinstance(x, int)
