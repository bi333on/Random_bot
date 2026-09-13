"""Клавиатуры бота."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import t


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t("menu_create"), callback_data="create_contest")],
        [InlineKeyboardButton(text=t("menu_my"), callback_data="my_contests")],
        [InlineKeyboardButton(text=t("menu_shop"), callback_data="shop")],
        [
            InlineKeyboardButton(text=t("menu_balance"), callback_data="balance"),
            InlineKeyboardButton(text=t("menu_referral"), callback_data="referral"),
        ],
        [InlineKeyboardButton(text=t("menu_support"), callback_data="support")],
    ]
    if is_admin:
        rows.append(
            [InlineKeyboardButton(text=t("menu_admin"), callback_data="admin_menu")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("back_menu"), callback_data="menu")]
        ]
    )


def condition_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписка на канал", callback_data="cond:subscribe")],
            [InlineKeyboardButton(text="💬 Комментарий", callback_data="cond:comment")],
            [InlineKeyboardButton(text="🔁 Репост", callback_data="cond:repost")],
            [InlineKeyboardButton(text="❌ Без условий", callback_data="cond:none")],
        ]
    )


def _mark(value) -> str:
    return "✅" if value else "⬜"


def options_keyboard(data: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{_mark(data.get('weights'))} Веса/множители",
                    callback_data="opt:weights",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{_mark(data.get('anti_cheat'))} Анти-чит",
                    callback_data="opt:anti_cheat",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{_mark(data.get('hide_mention'))} Скрыть упоминание бота",
                    callback_data="opt:hide_mention",
                )
            ],
            [InlineKeyboardButton(text="Готово ✅", callback_data="opt:done")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_contest")],
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать", callback_data="confirm_yes"),
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data="cancel_contest"
                ),
            ]
        ]
    )


def shop_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Тарифы", callback_data="shop:plans")],
            [InlineKeyboardButton(text="⚡ Опции", callback_data="shop:addons")],
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="shop:topup")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu")],
        ]
    )


PROVIDER_LABELS = {
    "yookassa": "💳 Картой / СБП",
    "cryptobot": "🪙 CryptoBot (USDT)",
    "rollypay": "🧾 RollyPay",
}


def pay_methods_keyboard(
    providers: list[str],
    prefix: str,
    allow_balance: bool = False,
    back_cb: str = "shop",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if allow_balance:
        rows.append(
            [
                InlineKeyboardButton(
                    text="💰 Оплатить с баланса",
                    callback_data=f"{prefix}:balance",
                )
            ]
        )
    for provider in providers:
        rows.append(
            [
                InlineKeyboardButton(
                    text=PROVIDER_LABELS.get(provider, provider),
                    callback_data=f"{prefix}:{provider}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pay_url_keyboard(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("pay_button"), url=pay_url)]
        ]
    )
