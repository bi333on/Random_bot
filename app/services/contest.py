"""Жизненный цикл конкурса: пост, публикация, подведение итогов."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Contest, Participant, User, Winner
from app.i18n import t
from app.services.randomizer import pick_winners
from app.utils import html_escape

logger = logging.getLogger(__name__)

CONDITION_LABELS = {
    "subscribe": "подписка на канал(ы)",
    "comment": "комментарий",
    "repost": "репост",
    "none": "без условий",
}


def build_post_text(contest: Contest, bot_username: str = "") -> str:
    lines = [f"🎲 <b>{html_escape(contest.title)}</b>"]
    if contest.description:
        lines.append(html_escape(contest.description))
    lines.append("")
    lines.append(f"🏆 Победителей: <b>{contest.winners_count}</b>")
    lines.append(
        f"📅 Условие участия: {CONDITION_LABELS.get(contest.condition_type, '—')}"
    )
    if contest.channel_usernames:
        joined = ", ".join(html_escape(c) for c in contest.channel_usernames)
        lines.append(f"📢 Каналы: {joined}")
    if contest.prize:
        lines.append(f"🎁 Приз: {html_escape(contest.prize)}")
    ends = contest.ends_at.strftime("%d.%m.%Y %H:%M")
    lines.append(f"⏳ Итоги: {ends} (UTC)")
    if contest.is_sponsored and contest.sponsor_name:
        lines.append(f"🤝 Спонсор: {html_escape(contest.sponsor_name)}")
    if not contest.hide_bot_mention and bot_username:
        lines.append("")
        lines.append(f"Проведено через @{bot_username}")
    return "\n".join(lines)


def join_keyboard(contest_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("contest_join"), callback_data=f"join:{contest_id}"
                )
            ]
        ]
    )


async def publish_contest(
    bot: Bot, session: AsyncSession, contest: Contest, bot_username: str = ""
) -> None:
    """Опубликовать пост конкурса в канал или ЛС организатора."""
    text = build_post_text(contest, bot_username)
    keyboard = join_keyboard(contest.id)

    target = (contest.announce_chat_id or "").strip()
    if target and target != "-":
        msg = await bot.send_message(target, text, reply_markup=keyboard)
        contest.post_message_id = msg.message_id
    else:
        organizer = await session.get(User, contest.organizer_id)
        if organizer is not None:
            msg = await bot.send_message(
                organizer.telegram_id, text, reply_markup=keyboard
            )
            contest.post_message_id = msg.message_id


async def finish_contest(
    bot: Bot, session: AsyncSession, contest: Contest
) -> None:
    """Выбрать победителей, сохранить и объявить результаты."""
    if contest.status != "active":
        return

    contest.status = "finished"

    participants = (
        (
            await session.execute(
                select(Participant).where(
                    Participant.contest_id == contest.id,
                    Participant.is_valid.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    entries: list[tuple[int, int]] = []
    for p in participants:
        weight = p.weight if contest.weights_enabled else 1
        entries.append((p.user_id, weight))

    winner_ids = pick_winners(entries, contest.winners_count)

    result_lines: list[str] = []
    for place, user_id in enumerate(winner_ids, start=1):
        session.add(Winner(contest_id=contest.id, user_id=user_id, place=place))
        user = await session.get(User, user_id)
        if user is not None:
            name = html_escape(
                user.first_name or user.username or str(user.telegram_id)
            )
            result_lines.append(
                t("winner_line", place=place, tg_id=user.telegram_id, name=name)
            )

    if result_lines:
        result_text = "\n".join(result_lines)
    else:
        result_text = t("no_participants")

    message_text = t(
        "results_title",
        title=html_escape(contest.title),
        results=result_text,
    )
    contest.result_message = message_text

    # Объявление в канале конкурса.
    target = (contest.announce_chat_id or "").strip()
    if target and target != "-":
        try:
            await bot.send_message(target, message_text)
        except Exception:  # noqa: BLE001
            logger.exception("failed to announce results in channel")

    # Результат организатору.
    try:
        organizer = await session.get(User, contest.organizer_id)
        if organizer is not None:
            await bot.send_message(organizer.telegram_id, message_text)
    except Exception:  # noqa: BLE001
        logger.exception("failed to send results to organizer")

    # Поздравление победителям.
    for user_id in winner_ids:
        try:
            user = await session.get(User, user_id)
            if user is not None:
                await bot.send_message(
                    user.telegram_id,
                    f"🎉 Поздравляем! Вы победили в конкурсе "
                    f"«{html_escape(contest.title)}»!",
                )
        except Exception:  # noqa: BLE001
            logger.exception("failed to notify winner")
