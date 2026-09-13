"""Обработчики: магазин (тарифы, опции, пополнение) и оплата."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from app.config import settings
from app.context import get_payments
from app.db.engine import session_scope
from app.db.models import Payment, Plan, User
from app.i18n import money, t
from app.keyboards import back_menu, pay_methods_keyboard, pay_url_keyboard, shop_menu
from app.services.payment_flow import finalize_payment
from app.services.promo import compute_discount, validate_promo
from app.services.users import get_or_create_user
from app.utils import html_escape

router = Router(name="purchase")

ADDON_CATALOG = [
    {
        "key": "weights",
        "title": "⚖️ Веса/множители",
        "desc": "Взвешенный выбор победителей (1 конкурс)",
        "price": settings.addon_weights_price,
    },
    {
        "key": "anti_cheat",
        "title": "🛡 Анти-чит",
        "desc": "Отсев ботов и проверка username (1 конкурс)",
        "price": settings.addon_anticheat_price,
    },
    {
        "key": "hide_mention",
        "title": "🙈 Скрыть упоминание бота",
        "desc": "Убрать ссылку на бота из поста (1 конкурс)",
        "price": settings.addon_hide_mention_price,
    },
    {
        "key": "extra_winners",
        "title": "➕ Дополнительный победитель",
        "desc": "+1 победитель сверх лимита тарифа",
        "price": settings.addon_extra_winners_price,
    },
]
ADDON_PRICES = {a["key"]: a["price"] for a in ADDON_CATALOG}


class PromoFlow(StatesGroup):
    waiting = State()


class TopupFlow(StatesGroup):
    amount = State()


@router.callback_query(F.data == "shop")
async def cb_shop(callback: CallbackQuery) -> None:
    await callback.message.edit_text("🛒 Выберите раздел:", reply_markup=shop_menu())
    await callback.answer()


@router.callback_query(F.data == "shop:plans")
async def cb_plans(callback: CallbackQuery) -> None:
    async with session_scope() as session:
        plans = (
            (
                await session.execute(
                    select(Plan)
                    .where(Plan.is_active.is_(True))
                    .order_by(Plan.position, Plan.price)
                )
            )
            .scalars()
            .all()
        )
        if not plans:
            await callback.message.edit_text(
                "Тарифы пока не настроены.", reply_markup=back_menu()
            )
            await callback.answer()
            return
        rows = [
            [
                InlineKeyboardButton(
                    text=(
                        f"{html_escape(plan.name)} — {money(plan.price)} ₽ "
                        f"/ {plan.duration_days} дн"
                    ),
                    callback_data=f"plan:{plan.id}",
                )
            ]
            for plan in plans
        ]
        rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="shop")])
        kb = _mk(rows)
        await callback.message.edit_text("📦 Выберите тариф:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "shop:addons")
async def cb_addons(callback: CallbackQuery) -> None:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{a['title']} — {money(a['price'])} ₽",
                callback_data=f"addon:{a['key']}",
            )
        ]
        for a in ADDON_CATALOG
    ]
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="shop")])
    await callback.message.edit_text(
        "⚡ Разовые опции (применяются к одному конкурсу):",
        reply_markup=_mk(rows),
    )
    await callback.answer()


@router.callback_query(F.data == "shop:topup")
async def cb_topup_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TopupFlow.amount)
    await callback.message.answer(
        "Введите сумму пополнения в рублях (например, 500):"
    )
    await callback.answer()


@router.message(TopupFlow.amount)
async def st_topup_amount(message: Message, state: FSMContext) -> None:
    try:
        rubles = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число рублей:")
        return
    if rubles < 1:
        await message.answer("Сумма должна быть не меньше 1 рубля:")
        return
    kopecks = rubles * 100
    await state.clear()
    await state.set_data({"topup_amount": kopecks})
    providers = get_payments().names()
    if not providers:
        await message.answer(
            "Платёжные методы не настроены. Обратитесь к администратору.",
            reply_markup=back_menu(),
        )
        return
    kb = pay_methods_keyboard(providers, prefix=f"paytopup:{kopecks}")
    await message.answer(
        f"Пополнение на {rubles} ₽. Выберите способ оплаты:",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("plan:"))
async def cb_plan(callback: CallbackQuery, state: FSMContext) -> None:
    plan_id = int(callback.data.split(":", 1)[1])
    await state.clear()
    await state.set_data({"plan_id": plan_id, "promo_code": None})
    async with session_scope() as session:
        view = await _plan_view(session, plan_id, promo_code=None, with_discount=False)
    if view is None:
        await callback.message.answer("Тариф не найден.", reply_markup=back_menu())
        await callback.answer()
        return
    text, kb = view
    await callback.message.edit_text(
        text + "\n\nВыберите способ оплаты:", reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("addon:"))
async def cb_addon(callback: CallbackQuery) -> None:
    key = callback.data.split(":", 1)[1]
    item = next((a for a in ADDON_CATALOG if a["key"] == key), None)
    if item is None:
        await callback.answer("Неизвестная опция")
        return
    providers = get_payments().names()
    kb = pay_methods_keyboard(
        providers, prefix=f"payaddon:{key}", allow_balance=True, back_cb="shop:addons"
    )
    await callback.message.edit_text(
        f"{item['title']}\n\n{item['desc']}\nЦена: <b>{money(item['price'])} ₽</b>\n\n"
        "Выберите способ оплаты:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("promo:"))
async def cb_promo(callback: CallbackQuery, state: FSMContext) -> None:
    plan_id = int(callback.data.split(":", 1)[1])
    await state.set_state(PromoFlow.waiting)
    await state.set_data({"plan_id": plan_id})
    await callback.message.answer("Введите промокод:")
    await callback.answer()


@router.message(PromoFlow.waiting)
async def st_promo(message: Message, state: FSMContext) -> None:
    code = message.text.strip().upper()
    if code == "-":
        await state.clear()
        await message.answer("Промокод отменён.", reply_markup=back_menu())
        return
    data = await state.get_data()
    plan_id = int(data.get("plan_id", 0))
    async with session_scope() as session:
        promo = await validate_promo(session, code)
        if promo is None:
            await message.answer(
                "Промокод не найден или недействителен. "
                "Введите ещё раз или «-» для отмены:"
            )
            return
        view = await _plan_view(
            session, plan_id, promo_code=code, with_discount=True
        )
    if view is None:
        await message.answer("Тариф не найден.", reply_markup=back_menu())
        await state.clear()
        return
    text, kb = view
    await state.clear()
    await state.set_data({"plan_id": plan_id, "promo_code": code})
    await message.answer(text + "\n\nВыберите способ оплаты:", reply_markup=kb)


async def _plan_view(
    session,
    plan_id: int,
    promo_code: str | None,
    with_discount: bool,
) -> tuple[str, InlineKeyboardMarkup] | None:
    plan = await session.get(Plan, plan_id)
    if plan is None:
        return None
    price = plan.price
    discount = 0
    if promo_code:
        promo = await validate_promo(session, promo_code)
        if promo:
            price, discount = compute_discount(plan.price, promo)
    text = (
        f"📦 <b>{html_escape(plan.name)}</b>\n\n"
        f"{html_escape(plan.description or '')}\n"
        f"Срок: {plan.duration_days} дн\n"
        f"Активных конкурсов: {plan.max_active_contests}\n"
        f"Участников на конкурс: {plan.max_participants or 'без лимита'}\n"
        f"Победителей: {plan.max_winners}\n"
    )
    if with_discount and discount > 0:
        text += (
            f"\nСтарая цена: {money(plan.price)} ₽\n"
            f"Скидка: -{money(discount)} ₽\n"
        )
    text += f"\nИтого: <b>{money(price)} ₽</b>"
    providers = get_payments().names()
    kb = pay_methods_keyboard(
        providers,
        prefix=f"payplan:{plan_id}",
        allow_balance=True,
        back_cb="shop:plans",
    )
    kb.inline_keyboard.insert(
        0,
        [
            InlineKeyboardButton(
                text="🎟 Промокод", callback_data=f"promo:{plan_id}"
            )
        ],
    )
    return text, kb


@router.callback_query(F.data.startswith("payplan:"))
async def cb_payplan(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    plan_id = int(parts[1])
    method = parts[2]
    data = await state.get_data()
    promo_code = data.get("promo_code")
    async with session_scope() as session:
        plan = await session.get(Plan, plan_id)
        if plan is None:
            await callback.answer("Тариф не найден.")
            return
        price = plan.price
        if promo_code:
            promo = await validate_promo(session, promo_code)
            if promo:
                price, _ = compute_discount(plan.price, promo)
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        await _run_payment(
            callback,
            user=user,
            purpose="subscription",
            amount=price,
            meta={"plan_id": plan.id, "promo_code": promo_code},
            method=method,
            description=f"Подписка {plan.name}",
            state=state,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("payaddon:"))
async def cb_payaddon(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    addon_key = parts[1]
    method = parts[2]
    price = ADDON_PRICES.get(addon_key)
    if price is None:
        await callback.answer("Неизвестная опция.")
        return
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        await _run_payment(
            callback,
            user=user,
            purpose="addon",
            amount=price,
            meta={"addon_type": addon_key, "quantity": 1},
            method=method,
            description=f"Опция {addon_key}",
            state=state,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("paytopup:"))
async def cb_paytopup(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    kopecks = int(parts[1])
    method = parts[2]
    if method == "balance":
        await callback.answer("Пополнение с баланса недоступно.", show_alert=True)
        return
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        await _run_payment(
            callback,
            user=user,
            purpose="topup",
            amount=kopecks,
            meta={},
            method=method,
            description="Пополнение баланса",
            state=state,
        )
    await callback.answer()


async def _run_payment(
    callback: CallbackQuery,
    *,
    user,
    purpose: str,
    amount: int,
    meta: dict,
    method: str,
    description: str,
    state: FSMContext,
) -> None:
    if method == "balance":
        if int(user.balance or 0) < amount:
            await callback.message.answer(t("pay_balance_fail"), reply_markup=back_menu())
            return
        async with session_scope() as session:
            fresh_user = await session.get(User, user.id)
            payment = Payment(
                user_id=fresh_user.id,
                provider="balance",
                amount=0,
                currency=settings.currency,
                status="pending",
                purpose=purpose,
                meta={**meta, "balance_used": amount},
            )
            session.add(payment)
            status, _ = await finalize_payment(session, payment)
        if status == "succeeded":
            await callback.message.answer(
                t("pay_balance_ok"), reply_markup=back_menu()
            )
        else:
            await callback.message.answer(
                t("pay_balance_fail"), reply_markup=back_menu()
            )
        await state.clear()
        return

    provider = get_payments().get(method)
    if provider is None:
        await callback.message.answer("Платёжный метод недоступен.", reply_markup=back_menu())
        return

    async with session_scope() as session:
        payment = Payment(
            user_id=user.id,
            provider=method,
            amount=amount,
            currency=settings.currency,
            status="pending",
            purpose=purpose,
            meta=meta,
        )
        session.add(payment)
        await session.flush()
        try:
            invoice = await provider.create_invoice(
                amount=amount,
                currency=settings.currency,
                description=description,
                metadata={"payment_id": payment.id, **meta},
            )
        except Exception as exc:  # noqa: BLE001
            await callback.message.answer(
                t("invoice_error", error=html_escape(str(exc))),
                reply_markup=back_menu(),
            )
            return
        payment.provider_payment_id = invoice.provider_payment_id

    await callback.message.answer(
        t("invoice_created", amount=money(amount)),
        reply_markup=pay_url_keyboard(invoice.pay_url) if invoice.pay_url else None,
    )
    await state.clear()


def _mk(rows: list[list[InlineKeyboardButton]]):
    from aiogram.types import InlineKeyboardMarkup

    return InlineKeyboardMarkup(inline_keyboard=rows)
