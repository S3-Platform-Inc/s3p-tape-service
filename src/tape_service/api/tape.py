from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth.dependencies import CurrentUser, current_user
from ..db import get_pool
from ..db.documents import fetch_by_ids
from ..db.roles import fetch_names_by_ids as fetch_role_names
from ..db.score import AlreadyScored
from ..db.score import save as score_save
from ..db.users import roles_for
from ..errors import ApiError, ErrorCode
from ..schemas.score import ScoreRequest
from ..schemas.tape import RoleRef, TapeDocument, TapeItem, TapePage
from ..store import get_redis
from ..store import tape as tape_store

router = APIRouter()


def _filter_already_scored(conn, *, user_id: int, doc_ids: list[int]) -> set[int]:
    """Defence in depth: even with the listener thread the API can race
    against a fresh score.save / pg_notify cycle. LEFT JOIN against
    score.score so the page never returns an entry the user has scored."""
    if not doc_ids:
        return set()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT document_id FROM score.score WHERE user_id = %s AND document_id = ANY(%s)",
            (user_id, doc_ids),
        )
        return {int(r[0]) for r in cur.fetchall()}


def _roles_by_source(conn, *, user_id: int, source_ids: set[int]) -> dict[int, list[RoleRef]]:
    """Map source_id → roles the user can score under for docs in that source."""
    out: dict[int, list[RoleRef]] = {}
    all_role_ids: set[int] = set()
    per_source: dict[int, list[int]] = {}
    for sid in source_ids:
        rids = roles_for(conn, user_id=user_id, source_id=sid)
        per_source[sid] = rids
        all_role_ids.update(rids)
    names = fetch_role_names(conn, ids=sorted(all_role_ids))
    for sid, rids in per_source.items():
        out[sid] = [RoleRef(id=rid, name=names.get(rid)) for rid in rids]
    return out


@router.get("/tape", response_model=TapePage)
def read_tape(
    after: int | None = Query(default=None, ge=0),
    user: CurrentUser = Depends(current_user),
) -> TapePage:
    r = get_redis()
    cfg = tape_store.get_config(r, user_id=user.user_id)
    if cfg is None:
        return TapePage(
            items=[],
            next_position=None,
            state="empty",
            display_mode="compact",
        )

    rows = tape_store.list_entries_page(
        r,
        user_id=user.user_id,
        after_position=after,
        limit=cfg.page_size,
    )
    if not rows:
        total = tape_store.count_entries(r, user_id=user.user_id)
        state = "preparing" if total == 0 and cfg.dirty else "empty"
        return TapePage(
            items=[],
            next_position=None,
            state=state,
            display_mode=cfg.display_mode,
        )

    doc_ids = [doc_id for (_pos, doc_id) in rows]
    with get_pool().connection() as conn:
        conn.autocommit = True
        docs = fetch_by_ids(conn, ids=doc_ids)
        already_scored = _filter_already_scored(
            conn,
            user_id=user.user_id,
            doc_ids=doc_ids,
        )
        source_ids = {docs[d].sourceid for d in doc_ids if d in docs and d not in already_scored}
        roles_by_src = _roles_by_source(
            conn,
            user_id=user.user_id,
            source_ids=source_ids,
        )

    items: list[TapeItem] = []
    for position, doc_id in rows:
        if doc_id in already_scored:
            # The listener may not have caught up yet; safety-filter the page.
            tape_store.remove_entry(r, user_id=user.user_id, document_id=doc_id)
            continue
        d = docs.get(doc_id)
        if d is None:
            continue
        td = TapeDocument(
            id=d.id,
            source_id=d.sourceid,
            title=d.title,
            link=d.weblink,
            published=d.published,
            abstract=d.abstract,
            text=d.text if cfg.display_mode == "detailed" else None,
        )
        # entry_id isn't carried in Redis sorted sets (members are doc ids);
        # expose position as the stable list key for the frontend.
        items.append(
            TapeItem(
                entry_id=position,
                position=position,
                document=td,
                roles=roles_by_src.get(d.sourceid, []),
            )
        )

    next_position = rows[-1][0] if len(rows) == cfg.page_size else None
    return TapePage(
        items=items,
        next_position=next_position,
        state="ok" if items else "empty",
        display_mode=cfg.display_mode,
    )


@router.post("/score")
def submit_score(
    payload: ScoreRequest,
    user: CurrentUser = Depends(current_user),
) -> dict:
    try:
        with get_pool().connection() as conn:
            conn.autocommit = True
            score_id = score_save(
                conn,
                user_id=user.user_id,
                document_id=payload.document_id,
                role_id=payload.role_id,
                verdict={"verdict": payload.verdict},
                comment=payload.comment,
            )
    except AlreadyScored:
        raise ApiError(
            ErrorCode.ALREADY_SCORED,
            "this document has already been scored by you",
        ) from None

    # Inline tape cleanup — no waiting on the LISTEN thread for the web path.
    # The listener is still the safety net for non-web score paths.
    tape_store.remove_entry(
        get_redis(),
        user_id=user.user_id,
        document_id=payload.document_id,
    )
    return {"score_id": score_id}
