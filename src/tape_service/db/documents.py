from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row


@dataclass(frozen=True)
class DocumentRow:
    id: int
    sourceid: int
    title: str
    weblink: str
    published: datetime
    abstract: str | None
    text: str | None
    storagelink: str | None
    loaded: datetime | None
    otherdata: Any | None


def fetch_by_ids(conn: Connection, *, ids: list[int]) -> dict[int, DocumentRow]:
    """Hydrate documents by id. Missing ids are simply absent from the result."""
    if not ids:
        return {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, sourceid, title, weblink, published, abstract, text, "
            "       storagelink, loaded, otherdata "
            "FROM documents.document WHERE id = ANY(%s)",
            (ids,),
        )
        return {r["id"]: DocumentRow(**r) for r in cur.fetchall()}
