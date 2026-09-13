"""Проверка подписки пользователя на каналы."""
from __future__ import annotations

from aiogram import Bot


async def check_subscriptions(
    bot: Bot, user_id: int, channels: list[str]
) -> tuple[bool, list[str]]:
    """Вернуть (все_подписаны, список_неподписанных)."""
    missing: list[str] = []
    for channel in channels:
        chat_id = str(channel or "").strip()
        if not chat_id:
            continue
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append(chat_id)
        except Exception:
            # Не удалось проверить (бот не админ и т.п.) — считаем неподписанным.
            missing.append(chat_id)
    return not missing, missing
