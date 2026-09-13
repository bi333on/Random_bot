"""Реферальная система."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Subscription, User
from app.services.balance import add_balance
from app.utils import generate_referral_code


async def ensure_referral_code(session: AsyncSession, user: User) -> str:
    if user.referral_code:
        return user.referral_code
    for _ in range(5):
        code = generate_referral_code()
        exists = (
            await session.execute(
                select(User.id).where(User.referral_code == code)
            )
        ).first()
        if not exists:
            user.referral_code = code
            return code
    raise RuntimeError("cannot generate unique referral code")


async def find_by_referral_code(
    session: AsyncSession, code: str
) -> User | None:
    normalized = (code or "").strip().upper()
    if not normalized:
        return None
    return (
        await session.execute(
            select(User).where(User.referral_code == normalized)
        )
    ).scalar_one_or_none()


async def grant_referral_bonus(
    session: AsyncSession,
    user: User,
    subscription_id: int,
    total_paid: int,
) -> None:
    """Начислить рефереру процент с первой платной покупки."""
    if not user.referred_by:
        return
    prior = (
        await session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.user_id == user.id,
                Subscription.id != subscription_id,
            )
        )
    ).scalar_one()
    if prior > 0:
        return
    referrer = (
        await session.execute(
            select(User).where(User.telegram_id == user.referred_by)
        )
    ).scalar_one_or_none()
    if referrer is None:
        return
    bonus = round(int(total_paid) * settings.referral_percent / 100)
    await add_balance(
        session, referrer, bonus, "referral", f"Реферал tg{user.telegram_id}"
    )
