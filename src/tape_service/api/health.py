from fastapi import APIRouter
from ..db import get_pool

router = APIRouter()


@router.get("/health")
def health() -> dict:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    return {"status": "ok", "db": "ok"}
