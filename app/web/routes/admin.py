"""Веб-админка: тарифы, промокоды, реклама, платежи, пополнение."""
from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from app.db.engine import session_scope
from app.db.models import Ad, Payment, Plan, PromoCode, User
from app.services.balance import add_balance
from app.web.auth import verify_session_token
from app.web.templating import templates

router = APIRouter()


def _guard(request: Request) -> dict | None:
    token = request.cookies.get("session")
    if not token:
        return None
    data = verify_session_token(token)
    if data is None or not data.get("admin"):
        return None
    return data


@router.get("/admin")
async def admin_dashboard(request: Request):
    guard = _guard(request)
    if guard is None:
        return RedirectResponse("/login", status_code=302)
    async with session_scope() as session:
        users = (await session.execute(select(func.count(User.id)))).scalar_one()
        revenue = (
            await session.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.status == "succeeded"
                )
            )
        ).scalar_one()
        plans = (await session.execute(select(Plan).order_by(Plan.position))).scalars().all()
        promos = (await session.execute(select(PromoCode))).scalars().all()
        ads = (await session.execute(select(Ad).order_by(Ad.created_at.desc()))).scalars().all()
        payments = (
            (
                await session.execute(
                    select(Payment).order_by(Payment.created_at.desc()).limit(50)
                )
            )
            .scalars()
            .all()
        )
        recent_users = (
            (
                await session.execute(
                    select(User).order_by(User.created_at.desc()).limit(50)
                )
            )
            .scalars()
            .all()
        )
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "is_admin": True,
            "users": users,
            "revenue": revenue,
            "plans": plans,
            "promos": promos,
            "ads": ads,
            "payments": payments,
            "recent_users": recent_users,
        },
    )


@router.post("/admin/plan")
async def create_plan(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    price: str = Form("0"),
    duration_days: int = Form(30),
    max_active_contests: int = Form(1),
    max_participants: str = Form(""),
    max_winners: int = Form(1),
    weights: str = Form(""),
    anti_cheat: str = Form(""),
    hide_bot_mention: str = Form(""),
    comment_condition: str = Form(""),
    repost_condition: str = Form(""),
    export_csv: str = Form(""),
):
    if _guard(request) is None:
        return RedirectResponse("/login", status_code=302)
    try:
        price_kop = int(round(float(price.replace(",", ".")) * 100))
    except ValueError:
        return HTMLResponse("Неверная цена", status_code=400)
    async with session_scope() as session:
        position = (
            await session.execute(select(func.coalesce(func.max(Plan.position), 0)))
        ).scalar_one() or 0
        session.add(
            Plan(
                name=name,
                description=description or None,
                price=price_kop,
                duration_days=duration_days,
                max_active_contests=max_active_contests,
                max_participants=int(max_participants) if max_participants.strip() else None,
                max_winners=max_winners,
                features={
                    "weights": bool(weights),
                    "anti_cheat": bool(anti_cheat),
                    "hide_bot_mention": bool(hide_bot_mention),
                    "comment_condition": bool(comment_condition),
                    "repost_condition": bool(repost_condition),
                    "export_csv": bool(export_csv),
                },
                position=int(position) + 1,
                is_active=True,
            )
        )
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/plan/{plan_id}/toggle")
async def toggle_plan(request: Request, plan_id: int):
    if _guard(request) is None:
        return RedirectResponse("/login", status_code=302)
    async with session_scope() as session:
        plan = await session.get(Plan, plan_id)
        if plan is not None:
            plan.is_active = not plan.is_active
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/promo")
async def create_promo(
    request: Request,
    code: str = Form(...),
    discount_type: str = Form("percent"),
    discount_value: int = Form(0),
    max_uses: str = Form(""),
):
    if _guard(request) is None:
        return RedirectResponse("/login", status_code=302)
    async with session_scope() as session:
        session.add(
            PromoCode(
                code=code.strip().upper(),
                discount_type=discount_type,
                discount_value=discount_value,
                max_uses=int(max_uses) if max_uses.strip() else None,
                is_active=True,
            )
        )
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/ad")
async def create_ad(
    request: Request,
    title: str = Form(...),
    text: str = Form(""),
    url: str = Form(""),
):
    if _guard(request) is None:
        return RedirectResponse("/login", status_code=302)
    async with session_scope() as session:
        session.add(
            Ad(
                title=title,
                text=text or None,
                url=url or None,
                is_active=True,
            )
        )
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/ad/{ad_id}/toggle")
async def toggle_ad(request: Request, ad_id: int):
    if _guard(request) is None:
        return RedirectResponse("/login", status_code=302)
    async with session_scope() as session:
        ad = await session.get(Ad, ad_id)
        if ad is not None:
            ad.is_active = not ad.is_active
    return RedirectResponse("/admin", status_code=302)


@router.post("/admin/topup")
async def topup_user(
    request: Request,
    telegram_id: int = Form(...),
    rubles: int = Form(...),
):
    if _guard(request) is None:
        return RedirectResponse("/login", status_code=302)
    async with session_scope() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
        ).scalar_one_or_none()
        if user is not None:
            await add_balance(
                session, user, rubles * 100, "manual", "Админ пополнение (веб)"
            )
    return RedirectResponse("/admin", status_code=302)
