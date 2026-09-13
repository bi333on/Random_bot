"""Подписки, тарифы и лимиты создания конкурсов."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import is_admin
from app.db.models import Contest, Plan, Subscription, User

PLAN_FEATURE_KEYS = (
    "weights",
    "anti_cheat",
    "hide_bot_mention",
    "comment_condition",
    "repost_condition",
    "export_csv",
)

ADDON_KEYS = ("weights", "anti_cheat", "hide_mention", "extra_winners")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def plan_features(plan: Plan | None) -> dict:
    f = dict(plan.features or {}) if plan else {}
    for key in PLAN_FEATURE_KEYS:
        f.setdefault(key, False)
    return f


def get_credits(user: User) -> dict:
    return dict(user.addon_credits or {})


def add_credit(user: User, key: str, quantity: int = 1) -> None:
    creds = get_credits(user)
    creds[key] = int(creds.get(key, 0)) + int(quantity)
    user.addon_credits = creds


def has_credits(user: User, needed: dict[str, int]) -> bool:
    creds = get_credits(user)
    return all(int(creds.get(key, 0)) >= int(qty) for key, qty in needed.items())


def consume_credits(user: User, needed: dict[str, int]) -> None:
    creds = get_credits(user)
    for key, qty in needed.items():
        creds[key] = max(0, int(creds.get(key, 0)) - int(qty))
    user.addon_credits = creds


async def get_active_subscription(
    session: AsyncSession, user_id: int
) -> Subscription | None:
    now = utcnow()
    row = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


async def get_plan_for_user(session: AsyncSession, user: User) -> Plan | None:
    sub = await get_active_subscription(session, user.id)
    if sub is not None and sub.plan_id is not None:
        return await session.get(Plan, sub.plan_id)
    return None


async def activate_subscription(
    session: AsyncSession,
    user: User,
    plan: Plan | None,
    duration_days: int,
    *,
    payment_id: int | None = None,
    paid_amount: int = 0,
) -> Subscription:
    now = utcnow()
    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id if plan else None,
        status="active",
        started_at=now,
        expires_at=now + timedelta(days=duration_days),
        payment_id=payment_id,
        paid_amount=paid_amount,
    )
    session.add(sub)
    await session.flush()
    return sub


async def count_active_contests(session: AsyncSession, user_id: int) -> int:
    return (
        await session.execute(
            select(func.count(Contest.id)).where(
                Contest.organizer_id == user_id,
                Contest.status.in_(["draft", "active"]),
            )
        )
    ).scalar_one()


async def can_create_contest(
    session: AsyncSession, user: User
) -> tuple[bool, str]:
    if is_admin(user.telegram_id):
        return True, ""
    plan = await get_plan_for_user(session, user)
    if plan is None:
        return False, "no_subscription"
    active = await count_active_contests(session, user.id)
    if plan.max_active_contests is not None and active >= plan.max_active_contests:
        return False, "limit_reached"
    return True, ""


async def compute_required_addons(
    user: User,
    plan: Plan | None,
    *,
    winners_count: int,
    weights: bool,
    anti_cheat: bool,
    hide_mention: bool,
) -> dict[str, int]:
    """Какие разовые опции нужно докупить под запрошенные параметры."""
    if is_admin(user.telegram_id):
        return {}
    feats = plan_features(plan)
    needed: dict[str, int] = {}
    if weights and not feats["weights"]:
        needed["weights"] = 1
    if anti_cheat and not feats["anti_cheat"]:
        needed["anti_cheat"] = 1
    if hide_mention and not feats["hide_bot_mention"]:
        needed["hide_mention"] = 1
    max_winners = plan.max_winners if plan else 0
    if winners_count > max_winners:
        needed["extra_winners"] = winners_count - max_winners
    return needed
