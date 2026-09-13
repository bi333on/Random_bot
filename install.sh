#!/usr/bin/env bash
# Установщик Randomizer: VPS + Docker + Caddy одной командой.
# Запускать от root (или через sudo).
#
# Неинтерактивно:
#   sudo DOMAIN=bot.example.com BOT_TOKEN=... BOT_USERNAME=... ADMIN_IDS=... bash install.sh
# Либо флагами:
#   sudo bash install.sh --domain bot.example.com --token 123:ABC --bot-username MyBot --admin 123456
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Запустите через sudo: sudo bash install.sh" >&2
    exit 1
fi

DOMAIN="${DOMAIN:-}"
BOT_TOKEN="${BOT_TOKEN:-}"
BOT_USERNAME="${BOT_USERNAME:-}"
ADMIN_IDS="${ADMIN_IDS:-}"
WEB_APP_SECRET="${WEB_APP_SECRET:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) DOMAIN="$2"; shift 2 ;;
        --token) BOT_TOKEN="$2"; shift 2 ;;
        --bot-username) BOT_USERNAME="$2"; shift 2 ;;
        --admin) ADMIN_IDS="$2"; shift 2 ;;
        --secret) WEB_APP_SECRET="$2"; shift 2 ;;
        *) echo "Неизвестный аргумент: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$DOMAIN" ]]; then read -rp "Домен (например bot.example.com): " DOMAIN; fi
if [[ -z "$BOT_TOKEN" ]]; then read -rp "BOT_TOKEN: " BOT_TOKEN; fi
if [[ -z "$BOT_USERNAME" ]]; then read -rp "BOT_USERNAME (@не указывать): " BOT_USERNAME; fi
if [[ -z "$ADMIN_IDS" ]]; then read -rp "ADMIN_IDS (Telegram ID через запятую): " ADMIN_IDS; fi
if [[ -z "$WEB_APP_SECRET" ]]; then
    WEB_APP_SECRET="$(openssl rand -hex 32 2>/dev/null || echo 'change-me-please')"
fi

echo ">> Проверяю Docker..."
if ! command -v docker >/dev/null 2>&1; then
    echo ">> Устанавливаю Docker..."
    curl -fsSL https://get.docker.com | sh
fi
if ! docker compose version >/dev/null 2>&1; then
    echo ">> Устанавливаю docker compose plugin..."
    apt-get update -y >/dev/null
    apt-get install -y docker-compose-plugin >/dev/null || true
fi

echo ">> Генерирую .env..."
cat > .env <<EOF
BOT_TOKEN=$BOT_TOKEN
BOT_USERNAME=$BOT_USERNAME
ADMIN_IDS=$ADMIN_IDS
DATABASE_URL=postgresql+asyncpg://randomizer:randomizer@localhost:5432/randomizer
WEB_BASE_URL=https://$DOMAIN
WEB_APP_SECRET=$WEB_APP_SECRET
POLLING_MODE=true
CURRENCY=RUB
REFERRAL_PERCENT=10
SUPPORT_LINK=https://t.me/support
EOF

echo ">> Генерирую deploy/Caddyfile..."
mkdir -p deploy
cat > deploy/Caddyfile <<EOF
$DOMAIN {
    reverse_proxy app:8000
}
EOF

echo ">> Собираю и запускаю контейнеры..."
docker compose up -d --build

echo ""
echo "✅ Готово!"
echo "   Веб-кабинет: https://$DOMAIN"
echo "   Health:      https://$DOMAIN/health"
echo "   Дальше: войдите админом по Telegram ID из ADMIN_IDS и создайте тариф в /admin"
