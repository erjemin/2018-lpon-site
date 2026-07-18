#!/usr/bin/env bash
# Сборка Tailwind CSS для фронтенда LPON.RU
# Запуск из корня проекта: bash ./scripts/build-tailwind.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAILWIND_DIR="$PROJECT_ROOT/frontend-assembly/tailwind"
OUTPUT_DIR="$PROJECT_ROOT/public/static/css"

log() {
  printf '[tailwind] %s\n' "$*"
}

fail() {
  printf '[tailwind] %s\n' "$*" >&2
  exit 1
}

cleanup() {
  rm -rf "$TAILWIND_DIR/src" "$TAILWIND_DIR/node_modules" "$TAILWIND_DIR/tailwind.config.js" "$TAILWIND_DIR/input.css"
}

trap cleanup EXIT INT TERM

if ! command -v npm >/dev/null 2>&1; then
  fail 'Не найден `npm`. Установи Node.js и повтори сборку.'
fi

if [[ ! -f "$TAILWIND_DIR/package.json" ]]; then
  fail "Не найден package.json: $TAILWIND_DIR/package.json"
fi

if [[ ! -f "$TAILWIND_DIR/package-lock.json" ]]; then
  fail "Не найден package-lock.json: $TAILWIND_DIR/package-lock.json"
fi

mkdir -p "$OUTPUT_DIR"

log "Создаю entry point для Tailwind"

# input.css (entry point)
# Проверяем: если input.css вообще нет, только тогда создаем базовый
# ВАЖНО: Tailwind так устроен, что он собирает в CSS только те классы, которые реально используются в исходниках (HTML,
#        Python и т.д.) Это очень круто, т.к. финальный CSS проекта будет минимальным по размеру!
#        Чтобы Tailwind знал, где искать классы, нужно указать ему исходники через директиву @source в input.css.
#        @source "../../lpon_site/templates/**/*.html"; <-- ищем все HTML-шаблоны в проекте
#        @source "../../lpon_site/frontend/**/*.py";    <-- ищем все Python-файлы в проекте (например, там могут
#                                                           генерироваться классы, которые генерируют HTML)
cat > "$TAILWIND_DIR/input.css" <<'EOF'
@import "tailwindcss";

@source "../../lpon_site/templates/**/*.html";
@source "../../lpon_site/frontend/**/*.py";
EOF

log "СОБИРАЮ Tailwind CSS"
cd "$TAILWIND_DIR"

log 'Устанавливаю зависимости через npm ci'
npm ci

log 'Собираю CSS'
npm run build

log 'ГОТОВО! Результат: '"$OUTPUT_DIR/tailwind.min.css"
