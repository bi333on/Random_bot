"""Кабинет организатора: конкурсы, участники, экспорт CSV."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select

from app.config import settings
from app.context import is_admin as is_tg_admin
from app.db.engine import session_scope
from app.db.models import Contest, Participant, User, Winner
from app.handlers.contest import parse_ends_at
from app.services.contest import publish_contest
from app.services.subscription import can_create_contest
from app.services.users import get_or_create_user
from app.web.auth import create_session_token, verify_session_token, verify_telegram_login
from app.web.templating import templates

router = APIRouter()


def current_session(request: Request) -> dict | None:
    token = request.cookies.get("session")
    if not token:
        return None
    return verify_session_token(token)


@router.get("/")
async def index(request: Request):
    if current_session(request) is None:
        return RedirectResponse("/login", status_code=302)
    return RedirectResponse("/cabinet", status_code=302)


@router.get("/login")
async def login(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"bot_username": settings.bot_login_username},
    )


@router.post("/auth/telegram/callback")
async def auth_callback(request: Request):
    form = await request.form()
    data = {key: value for key, value in form.items()}
    if not verify_telegram_login(data):
        return HTMLResponse("Bad signature", status_code=403)
    tg_id = int(data.get("id", 0))
    token = create_session_token(tg_id, is_tg_admin(tg_id))
    resp = RedirectResponse("/cabinet", status_code=302)
    resp.set_cookie(
        "session",
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.web_session_ttl,
    )
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("session")
    return resp


@router.get("/cabinet")
async def cabinet(request: Request):
    session_data = current_session(request)
    if session_data is None:
        return RedirectResponse("/login", status_code=302)
    async with session_scope() as session:
        user = await get_or_create_user(session, session_data["tg"])
        contests = (
            (
                await session.execute(
                    select(Contest)
                    .where(Contest.organizer_id == user.id)
                    .order_by(Contest.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        counts: dict[int, int] = {}
        for contest in contests:
            counts[contest.id] = (
                await session.execute(
                    select(func.count(Participant.id)).where(
                        Participant.contest_id == contest.id
                    )
                )
            ).scalar_one()
    return templates.TemplateResponse(
        request,
        "cabinet.html",
        {
            "user": user,
            "contests": contests,
            "counts": counts,
            "is_admin": session_data.get("admin", False),
        },
    )


@router.post("/cabinet/contest")
async def create_contest_web(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    channels: str = Form(""),
    condition: str = Form("subscribe"),
    winners: int = Form(1),
    ends_in: str = Form("1d"),
    prize: str = Form(""),
    announce: str = Form(""),
):
    session_data = current_session(request)
    if session_data is None:
        return RedirectResponse("/login", status_code=302)

    ends_at = parse_ends_at(ends_in)
    if ends_at is None or ends_at <= datetime.now(timezone.utc):
        return HTMLResponse("Неверный формат даты завершения", status_code=400)

    channel_list = (
        [c.strip() for c in channels.replace(" ", "").split(",") if c.strip()]
        if channels.strip()
        else []
    )

    async with session_scope() as session:
        user = await get_or_create_user(session, session_data["tg"])
        ok, reason = await can_create_contest(session, user)
        if not ok:
            return HTMLResponse(reason, status_code=403)
        contest = Contest(
            organizer_id=user.id,
            title=title.strip(),
            description=description.strip() or None,
            status="active",
            channel_usernames=channel_list,
            condition_type=condition,
            winners_count=max(1, winners),
            ends_at=ends_at,
            prize=prize.strip() or None,
            announce_chat_id=announce.strip() or None,
        )
        session.add(contest)
        await session.flush()
        try:
            await publish_contest(
                request.app.state.bot, session, contest, settings.bot_username
            )
        except Exception:  # noqa: BLE001
            pass
    return RedirectResponse("/cabinet", status_code=302)


@router.get("/cabinet/contest/{contest_id}")
async def contest_detail(request: Request, contest_id: int):
    session_data = current_session(request)
    if session_data is None:
        return RedirectResponse("/login", status_code=302)
    async with session_scope() as session:
        user = await get_or_create_user(session, session_data["tg"])
        contest = await session.get(Contest, contest_id)
        if contest is None or (
            contest.organizer_id != user.id and not session_data.get("admin")
        ):
            return HTMLResponse("Не найдено", status_code=404)
        rows = (
            await session.execute(
                select(Participant, User)
                .join(User, User.id == Participant.user_id)
                .where(Participant.contest_id == contest_id)
                .order_by(Participant.joined_at)
            )
        ).all()
        participants = [
            {
                "tg": u.telegram_id,
                "name": u.first_name or u.username or str(u.telegram_id),
                "username": u.username,
                "joined": p.joined_at,
            }
            for p, u in rows
        ]
        winners = (
            (
                await session.execute(
                    select(Winner)
                    .where(Winner.contest_id == contest_id)
                    .order_by(Winner.place)
                )
            )
            .scalars()
            .all()
        )
    return templates.TemplateResponse(
        request,
        "contest.html",
        {
            "contest": contest,
            "participants": participants,
            "winners": winners,
            "is_admin": session_data.get("admin", False),
        },
    )


@router.get("/cabinet/contest/{contest_id}/csv")
async def contest_csv(request: Request, contest_id: int):
    session_data = current_session(request)
    if session_data is None:
        return RedirectResponse("/login", status_code=302)
    async with session_scope() as session:
        user = await get_or_create_user(session, session_data["tg"])
        contest = await session.get(Contest, contest_id)
        if contest is None or (
            contest.organizer_id != user.id and not session_data.get("admin")
        ):
            return HTMLResponse("Не найдено", status_code=404)
        rows = (
            await session.execute(
                select(Participant, User)
                .join(User, User.id == Participant.user_id)
                .where(Participant.contest_id == contest_id)
                .order_by(Participant.joined_at)
            )
        ).all()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["telegram_id", "username", "name", "joined_at"])
        for p, u in rows:
            writer.writerow(
                [
                    u.telegram_id,
                    u.username or "",
                    u.first_name or "",
                    p.joined_at.isoformat(),
                ]
            )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=contest_{contest_id}.csv"
        },
    )
