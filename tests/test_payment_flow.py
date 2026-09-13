"""Тесты финализации платежей."""
from sqlalchemy import select

from app.db.models import Payment, Plan, Subscription, User
from app.services.payment_flow import finalize_payment


async def test_subscription_payment_with_referral(session):
    referrer = User(telegram_id=100, referral_code="ABC12345")
    user = User(telegram_id=200, referred_by=100, balance=5000)
    session.add_all([referrer, user])
    await session.flush()

    plan = Plan(name="Pro", price=1000, duration_days=30)
    session.add(plan)
    await session.flush()

    payment = Payment(
        user_id=user.id,
        provider="balance",
        amount=0,
        purpose="subscription",
        meta={"plan_id": plan.id, "balance_used": 1000},
    )
    session.add(payment)
    await session.flush()

    status, result_user = await finalize_payment(session, payment)
    assert status == "succeeded"
    assert result_user.id == user.id

    subs = (
        await session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
    ).scalars().all()
    assert len(subs) == 1
    assert subs[0].status == "active"
    assert subs[0].plan_id == plan.id

    await session.refresh(user)
    await session.refresh(referrer)
    assert user.balance == 4000
    # 10% от 1000 = 100
    assert referrer.balance == 100


async def test_addon_payment(session):
    user = User(telegram_id=1, balance=1000)
    session.add(user)
    await session.flush()

    payment = Payment(
        user_id=user.id,
        provider="balance",
        amount=0,
        purpose="addon",
        meta={"addon_type": "weights", "quantity": 1, "balance_used": 500},
    )
    session.add(payment)
    await session.flush()

    status, _ = await finalize_payment(session, payment)
    assert status == "succeeded"

    await session.refresh(user)
    assert user.addon_credits.get("weights") == 1
    assert user.balance == 500


async def test_topup_payment(session):
    user = User(telegram_id=1, balance=0)
    session.add(user)
    await session.flush()

    payment = Payment(
        user_id=user.id,
        provider="yookassa",
        amount=1000,
        purpose="topup",
        meta={},
    )
    session.add(payment)
    await session.flush()

    status, _ = await finalize_payment(session, payment)
    assert status == "succeeded"

    await session.refresh(user)
    assert user.balance == 1000
