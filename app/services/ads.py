"""Рекламные материалы."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ad


async def get_active_ads(session: AsyncSession) -> list[Ad]:
    rows = await session.execute(
        select(Ad).where(Ad.is_active.is_(True)).order_by(Ad.created_at)
    )
    return list(rows.scalars().all())
