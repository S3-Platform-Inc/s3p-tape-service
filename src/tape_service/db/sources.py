from __future__ import annotations

from psycopg import Connection


def fetch_names_by_ids(conn: Connection, *, ids: list[int]) -> dict[int, str]:
    """Look up source labels for an id list. Missing ids absent from result."""
    if not ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name FROM sources.source WHERE id = ANY(%s)",
            (ids,),
        )
        return {int(r[0]): r[1] for r in cur.fetchall()}
