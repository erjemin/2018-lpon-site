#!/usr/bin/env bash
# Сборка HTMX для фронтенда LPON.RU
# Запуск из корня проекта: bash ./scripts/build-htmx.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HTMX_DIR="$PROJECT_ROOT/frontend-assembly/htmx"
OUTPUT_DIR="$PROJECT_ROOT/public/static/js"

log() {
  printf '[htmx] %s\n' "$*"
}

fail() {
  printf '[htmx] %s\n' "$*" >&2
  exit 1
}

cleanup() {
  rm -rf "$HTMX_DIR/src" "$HTMX_DIR/node_modules"
}

trap cleanup EXIT INT TERM

if ! command -v npm >/dev/null 2>&1; then
  fail 'Не найден `npm`. Установи Node.js и повтори сборку.'
fi

if [[ ! -f "$HTMX_DIR/package.json" ]]; then
  fail "Не найден package.json: $HTMX_DIR/package.json"
fi

if [[ ! -f "$HTMX_DIR/package-lock.json" ]]; then
  fail "Не найден package-lock.json: $HTMX_DIR/package-lock.json"
fi

mkdir -p "$OUTPUT_DIR"

log "Создаю entry point для HTMX"

# src/htmx.js (entry point)
mkdir -p "$HTMX_DIR/src"
cat > "$HTMX_DIR/src/htmx.js" <<'EOF'
import htmx from 'htmx.org';

window.htmx = htmx;

export default htmx;
EOF

log "СОБИРАЮ HTMX"
cd "$HTMX_DIR"

log 'Устанавливаю зависимости через npm ci'
npm ci

log 'Собираю JavaScript'
npm run build

log 'ГОТОВО! Результат: '"$OUTPUT_DIR/htmx.min.js"
