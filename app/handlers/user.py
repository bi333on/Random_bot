"""Обработчики: /start, меню, профиль, баланс, рефералка."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.context import is_admin
from app.db.engine import session_scope
from app.db.models import Subscription
from app.i18n import money, t
from app.keyboards import back_menu, main_menu
from app.services.referral import ensure_referral_code, find_by_referral_code
from app.services.subscription import get_active_subscription
from app.services.users import get_or_create_user
from app.config import settings

router = Router(name="user")


async def _menu(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, message.from_user.id, message.from_user.username,
            message.from_user.first_name,
        )
        await ensure_referral_code(session, user)
        await message.answer(
            t("start"), reply_markup=main_menu(is_admin(user.telegram_id))
        )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    args = message.text.split()
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        if len(args) > 1 and not user.referred_by:
            referrer = await find_by_referral_code(session, args[1])
            if referrer is not None and referrer.telegram_id != user.telegram_id:
                user.referred_by = referrer.telegram_id
        await ensure_referral_code(session, user)
        await message.answer(
            t("start"), reply_markup=main_menu(is_admin(user.telegram_id))
        )


@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        await callback.message.edit_text(
            t("start"), reply_markup=main_menu(is_admin(user.telegram_id))
        )
    await callback.answer()


@router.callback_query(F.data == "balance")
async def cb_balance(callback: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        await callback.message.edit_text(
            t("balance", balance=money(user.balance)), reply_markup=back_menu()
        )
    await callback.answer()


@router.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        code = await ensure_referral_code(session, user)
        link = f"https://t.me/{settings.bot_username}?start={code}"
        await callback.message.edit_text(
            t(
                "referral",
                code=code,
                link=link,
                percent=settings.referral_percent,
            ),
            reply_markup=back_menu(),
        )
    await callback.answer()


@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        t("support", link=settings.support_link), reply_markup=back_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        sub = await get_active_subscription(session, user.id)
        plan_name = t("plan_none")
        if sub is not None and sub.plan_id is not None:
            from app.db.models import Plan

            plan = await session.get(Plan, sub.plan_id)
            if plan is not None:
                plan_name = plan.name
        role = (
            t("role_admin")
            if is_admin(user.telegram_id)
            else (t("role_org") if sub is not None else t("role_user"))
        )
        await callback.message.edit_text(
            t(
                "profile",
                tg_id=user.telegram_id,
                balance=money(user.balance),
                plan=plan_name,
                role=role,
            ),
            reply_markup=back_menu(),
        )
    await callback.answer()
