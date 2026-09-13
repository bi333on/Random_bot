"""Вспомогательные утилиты."""
from __future__ import annotations

import secrets
import string

_ALPHABET = string.ascii_uppercase + string.digits


def generate_referral_code(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def html_escape(text: str | None) -> str:
    import html

    return html.escape(str(text or ""))
