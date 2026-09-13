"""Точка входа: FastAPI (веб + вебхуки) + aiogram (long polling)."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import settings
from app.context import get_payments
from app.db.engine import dispose_engine, init_db, session_scope
from app.db.models import Payment
from app.handlers import register_handlers
from app.i18n import t
from app.scheduler.jobs import start_scheduler, stop_scheduler
from app.services.payment_flow import finalize_payment
from app.web.routes import router as web_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def payment_webhook(provider: str, request: Request) -> JSONResponse:
    provider_obj = get_payments().get(provider)
    if provider_obj is None:
        return JSONResponse({"error": "unknown provider"}, status_code=404)

    raw = await request.body()
    body_text = raw.decode("utf-8")
    if not provider_obj.verify_signature(body_text, dict(request.headers)):
        return JSONResponse({"error": "bad signature"}, status_code=403)

    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError:
        return JSONResponse({"error": "bad json"}, status_code=400)

    result = provider_obj.parse_webhook(payload)

    status = "ignored"
    user = None
    async with session_scope() as session:
        payment = (
            await session.execute(
                select(Payment).where(
                    Payment.provider_payment_id == result.provider_payment_id
                )
            )
        ).scalar_one_or_none()
        if payment is None:
            return JSONResponse({"error": "unknown payment"}, status_code=404)

        if result.status == "succeeded":
            status, user = await finalize_payment(session, payment)
        else:
            payment.status = result.status

    if status == "succeeded" and user is not None:
        try:
            await request.app.state.bot.send_message(
                user.telegram_id, t("payment_ok")
            )
        except Exception:  # noqa: BLE001
            logger.exception("failed to notify user after payment")

    return JSONResponse({"ok": True})


async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    bot: Bot | None = None
    dp: Dispatcher | None = None
    poll_task: asyncio.Task | None = None

    if settings.bot_token:
        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher(storage=MemoryStorage())
        register_handlers(dp)
        poll_task = asyncio.create_task(
            dp.start_polling(bot, drop_pending_updates=True)
        )
    else:
        logger.warning("BOT_TOKEN не задан — бот не запустится.")

    app.state.bot = bot
    app.state.dp = dp
    app.state.poll_task = poll_task

    if bot is not None:
        start_scheduler(bot)

    yield

    if poll_task is not None:
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass

    stop_scheduler()
    if bot is not None:
        await bot.session.close()
    await dispose_engine()


app = FastAPI(title="Randomizer", lifespan=lifespan)
app.include_router(web_router)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "web" / "static")),
    name="static",
)
app.add_api_route("/health", health, methods=["GET"])
app.add_api_route("/payments/{provider}", payment_webhook, methods=["POST"])
