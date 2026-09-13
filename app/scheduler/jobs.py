"""Планировщик: авто-подведение итогов конкурсов."""
from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.db.engine import session_scope
from app.db.models import Contest
from app.services.contest import finish_contest
from app.services.subscription import utcnow

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler(bot: Bot) -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        finish_due_contests, "interval", minutes=1, args=[bot], id="finish_contests"
    )
    _scheduler.start()
    logger.info("scheduler started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


async def finish_due_contests(bot: Bot) -> None:
    now = utcnow()
    async with session_scope() as session:
        due = (
            (
                await session.execute(
                    select(Contest).where(
                        Contest.status == "active",
                        Contest.ends_at <= now,
                    )
                )
            )
            .scalars()
            .all()
        )
        for contest in due:
            try:
                await finish_contest(bot, session, contest)
            except Exception:  # noqa: BLE001
                logger.exception("failed to finish contest %s", contest.id)
