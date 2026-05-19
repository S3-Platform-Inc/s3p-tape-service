from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.dependencies import CurrentUser, current_user
from ..db import get_pool
from ..db.sources import fetch_names_by_ids
from ..db.users import sources_for
from ..errors import ApiError, ErrorCode
from ..schemas.config import ConfigResponse, ConfigUpdate, SourceRef
from ..store import events, get_redis
from ..store import tape as tape_store

router = APIRouter(prefix="/config")

_DEFAULT_ORDERING = "desc"
_DEFAULT_DISPLAY_MODE = "compact"
_DEFAULT_PAGE_SIZE = 20


def _hydrate_sources(user_id: int) -> tuple[list[int], list[SourceRef]]:
    """Look up the user's allowed source ids from PG and label them.
    Returns (allowed_ids, [SourceRef])."""
    with get_pool().connection() as conn:
        conn.autocommit = True
        allowed = sources_for(conn, user_id=user_id)
        names = fetch_names_by_ids(conn, ids=allowed)
    return allowed, [SourceRef(id=i, name=names.get(i)) for i in allowed]


@router.get("", response_model=ConfigResponse)
def read_config(user: CurrentUser = Depends(current_user)) -> ConfigResponse:
    r = get_redis()
    cfg = tape_store.get_config(r, user_id=user.user_id)
    selected = tape_store.get_config_sources(r, user_id=user.user_id)
    _, available = _hydrate_sources(user.user_id)

    if cfg is None:
        return ConfigResponse(
            ordering=_DEFAULT_ORDERING,
            display_mode=_DEFAULT_DISPLAY_MODE,
            page_size=_DEFAULT_PAGE_SIZE,
            date_from=None,
            date_to=None,
            dirty=False,
            selected_source_ids=selected,
            available_sources=available,
        )
    return ConfigResponse(
        ordering=cfg.ordering,
        display_mode=cfg.display_mode,
        page_size=cfg.page_size,
        date_from=cfg.date_from,
        date_to=cfg.date_to,
        dirty=cfg.dirty,
        selected_source_ids=selected,
        available_sources=available,
    )


@router.put("", response_model=ConfigResponse)
def write_config(
    payload: ConfigUpdate,
    user: CurrentUser = Depends(current_user),
) -> ConfigResponse:
    # Whitelist source ids against users.sources(user_id) before persisting.
    allowed, _ = _hydrate_sources(user.user_id)
    requested = set(payload.selected_source_ids)
    bad = requested - set(allowed)
    if bad:
        raise ApiError(
            ErrorCode.FORBIDDEN,
            f"sources not permitted for this user: {sorted(bad)}",
        )

    r = get_redis()
    tape_store.upsert_config(
        r,
        user_id=user.user_id,
        ordering=payload.ordering,
        display_mode=payload.display_mode,
        page_size=payload.page_size,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )
    tape_store.set_config_sources(
        r,
        user_id=user.user_id,
        source_ids=list(payload.selected_source_ids),
    )
    # Both upsert_config and set_config_sources flip the dirty flag to "1",
    # so the worker will pick this user up on the next tick.
    events.publish(
        r,
        user_id=user.user_id,
        event=events.make_schedule_queued(user.user_id, "config_dirty"),
    )
    return read_config(user=user)
