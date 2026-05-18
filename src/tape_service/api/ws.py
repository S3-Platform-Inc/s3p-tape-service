from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..settings import get_settings
from ..store import sessions
from ..store.async_client import get_async_redis
from ..store.events import channel_for

log = logging.getLogger(__name__)

router = APIRouter()

# Policy-violation close code per RFC 6455 section 7.4.1.
_CLOSE_UNAUTHORIZED = 1008


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    """Subscribe an authenticated client to its per-user event stream.

    Auth uses the same s3p_session cookie that /auth/login issued: the
    upgrade is accepted only after sessions.validate succeeds. Unauthed
    upgrades close immediately with code 1008.

    Once accepted, every frame from Redis channel tape:events:{user_id}
    is forwarded to the client verbatim (already JSON). The handler
    never reads from the client.
    """
    s = get_settings()
    raw = ws.cookies.get(s.session_cookie_name)
    ar = get_async_redis()
    sess = await sessions.validate_async(ar, raw_session=raw) if raw else None
    if sess is None:
        await ws.close(code=_CLOSE_UNAUTHORIZED)
        return

    await ws.accept()
    channel = channel_for(sess.user_id)
    pubsub = ar.pubsub()
    try:
        await pubsub.subscribe(channel)
        log.info("ws.subscribed", extra={"user_id": sess.user_id, "channel": channel})
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            await ws.send_text(data)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await pubsub.unsubscribe(channel)
        except Exception:  # noqa: S110 - best-effort cleanup
            pass
        try:
            await pubsub.aclose()
        except Exception:  # noqa: S110 - best-effort cleanup
            pass
        log.info("ws.closed", extra={"user_id": sess.user_id})
