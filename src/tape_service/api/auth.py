from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ..auth.dependencies import CurrentUser, current_user
from ..auth.rate_limit import TokenBucket
from ..db import get_pool
from ..db.users import auth_by_token
from ..errors import ApiError, ErrorCode
from ..schemas.auth import LoginRequest, MeResponse
from ..settings import get_settings
from ..store import get_redis
from ..store import sessions as session_store

router = APIRouter(prefix="/auth")

_login_limiter: TokenBucket | None = None


def _limiter() -> TokenBucket:
    global _login_limiter
    if _login_limiter is None:
        s = get_settings()
        _login_limiter = TokenBucket(
            capacity=s.login_rate_limit_per_ip,
            window_seconds=s.login_rate_limit_window_seconds,
        )
    return _login_limiter


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login")
def login(req: LoginRequest, request: Request, response: Response) -> MeResponse:
    s = get_settings()
    if not _limiter().allow(_client_ip(request)):
        raise ApiError(ErrorCode.RATE_LIMITED, "too many login attempts")

    with get_pool().connection() as conn:
        conn.autocommit = True
        user = auth_by_token(conn, token=req.token)
    if user is None:
        raise ApiError(ErrorCode.UNAUTHORIZED, "unknown token")
    if not user.is_expert:
        raise ApiError(ErrorCode.FORBIDDEN, "expert privilege required")

    raw = session_store.issue(get_redis(), user_id=user.user_id)
    response.set_cookie(
        key=s.session_cookie_name,
        value=raw,
        max_age=s.session_absolute_ttl_days * 86400,
        httponly=True,
        secure=s.session_cookie_secure,
        samesite=s.session_cookie_samesite,
        path="/",
    )
    return MeResponse(user_id=user.user_id)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    _user: CurrentUser = Depends(current_user),
) -> dict:
    s = get_settings()
    raw = request.cookies.get(s.session_cookie_name)
    if raw:
        session_store.revoke(get_redis(), raw_session=raw)
    response.delete_cookie(s.session_cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser = Depends(current_user)) -> MeResponse:
    return MeResponse(user_id=user.user_id)


def reset_login_limiter_for_tests() -> None:
    """Test-only hook: forget any rate-limit state so independent tests
    don't interfere. Never call from app code."""
    global _login_limiter
    _login_limiter = None
