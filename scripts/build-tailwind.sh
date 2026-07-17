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
  rm -rf "$TAILWIND_DIR/src" "$TAILWIND_DIR/node_modules" "$TAILWIND_DIR/tailwind.config.js"
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

log "Создаю конфиги и entry point для Tailwind"

# tailwind.config.js
cat > "$TAILWIND_DIR/tailwind.config.js" <<'EOF'
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    '../../lpon_site/templates/**/*.html',
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
EOF

# src/tailwind.css (entry point)
mkdir -p "$TAILWIND_DIR/src"
cat > "$TAILWIND_DIR/src/tailwind.css" <<'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;
EOF

log "СОБИРАЮ Tailwind CSS"
cd "$TAILWIND_DIR"

log 'Устанавливаю зависимости через npm ci'
npm ci

log 'Собираю CSS'
npm run build

log 'ГОТОВО! Результат: '"$OUTPUT_DIR/tailwind.min.css"
