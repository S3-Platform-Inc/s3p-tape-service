from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row


@dataclass(frozen=True)
class AuthedUser:
    user_id: int
    privilege: Any  # JSON value as returned by users.auth_by_token

    @property
    def is_expert(self) -> bool:
        priv = self.privilege
        if isinstance(priv, dict):
            if priv.get("expert") is True:
                return True
            roles = priv.get("roles")
            if isinstance(roles, list) and "expert" in roles:
                return True
        if isinstance(priv, list):
            return "expert" in priv
        return False


def auth_by_token(conn: Connection, *, token: str) -> AuthedUser | None:
    """Call users.auth_by_token(_token text). Returns None on no match."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM users.auth_by_token(%s)", (token,))
        row = cur.fetchone()
    if not row:
        return None
    uid = row.get("user_id") or row.get("id")
    priv = row.get("privilege")
    if uid is None:
        return None
    return AuthedUser(user_id=int(uid), privilege=priv if priv is not None else {})


def sources_for(conn: Connection, *, user_id: int) -> list[int]:
    """users.sources(_id integer) returns integer[]"""
    with conn.cursor() as cur:
        cur.execute("SELECT users.sources(%s)", (user_id,))
        row = cur.fetchone()
    if not row or row[0] is None:
        return []
    return [int(x) for x in row[0]]


def roles_for(conn: Connection, *, user_id: int, source_id: int | None = None) -> list[int]:
    """users.roles overloads:
    users.roles(_id integer)             -> integer[]
    users.roles(_uid integer, _sid int)  -> SETOF (role row)
    """
    with conn.cursor() as cur:
        if source_id is None:
            cur.execute("SELECT users.roles(%s)", (user_id,))
            row = cur.fetchone()
            if not row or row[0] is None:
                return []
            return [int(x) for x in row[0]]
        cur.execute("SELECT id FROM users.roles(%s, %s)", (user_id, source_id))
        return [int(r[0]) for r in cur.fetchall()]
