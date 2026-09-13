"""Тесты анти-чита."""
from types import SimpleNamespace

from app.db.models import User
from app.services.anti_cheat import evaluate


def test_banned_user_rejected():
    user = User(telegram_id=1, is_banned=True)
    ok, _ = evaluate(user, None)
    assert not ok


def test_bot_rejected():
    user = User(telegram_id=1)
    ok, _ = evaluate(user, SimpleNamespace(is_bot=True))
    assert not ok


def test_regular_user_allowed():
    user = User(telegram_id=1)
    ok, _ = evaluate(user, SimpleNamespace(is_bot=False))
    assert ok
