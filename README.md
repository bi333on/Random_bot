# 🎲 Randomizer — бот-рандомайзер конкурсов с монетизацией

Telegram-бот на **Python + aiogram 3** для проведения конкурсов/розыгрышей
с честным выбором победителей, плюс **веб-кабинет организатора** (FastAPI + Jinja2)
и **PostgreSQL**. Монетизация: тарифы-подписки, разовые опции, реферальная
программа, реклама/спонсорские конкурсы. Оплата: ЮKassa, CryptoBot, RollyPay.

## Возможности

**Конкурсы**
- Визард создания: название, описание, каналы, условие (подписка/комментарий/репост/без условий),
  число победителей, срок, приз, место публикации.
- Кнопка «🎲 Участвовать» в посте конкурса.
- Проверка подписки на каналы через `getChatMember`.
- Анти-чит: отсев ботов, блокировка забаненных, требование username, защита от дублей.
- Взвешенный выбор победителей (веса/множители), криптостойкий `SystemRandom`.
- Авто-подведение итогов по таймеру (APScheduler), объявление в канале и ЛС организатора,
  поздравление победителей.

**Монетизация**
- Тарифы (планы) с лимитами: активные конкурсы, участники, победители, набор фич.
- Разовые опции: веса, анти-чит, скрытие упоминания бота, доп. победители.
- Промокоды (%/фикс. скидка), оплата с баланса.
- Реферальная программа: % с первой покупки приглашённого.
- Реклама/спонсорские конкурсы (модель `ads` + флаг `is_sponsored`).

**Платежи**
- ЮKassa (карты/СБП), CryptoBot (USDT), RollyPay — за единым интерфейсом `PaymentProvider`.
- Вебхуки на `/payments/{provider}`, проверка подписей.

**Веб-кабинет**
- Вход через Telegram Login Widget.
- Кабинет организатора: список конкурсов, создание, участники, результаты, экспорт CSV.
- Админка: статистика, тарифы, промокоды, реклама, пополнение баланса, платежи.

## Структура

```
Randomizer/
├── app/
│   ├── main.py              # FastAPI + aiogram polling (lifespan)
│   ├── config.py            # pydantic-settings
│   ├── context.py           # синглтоны платежей, is_admin
│   ├── i18n.py              # строки RU
│   ├── db/                  # модели, движок, Alembic
│   ├── payments/            # провайдеры оплаты
│   ├── services/            # contest, randomizer, anti_cheat, promo, referral, ...
│   ├── handlers/            # роутеры бота (user, contest, purchase, admin)
│   ├── scheduler/           # авто-подведение итогов
│   └── web/                 # веб-кабинет (auth, routes, templates, static)
├── deploy/                  # docker-compose + Caddy
├── tests/
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Быстрый старт (локально)

```bash
cd Randomizer
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # заполнить BOT_TOKEN, ADMIN_IDS, DATABASE_URL
# поднять PostgreSQL (например, docker run -d -p 5432:5432 -e POSTGRES_USER=randomizer \
#   -e POSTGRES_PASSWORD=randomizer -e POSTGRES_DB=randomizer postgres:16-alpine)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Бот запускается long polling внутри того же процесса, что и веб.
Перед запуском создайте в БД хотя бы один тариф (через веб-админку `/admin`
после входа администратором) — иначе организаторы не смогут создавать конкурсы.

## Деплой (VPS + Caddy одной командой)

```bash
sudo bash install.sh
```

Установщик сам поставит Docker (если нет), спросит домен, `BOT_TOKEN`,
`BOT_USERNAME` и `ADMIN_IDS`, сгенерирует `.env` и `deploy/Caddyfile`,
поднимет PostgreSQL + приложение + Caddy с автоматическим HTTPS.

Неинтерактивно:

```bash
sudo DOMAIN=bot.example.com BOT_TOKEN=123:ABC BOT_USERNAME=MyBot ADMIN_IDS=123456 bash install.sh
```

Либо со свежего VPS одной строкой:

```bash
git clone https://github.com/bi333on/Random_bot.git && cd Random_bot && sudo bash install.sh
```

Веб-кабинет и платёжные вебхуки будут доступны по вашему домену.
После запуска войдите админом (Telegram ID из `ADMIN_IDS`) и создайте тариф в `/admin`.

### Ручной деплой (без install.sh)

```bash
cp .env.example .env   # заполнить секреты
# в deploy/Caddyfile заменить randomizer.example.com на свой домен
docker compose up -d --build
```

## Администрирование

- В боте: `/admin` — статистика, `/topup <tg_id> <рубли>`, `/broadcast <текст>`.
- В вебе `/admin` — тарифы, промокоды, реклама, пополнение, платежи.

## Тесты

```bash
pytest
```

## Платёжные вебхуки

- ЮKassa: `https://<домен>/payments/yookassa`
- CryptoBot: `https://<домен>/payments/cryptobot`
- RollyPay: `https://<домен>/payments/rollypay`

Поля интеграций RollyPay сверьте с документацией провайдера
(`app/payments/rollypay.py` — заготовка под документацию).

## Примечания

- Условие «репост» в v1 — самодекларация (Telegram API не позволяет достоверно
  проверить репост). «Комментарий» — без автоматической проверки текста.
- Для прод-миграций используйте Alembic: `alembic upgrade head`.
  В dev-режиме таблицы создаются автоматически через `Base.metadata.create_all`.
