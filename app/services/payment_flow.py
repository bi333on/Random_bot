"""Завершение платежа: подписка, опции, пополнение, рефералка."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Addon, Payment, Plan, User
from app.services.balance import add_balance, spend_balance
from app.services.promo import mark_promo_used, validate_promo
from app.services.referral import grant_referral_bonus
from app.services.subscription import (
    activate_subscription,
    add_credit,
    utcnow,
)


async def finalize_payment(
    session: AsyncSession, payment: Payment
) -> tuple[str, User | None]:
    """Обработать успешный платёж (только БД, без отправки сообщений).

    Возвращает (status, user).
    """
    if payment.status == "succeeded":
        return "ignored", None

    user = await session.get(User, payment.user_id)
    if user is None:
        return "ignored", None

    snapshot = payment.meta or {}
    purpose = payment.purpose
    amount = int(payment.amount or 0)
    balance_used = int(snapshot.get("balance_used", 0) or 0)

    if balance_used > 0:
        ok = await spend_balance(session, user, balance_used, "Оплата с баланса")
        if not ok:
            payment.status = "failed"
            return "failed", user

    if purpose == "topup":
        await add_balance(session, user, amount, "topup", "Пополнение баланса")

    elif purpose == "addon":
        addon_type = snapshot.get("addon_type")
        quantity = int(snapshot.get("quantity", 1) or 1)
        add_credit(user, addon_type, quantity)
        session.add(
            Addon(
                user_id=user.id,
                addon_type=addon_type,
                quantity=quantity,
                amount=balance_used + amount,
                payment_id=payment.id,
            )
        )

    elif purpose == "subscription":
        plan_id = snapshot.get("plan_id")
        plan = await session.get(Plan, plan_id) if plan_id else None
        promo_code = snapshot.get("promo_code")
        if promo_code:
            promo = await validate_promo(session, promo_code)
            if promo:
                await mark_promo_used(session, promo)
        duration_days = int(
            snapshot.get("duration_days")
            or (plan.duration_days if plan else 30)
        )
        total_paid = balance_used + amount
        sub = await activate_subscription(
            session,
            user,
            plan,
            duration_days,
            payment_id=payment.id,
            paid_amount=total_paid,
        )
        await grant_referral_bonus(session, user, sub.id, total_paid)

    elif purpose == "ad":
        # Оплата рекламы/спонсорского конкурса — просто фиксируем факт оплаты.
        pass

    else:
        return "ignored", user

    payment.status = "succeeded"
    payment.paid_at = utcnow()
    await session.flush()
    return "succeeded", user
