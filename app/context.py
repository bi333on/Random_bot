"""Ленивые синглтоны внешних зависимостей (платёжные провайдеры)."""
from __future__ import annotations

from app.config import settings

_payments = None


def get_payments():
    global _payments
    if _payments is None:
        from app.payments.manager import PaymentManager

        _payments = PaymentManager.build()
    return _payments


def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admin_ids
