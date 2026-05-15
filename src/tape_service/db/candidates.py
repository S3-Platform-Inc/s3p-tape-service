from __future__ import annotations

from datetime import datetime
from typing import Literal

from psycopg import Connection

Ordering = Literal["asc", "desc"]


def candidates_for_user(
    conn: Connection,
    *,
    user_id: int,
    source_ids: list[int],
    date_from: datetime | None,
    date_to: datetime | None,
    ordering: Ordering,
    exclude_ids: list[int] | None = None,
) -> list[int]:
    """Return document ids in the user's configured sources/date range
    that have not yet been scored by them and are not already present
    in their tape (caller passes the existing ids via exclude_ids).

    Tape-side filtering is done in Python (since tape state lives in
    Redis, not PG); score-side filtering is a SQL NOT EXISTS.
    """
    if not source_ids:
        return []
    # Whitelisted by Literal type — never user input. Postgres won't
    # accept ORDER BY direction as a bind parameter, so the constant
    # has to be interpolated; the conditional above ensures it's one of
    # exactly two literal strings.
    order_clause = "DESC" if ordering == "desc" else "ASC"
    sql = (
        "SELECT d.id FROM documents.document d "  # noqa: S608
        "WHERE d.sourceid = ANY(%s) "
        "  AND (%s::timestamptz IS NULL OR d.published >= %s::timestamptz) "
        "  AND (%s::timestamptz IS NULL OR d.published <= %s::timestamptz) "
        "  AND NOT EXISTS ("
        "      SELECT 1 FROM score.score s "
        "      WHERE s.user_id = %s AND s.document_id = d.id"
        "  ) "
        f"ORDER BY d.published {order_clause} NULLS LAST"
    )
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (source_ids, date_from, date_from, date_to, date_to, user_id),
        )
        rows = [int(r[0]) for r in cur.fetchall()]
    if not exclude_ids:
        return rows
    excluded = set(exclude_ids)
    return [r for r in rows if r not in excluded]
