"""Анти-чит: базовые проверки участника."""
from __future__ import annotations

from app.db.models import User


def evaluate(user: User, tg_user) -> tuple[bool, str]:
    """Вернуть (допущен, причина_отказа)."""
    if user.is_banned:
        return False, "Пользователь заблокирован"
    if tg_user is not None and getattr(tg_user, "is_bot", False):
        return False, "Боты не могут участвовать в конкурсе"
    return True, ""
