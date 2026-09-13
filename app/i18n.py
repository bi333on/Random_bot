"""Строковые ресурсы интерфейса (RU)."""
from __future__ import annotations

from app.config import settings


def money(value: int) -> str:
    """Форматировать сумму в копейках как рубли."""
    rub = value / 100
    if rub == int(rub):
        return f"{int(rub):,}".replace(",", " ")
    return f"{rub:,.2f}".replace(",", " ")


T = {
    "start": (
        "🎲 <b>Рандомайзер конкурсов</b>\n\n"
        "Я помогу провести розыгрыш в Telegram: проверю подписку на каналы, "
        "уберу ботов и честно выберу победителей (с весами, если нужно).\n\n"
        "Выберите действие:"
    ),
    "menu_create": "➕ Создать конкурс",
    "menu_my": "📋 Мои конкурсы",
    "menu_shop": "🛒 Тарифы и опции",
    "menu_balance": "💰 Баланс",
    "menu_referral": "👥 Реферальная программа",
    "menu_support": "💬 Поддержка",
    "menu_admin": "🛠 Админ",
    "back_menu": "🔙 В меню",
    "no_subscription": (
        "Для создания конкурсов нужна активная подписка.\n"
        "Перейдите в «🛒 Тарифы и опции» и выберите тариф."
    ),
    "limit_reached": "Достигнут лимит активных конкурсов по вашему тарифу.",
    "profile": (
        "👤 <b>Профиль</b>\n"
        "ID: <code>{tg_id}</code>\n"
        "Баланс: <b>{balance} ₽</b>\n"
        "Подписка: {plan}\n"
        "Роль: {role}"
    ),
    "balance": "💰 Ваш баланс: <b>{balance} ₽</b>",
    "referral": (
        "👥 <b>Реферальная программа</b>\n\n"
        "Ваш код: <code>{code}</code>\n"
        "Ссылка: {link}\n\n"
        "Вы получаете <b>{percent}%</b> с первой покупки приглашённого друга на свой баланс."
    ),
    "support": "💬 Свяжитесь с поддержкой: {link}",
    "admin_stats": (
        "🛠 <b>Админ-статистика</b>\n"
        "Пользователей: {users}\n"
        "Активных конкурсов: {contests}\n"
        "Активных подписок: {subs}\n"
        "Выручка (оплачено): {revenue} ₽"
    ),
    "broadcast_ok": "✅ Рассылка запущена: {sent} / {total}",
    "topup_ok": "✅ Баланс пополнен на {amount} ₽. Новый баланс: {balance} ₽",
    "contest_created": (
        "🎉 <b>Конкурс создан!</b>\n\n"
        "Название: {title}\n"
        "Победителей: {winners}\n"
        "Завершение: {ends_at}\n\n"
        "Пост опубликован. Участники нажмут кнопку «Участвовать»."
    ),
    "already_joined": "Вы уже участвуете в этом конкурсе.",
    "joined": "✅ Вы участвуете в конкурсе «{title}»! Желаем удачи 🍀",
    "not_subscribed": (
        "⚠️ Для участия нужно подписаться на каналы:\n{channels}"
    ),
    "contest_finished": "Этот конкурс уже завершён.",
    "contest_join": "🎲 Участвовать",
    "results_title": "🏆 <b>Итоги конкурса «{title}»</b>\n\n{results}",
    "winner_line": "{place}. <a href=\"tg://user?id={tg_id}\">{name}</a>",
    "no_participants": "В конкурсе не было участников.",
    "pay_balance_ok": "✅ Оплата с баланса прошла успешно.",
    "pay_balance_fail": "❌ Недостаточно средств на балансе.",
    "invoice_created": "🧾 Счёт создан. К оплате: <b>{amount} ₽</b>.",
    "pay_button": "💳 Оплатить",
    "invoice_error": "Ошибка создания счёта: {error}",
    "payment_ok": "✅ Оплата получена. Спасибо!",
    "plan_none": "Без подписки",
    "role_user": "участник",
    "role_admin": "администратор",
    "role_org": "организатор",
}


def t(key: str, **kwargs) -> str:
    return T.get(key, key).format(**kwargs)
