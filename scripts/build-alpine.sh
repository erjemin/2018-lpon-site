#!/usr/bin/env bash
# Сборка Alpine.js для фронтенда LPON.RU
# Запуск из корня проекта: bash ./scripts/build-alpine.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALPINE_DIR="$PROJECT_ROOT/frontend-assembly/alpine"
OUTPUT_DIR="$PROJECT_ROOT/public/static/js"

log() {
  printf '[alpine] %s\n' "$*"
}

fail() {
  printf '[alpine] %s\n' "$*" >&2
  exit 1
}

cleanup() {
  rm -rf "$ALPINE_DIR/src" "$ALPINE_DIR/node_modules"
}

trap cleanup EXIT INT TERM

if ! command -v npm >/dev/null 2>&1; then
  fail 'Не найден `npm`. Установи Node.js и повтори сборку.'
fi

if [[ ! -f "$ALPINE_DIR/package.json" ]]; then
  fail "Не найден package.json: $ALPINE_DIR/package.json"
fi

if [[ ! -f "$ALPINE_DIR/package-lock.json" ]]; then
  fail "Не найден package-lock.json: $ALPINE_DIR/package-lock.json"
fi

mkdir -p "$OUTPUT_DIR"

log "Создаю entry point для Alpine.js"

# src/alpine.js (entry point)
mkdir -p "$ALPINE_DIR/src"
cat > "$ALPINE_DIR/src/alpine.js" <<'EOF'
import Alpine from 'alpinejs';

Alpine.start();

export default Alpine;
EOF

log "СОБИРАЮ Alpine.js"
cd "$ALPINE_DIR"

log 'Устанавливаю зависимости через npm ci'
npm ci

log 'Собираю JavaScript'
npm run build

log 'ГОТОВО! Результат: '"$OUTPUT_DIR/alpine.min.js"
