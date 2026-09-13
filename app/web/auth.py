"""Аутентификация веб-кабинета: Telegram Login Widget + подписанные cookie."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.config import settings


def _sign(data: bytes) -> str:
    return hmac.new(
        settings.web_app_secret.encode(), data, hashlib.sha256
    ).hexdigest()


def create_session_token(telegram_id: int, is_admin: bool) -> str:
    payload = {
        "tg": telegram_id,
        "admin": is_admin,
        "exp": int(time.time()) + settings.web_session_ttl,
    }
    raw = (
        base64.urlsafe_b64encode(json.dumps(payload).encode())
        .decode()
        .rstrip("=")
    )
    return f"{raw}.{_sign(raw.encode())}"


def verify_session_token(token: str) -> dict | None:
    try:
        raw, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(raw.encode()), sig):
            return None
        padded = raw + "=" * (-len(raw) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        if int(data.get("exp", 0)) < time.time():
            return None
        return data
    except Exception:
        return None


def verify_telegram_login(data: dict) -> bool:
    received = data.get("hash", "")
    if not received:
        return False
    try:
        auth_date = int(data.get("auth_date", 0))
        if auth_date and abs(time.time() - auth_date) > 86400:
            return False
    except (TypeError, ValueError):
        return False
    if not settings.bot_token:
        return False
    secret = hashlib.sha256(settings.bot_token.encode()).digest()
    check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(data.items())
        if key != "hash"
    )
    expected = hmac.new(
        secret, check_string.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received)
