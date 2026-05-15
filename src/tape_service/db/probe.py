from __future__ import annotations

from psycopg import Connection


def tape_schema_present(conn: Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('tape.entry') IS NOT NULL")
        row = cur.fetchone()
    return bool(row and row[0])


def users_auth_by_token_present(conn: Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM pg_proc p "
            "  JOIN pg_namespace n ON p.pronamespace = n.oid "
            "  WHERE n.nspname = 'users' AND p.proname = 'auth_by_token'"
            ")"
        )
        row = cur.fetchone()
    return bool(row and row[0])
