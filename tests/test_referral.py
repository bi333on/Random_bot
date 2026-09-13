"""Тесты реферальной системы."""
from app.db.models import User
from app.services.referral import ensure_referral_code, find_by_referral_code


async def test_ensure_referral_code(session):
    user = User(telegram_id=1)
    session.add(user)
    await session.flush()
    code = await ensure_referral_code(session, user)
    assert code
    assert len(code) == 8
    assert await ensure_referral_code(session, user) == code


async def test_find_by_referral_code(session):
    user = User(telegram_id=1, referral_code="ABCD1234")
    session.add(user)
    await session.flush()
    found = await find_by_referral_code(session, "abcd1234")
    assert found is not None and found.telegram_id == 1
    assert await find_by_referral_code(session, "unknown") is None
