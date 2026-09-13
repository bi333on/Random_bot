"""Обработчики: создание конкурса (визард) и участие."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.context import is_admin
from app.db.engine import session_scope
from app.db.models import Contest, Participant
from app.i18n import t
from app.keyboards import (
    back_menu,
    condition_keyboard,
    confirm_keyboard,
    options_keyboard,
)
from app.services.anti_cheat import evaluate
from app.services.channel_check import check_subscriptions
from app.services.contest import (
    CONDITION_LABELS,
    publish_contest,
)
from app.services.subscription import (
    can_create_contest,
    compute_required_addons,
    consume_credits,
    get_plan_for_user,
    has_credits,
)
from app.services.users import get_or_create_user
from app.utils import html_escape

router = Router(name="contest")


class CreateContest(StatesGroup):
    title = State()
    description = State()
    channels = State()
    condition = State()
    winners = State()
    ends_at = State()
    prize = State()
    announce = State()
    options = State()
    confirm = State()


def parse_ends_at(text: str) -> datetime | None:
    text = text.strip()
    now = datetime.now(timezone.utc)
    lowered = text.lower()
    if lowered.endswith(("m", "h", "d")):
        try:
            n = int(text[:-1])
        except ValueError:
            return None
        if lowered.endswith("m"):
            return now + timedelta(minutes=n)
        if lowered.endswith("h"):
            return now + timedelta(hours=n)
        if lowered.endswith("d"):
            return now + timedelta(days=n)
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@router.callback_query(F.data == "create_contest")
async def cb_create_contest(callback: CallbackQuery, state: FSMContext) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        ok, reason = await can_create_contest(session, user)
    if not ok:
        await callback.message.answer(t(reason), reply_markup=back_menu())
        await callback.answer()
        return
    await state.set_state(CreateContest.title)
    await callback.message.answer("Введите название конкурса:")
    await callback.answer()


@router.message(CreateContest.title)
async def st_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(CreateContest.description)
    await message.answer("Введите описание конкурса (или «-», чтобы пропустить):")


@router.message(CreateContest.description)
async def st_description(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    await state.update_data(description=None if text == "-" else text)
    await state.set_state(CreateContest.channels)
    await message.answer(
        "Введите каналы для обязательной подписки через запятую\n"
        "(например: @channel1, @channel2). «-» — без каналов:"
    )


@router.message(CreateContest.channels)
async def st_channels(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    channels: list[str] = []
    if raw != "-":
        channels = [c.strip() for c in raw.replace(" ", "").split(",") if c.strip()]
    await state.update_data(channels=channels)
    await state.set_state(CreateContest.condition)
    await message.answer("Условие участия:", reply_markup=condition_keyboard())


@router.callback_query(F.data.startswith("cond:"), CreateContest.condition)
async def cb_condition(callback: CallbackQuery, state: FSMContext) -> None:
    condition = callback.data.split(":", 1)[1]
    await state.update_data(condition=condition)
    await state.set_state(CreateContest.winners)
    await callback.message.edit_text("Сколько победителей выбрать? (введите число)")
    await callback.answer()


@router.message(CreateContest.winners)
async def st_winners(message: Message, state: FSMContext) -> None:
    try:
        winners = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число победителей:")
        return
    if winners < 1:
        await message.answer("Число победителей должно быть не меньше 1:")
        return
    await state.update_data(winners=winners)
    await state.set_state(CreateContest.ends_at)
    await message.answer(
        "Когда подвести итоги?\n"
        "Примеры: 30m, 2h, 1d или 2026-09-15 18:00 (время UTC):"
    )


@router.message(CreateContest.ends_at)
async def st_ends_at(message: Message, state: FSMContext) -> None:
    dt = parse_ends_at(message.text)
    if dt is None:
        await message.answer(
            "Не понял формат. Примеры: 30m, 2h, 1d или 2026-09-15 18:00:"
        )
        return
    if dt <= datetime.now(timezone.utc):
        await message.answer("Дата завершения должна быть в будущем:")
        return
    await state.update_data(ends_at=dt)
    await state.set_state(CreateContest.prize)
    await message.answer("Приз (или «-», чтобы пропустить):")


@router.message(CreateContest.prize)
async def st_prize(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    await state.update_data(prize=None if text == "-" else text)
    await state.set_state(CreateContest.announce)
    await message.answer(
        "Куда опубликовать пост конкурса?\n"
        "Введите @username канала/чата или chat_id\n"
        "(«-» — получить пост себе в личные сообщения):"
    )


@router.message(CreateContest.announce)
async def st_announce(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    await state.update_data(announce=None if text == "-" else text)
    await state.set_state(CreateContest.options)
    data = await state.get_data()
    await message.answer("Опции конкурса:", reply_markup=options_keyboard(data))


@router.callback_query(F.data.startswith("opt:"), CreateContest.options)
async def cb_options(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()

    if key == "done":
        await state.set_state(CreateContest.confirm)
        summary = _summary(data)
        await callback.message.edit_text(
            summary + "\n\nПодтвердите создание:", reply_markup=confirm_keyboard()
        )
        await callback.answer()
        return

    data[key] = not data.get(key, False)
    await state.update_data(**{key: data[key]})
    await callback.message.edit_text(
        "Опции конкурса:", reply_markup=options_keyboard(data)
    )
    await callback.answer()


def _summary(data: dict) -> str:
    lines = [
        "📋 <b>Проверка конкурса</b>",
        f"Название: {html_escape(str(data.get('title', '')))}",
        f"Условие: {CONDITION_LABELS.get(data.get('condition'), '—')}",
        f"Каналы: {', '.join(html_escape(c) for c in (data.get('channels') or [])) or '—'}",
        f"Победителей: {data.get('winners')}",
        f"Итоги: {data.get('ends_at').strftime('%d.%m.%Y %H:%M')} UTC",
        f"Приз: {html_escape(str(data.get('prize') or '—'))}",
        f"Публикация: {html_escape(str(data.get('announce') or 'в ЛС'))}",
        f"Веса: {'да' if data.get('weights') else 'нет'}",
        f"Анти-чит: {'да' if data.get('anti_cheat') else 'нет'}",
        f"Скрыть упоминание бота: {'да' if data.get('hide_mention') else 'нет'}",
    ]
    return "\n".join(lines)


@router.callback_query(F.data == "confirm_yes", CreateContest.confirm)
async def cb_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        plan = await get_plan_for_user(session, user)
        needed = await compute_required_addons(
            user,
            plan,
            winners_count=int(data.get("winners", 1)),
            weights=bool(data.get("weights")),
            anti_cheat=bool(data.get("anti_cheat")),
            hide_mention=bool(data.get("hide_mention")),
        )
        if needed and not has_credits(user, needed):
            missing = ", ".join(needed.keys())
            await callback.message.answer(
                "Для этих опций нужны разовые пакеты. "
                "Приобретите их в «🛒 Тарифы и опции» → «⚡ Опции».\n"
                f"Не хватает: {missing}",
                reply_markup=back_menu(),
            )
            await state.clear()
            await callback.answer()
            return

        consume_credits(user, needed)

        participants_limit = None
        if plan is not None and not is_admin(user.telegram_id):
            participants_limit = plan.max_participants

        contest = Contest(
            organizer_id=user.id,
            title=data["title"],
            description=data.get("description"),
            status="active",
            channel_usernames=data.get("channels") or [],
            condition_type=data.get("condition") or "subscribe",
            winners_count=int(data.get("winners", 1)),
            participants_limit=participants_limit,
            ends_at=data["ends_at"],
            prize=data.get("prize"),
            announce_chat_id=data.get("announce"),
            weights_enabled=bool(data.get("weights")),
            anti_cheat_enabled=bool(data.get("anti_cheat")),
            hide_bot_mention=bool(data.get("hide_mention")),
        )
        session.add(contest)
        await session.flush()

        await publish_contest(
            callback.bot, session, contest, settings.bot_username
        )
        await callback.message.answer(
            t(
                "contest_created",
                title=html_escape(contest.title),
                winners=contest.winners_count,
                ends_at=contest.ends_at.strftime("%d.%m.%Y %H:%M"),
            ),
            reply_markup=back_menu(),
        )

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel_contest")
async def cb_cancel_contest(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Создание конкурса отменено.")
    await callback.answer()


@router.callback_query(F.data == "my_contests")
async def cb_my_contests(callback: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        contests = (
            (
                await session.execute(
                    select(Contest)
                    .where(Contest.organizer_id == user.id)
                    .order_by(Contest.created_at.desc())
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )
        if not contests:
            await callback.message.edit_text(
                "У вас пока нет конкурсов.", reply_markup=back_menu()
            )
        else:
            lines = ["📋 <b>Ваши конкурсы:</b>"]
            for c in contests:
                cnt = (
                    await session.execute(
                        select(func.count(Participant.id)).where(
                            Participant.contest_id == c.id
                        )
                    )
                ).scalar_one()
                status = {
                    "draft": "черновик",
                    "active": "идёт",
                    "finished": "завершён",
                    "canceled": "отменён",
                }.get(c.status, c.status)
                lines.append(
                    f"#{c.id} {html_escape(c.title)} — {status} ({cnt} участ.)"
                )
            await callback.message.edit_text(
                "\n".join(lines), reply_markup=back_menu()
            )
    await callback.answer()


@router.callback_query(F.data.startswith("join:"))
async def cb_join(callback: CallbackQuery) -> None:
    contest_id = int(callback.data.split(":", 1)[1])
    async with session_scope() as session:
        contest = await session.get(Contest, contest_id)
        if contest is None or contest.status != "active":
            await callback.answer(t("contest_finished"), show_alert=True)
            return

        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )

        ok, reason = evaluate(user, callback.from_user)
        if not ok:
            await callback.answer(reason, show_alert=True)
            return

        if contest.anti_cheat_enabled and not user.username:
            await callback.answer(
                "Для участия в этом конкурсе нужен username в Telegram.",
                show_alert=True,
            )
            return

        if contest.condition_type == "subscribe" and contest.channel_usernames:
            all_ok, missing = await check_subscriptions(
                callback.bot, callback.from_user.id, contest.channel_usernames
            )
            if not all_ok:
                await callback.answer(
                    t("not_subscribed", channels=", ".join(missing)),
                    show_alert=True,
                )
                return

        if contest.participants_limit:
            cnt = (
                await session.execute(
                    select(func.count(Participant.id)).where(
                        Participant.contest_id == contest.id
                    )
                )
            ).scalar_one()
            if cnt >= contest.participants_limit:
                await callback.answer(
                    "Достигнут лимит участников.", show_alert=True
                )
                return

        try:
            session.add(
                Participant(contest_id=contest.id, user_id=user.id, weight=1)
            )
            await session.flush()
        except IntegrityError:
            await callback.answer(t("already_joined"), show_alert=True)
            return

        await callback.answer(
            t("joined", title=html_escape(contest.title)), show_alert=True
        )
