from __future__ import annotations

import json
from typing import Any

from psycopg import Connection
from psycopg.errors import UniqueViolation


class AlreadyScored(Exception):
    """The user has already scored this document under this role."""


def save(
    conn: Connection,
    *,
    user_id: int,
    document_id: int,
    role_id: int,
    verdict: dict[str, Any],
    comment: str | None,
) -> int:
    """Call score.save(_uid, telegram_id, _did, _rid, _score, _comment).

    The web flow has no telegram id, so telegram_id is always NULL.
    Duplicate (user_id, role_id, document_id) raises AlreadyScored so
    callers can surface ErrorCode.ALREADY_SCORED to the frontend without
    leaking the underlying DB error.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT score.save(%s, %s, %s, %s, %s::json, %s)",
                (user_id, None, document_id, role_id, json.dumps(verdict), comment),
            )
            row = cur.fetchone()
        return int(row[0])
    except UniqueViolation as e:
        raise AlreadyScored(str(e)) from e
