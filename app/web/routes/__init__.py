"""Маршруты веб-кабинета."""
from __future__ import annotations

from fastapi import APIRouter

from app.web.routes import admin, cabinet

router = APIRouter()
router.include_router(cabinet.router)
router.include_router(admin.router)
