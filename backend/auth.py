"""Feishu webview authentication. Dev mode bypasses when Feishu not configured."""
from __future__ import annotations
import hashlib
import hmac
import os
import time
from fastapi import Request, HTTPException
from fastapi.responses import Response

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "dev-secret")
DEV_MODE = not FEISHU_APP_ID or os.getenv("DEV_MODE", "").lower() == "true"

COOKIE_NAME = "breakfast_token"
COOKIE_MAX_AGE = 86400 * 7  # 7 days


def _sign(user_id: str, ts: str) -> str:
    raw = f"{user_id}:{ts}"
    return hmac.new(FEISHU_APP_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]


def set_auth_cookie(response: Response, user_id: str = "feishu-user"):
    """Set signed session cookie. Call from page-load handlers."""
    ts = str(int(time.time()))
    sig = _sign(user_id, ts)
    token = f"v1|{user_id}|{ts}|{sig}"
    response.set_cookie(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax")


def _verify_token(token: str) -> str | None:
    """Verify cookie token, return user_id or None."""
    try:
        parts = token.split("|")
        if len(parts) != 4 or parts[0] != "v1":
            return None
        _, user_id, ts, sig = parts
        if int(ts) + COOKIE_MAX_AGE < time.time():
            return None
        expected = _sign(user_id, ts)
        if not hmac.compare_digest(sig, expected):
            return None
        return user_id
    except Exception:
        return None


async def get_current_user(request: Request) -> str:
    """FastAPI dependency. Checks Feishu headers first, then cookie."""
    if DEV_MODE:
        return "dev-user"

    user_id = request.headers.get("X-Feishu-User-Id")
    if user_id:
        return user_id

    user_id = request.query_params.get("feishu_user_id") or request.query_params.get("open_id")
    if user_id:
        return user_id

    token = request.cookies.get(COOKIE_NAME)
    if token:
        user_id = _verify_token(token)
        if user_id:
            return user_id

    raise HTTPException(status_code=401, detail="请在飞书中打开此页面")
