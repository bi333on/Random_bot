"""Модели БД (SQLAlchemy 2.0, async)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="participant")
    # participant | organizer | admin
    balance: Mapped[int] = mapped_column(Integer, default=0)  # в копейках
    referral_code: Mapped[Optional[str]] = mapped_column(
        String(32), unique=True, nullable=True
    )
    referred_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Кредиты разовых опций: {"weights": N, "anti_cheat": N, ...}
    addon_credits: Mapped[dict] = mapped_column(JSON, default=dict)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(Integer, default=0)  # в копейках
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    max_active_contests: Mapped[int] = mapped_column(Integer, default=1)
    max_participants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_winners: Mapped[int] = mapped_column(Integer, default=1)
    # features: weights, anti_cheat, hide_bot_mention,
    #           comment_condition, repost_condition, export_csv
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("plans.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default="active", index=True
    )  # active | expired | canceled
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payments.id"), nullable=True
    )
    paid_amount: Mapped[int] = mapped_column(Integer, default=0)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_payment_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    amount: Mapped[int] = mapped_column(Integer, default=0)  # в копейках
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", index=True
    )  # pending | succeeded | failed | canceled
    purpose: Mapped[str] = mapped_column(
        String(16), default="topup", index=True
    )  # subscription | addon | topup | ad
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PromoCode(Base):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    discount_type: Mapped[str] = mapped_column(
        String(16), default="percent"
    )  # percent | fixed
    discount_value: Mapped[int] = mapped_column(Integer, default=0)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BalanceTransaction(Base):
    __tablename__ = "balance_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)  # знаковое
    type: Mapped[str] = mapped_column(
        String(16), default="manual"
    )  # referral | promo | manual | spend | topup
    description: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Contest(Base):
    __tablename__ = "contests"

    id: Mapped[int] = mapped_column(primary_key=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="draft", index=True
    )  # draft | active | finished | canceled
    channel_usernames: Mapped[list] = mapped_column(JSON, default=list)
    condition_type: Mapped[str] = mapped_column(
        String(16), default="subscribe"
    )  # subscribe | comment | repost | none
    winners_count: Mapped[int] = mapped_column(Integer, default=1)
    participants_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prize: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    announce_chat_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    post_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    weights_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    anti_cheat_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    hide_bot_mention: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sponsored: Mapped[bool] = mapped_column(Boolean, default=False)
    sponsor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    result_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", name="uq_contest_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(
        ForeignKey("contests.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    sub_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    comment_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repost_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Winner(Base):
    __tablename__ = "winners"

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(
        ForeignKey("contests.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    place: Mapped[int] = mapped_column(Integer, default=1)
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Addon(Base):
    __tablename__ = "addons"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    addon_type: Mapped[str] = mapped_column(String(32))
    # weights | anti_cheat | hide_mention | extra_winners
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Ad(Base):
    __tablename__ = "ads"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
