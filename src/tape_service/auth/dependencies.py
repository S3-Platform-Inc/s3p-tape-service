from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from ..errors import ApiError, ErrorCode
from ..settings import get_settings
from ..store import get_redis
from ..store import sessions as session_store


@dataclass(frozen=True)
class CurrentUser:
    user_id: int


def current_user(request: Request) -> CurrentUser:
    s = get_settings()
    raw = request.cookies.get(s.session_cookie_name)
    if not raw:
        raise ApiError(ErrorCode.UNAUTHORIZED, "missing session cookie")
    sess = session_store.validate(get_redis(), raw_session=raw)
    if sess is None:
        raise ApiError(ErrorCode.UNAUTHORIZED, "invalid or expired session")
    return CurrentUser(user_id=sess.user_id)
