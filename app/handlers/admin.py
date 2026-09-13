"""Обработчики админа: статистика, пополнение, рассылка."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from app.context import is_admin
from app.db.engine import session_scope
from app.db.models import Contest, Payment, Subscription, User
from app.i18n import money, t
from app.services.balance import add_balance

router = Router(name="admin")


async def _stats_text(session) -> str:
    users = (await session.execute(select(func.count(User.id)))).scalar_one()
    contests = (
        await session.execute(
            select(func.count(Contest.id)).where(Contest.status == "active")
        )
    ).scalar_one()
    subs = (
        await session.execute(
            select(func.count(Subscription.id)).where(Subscription.status == "active")
        )
    ).scalar_one()
    revenue = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == "succeeded"
            )
        )
    ).scalar_one()
    return t(
        "admin_stats",
        users=users,
        contests=contests,
        subs=subs,
        revenue=money(int(revenue)),
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    async with session_scope() as session:
        await message.answer(await _stats_text(session))


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    async with session_scope() as session:
        await callback.message.edit_text(await _stats_text(session))
    await callback.answer()


@router.message(Command("topup"))
async def cmd_topup(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /topup <telegram_id> <рубли>")
        return
    try:
        tg_id = int(parts[1])
        rubles = int(parts[2])
    except ValueError:
        await message.answer("Использование: /topup <telegram_id> <рубли>")
        return
    async with session_scope() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == tg_id)
            )
        ).scalar_one_or_none()
        if user is None:
            await message.answer("Пользователь не найден.")
            return
        await add_balance(session, user, rubles * 100, "manual", "Админ пополнение")
        await message.answer(
            t("topup_ok", amount=rubles, balance=money(user.balance))
        )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /broadcast <текст>")
        return
    async with session_scope() as session:
        ids = (await session.execute(select(User.telegram_id))).scalars().all()
    sent = 0
    for tg_id in ids:
        try:
            await message.bot.send_message(tg_id, parts[1])
            sent += 1
        except Exception:  # noqa: BLE001
            continue
    await message.answer(t("broadcast_ok", sent=sent, total=len(ids)))
