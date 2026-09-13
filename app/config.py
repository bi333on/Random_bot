"""Конфигурация приложения (pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Telegram ---
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    bot_username: str = Field(default="", alias="BOT_USERNAME")
    admin_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list, alias="ADMIN_IDS"
    )

    # --- Storage ---
    database_url: str = Field(
        default="postgresql+asyncpg://randomizer:randomizer@localhost:5432/randomizer",
        alias="DATABASE_URL",
    )

    # --- Polling / webhook ---
    polling_mode: bool = Field(default=True, alias="POLLING_MODE")
    webhook_host: str = Field(default="", alias="WEBHOOK_HOST")
    webhook_path: str = Field(default="/telegram", alias="WEBHOOK_PATH")
    webhook_secret: str = Field(default="", alias="WEBHOOK_SECRET_TOKEN")

    # --- Web ---
    web_host: str = Field(default="0.0.0.0", alias="WEB_HOST")
    web_port: int = Field(default=8000, alias="WEB_PORT")
    web_base_url: str = Field(default="", alias="WEB_BASE_URL")
    web_app_secret: str = Field(default="change-me", alias="WEB_APP_SECRET")
    web_session_ttl: int = Field(default=60 * 60 * 24 * 14, alias="WEB_SESSION_TTL")

    # --- Деньги / рефералка ---
    currency: str = Field(default="RUB", alias="CURRENCY")
    referral_percent: int = Field(default=10, alias="REFERRAL_PERCENT")
    support_link: str = Field(default="https://t.me/support", alias="SUPPORT_LINK")
    channel_link: str = Field(default="", alias="CHANNEL_LINK")
    web_link: str = Field(default="", alias="WEB_CABINET_LINK")

    # --- Тарифы/опции: цены разовых опций (в копейках) ---
    addon_weights_price: int = Field(default=10_000, alias="ADDON_WEIGHTS_PRICE")
    addon_anticheat_price: int = Field(default=15_000, alias="ADDON_ANTICHEAT_PRICE")
    addon_hide_mention_price: int = Field(
        default=5_000, alias="ADDON_HIDE_MENTION_PRICE"
    )
    addon_extra_winners_price: int = Field(
        default=20_000, alias="ADDON_EXTRA_WINNERS_PRICE"
    )

    # --- ЮKassa ---
    yookassa_enabled: bool = Field(default=False, alias="YOOKASSA_ENABLED")
    yookassa_shop_id: str = Field(default="", alias="YOOKASSA_SHOP_ID")
    yookassa_secret_key: str = Field(default="", alias="YOOKASSA_SECRET_KEY")

    # --- CryptoBot (Crypto Pay) ---
    cryptobot_enabled: bool = Field(default=False, alias="CRYPTOBOT_ENABLED")
    cryptobot_api_token: str = Field(default="", alias="CRYPTOBOT_API_TOKEN")
    cryptobot_webhook_secret: str = Field(
        default="", alias="CRYPTOBOT_WEBHOOK_SECRET"
    )

    # --- RollyPay ---
    rollypay_enabled: bool = Field(default=False, alias="ROLLYPAY_ENABLED")
    rollypay_api_url: str = Field(
        default="https://api.rollypay.com", alias="ROLLYPAY_API_URL"
    )
    rollypay_api_key: str = Field(default="", alias="ROLLYPAY_API_KEY")
    rollypay_secret: str = Field(default="", alias="ROLLYPAY_SECRET")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_comma_separated(cls, value):
        if isinstance(value, str):
            return [int(x.strip()) for x in value.split(",") if x.strip()]
        return value

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_host}{self.webhook_path}"

    @property
    def bot_login_username(self) -> str:
        """Username бота без '@' для Telegram Login Widget."""
        return (self.bot_username or "").strip().lstrip("@")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
