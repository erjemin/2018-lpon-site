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

# Скрипт идемпотентный и не оставляет после себя рабочих файлов: input.css
# генерируется заново при каждом запуске (см. ниже), а node_modules ставится
# через `npm ci` (чистая установка по package-lock.json). Поэтому ни один из
# этих файлов не хранится в репозитории и не добавлен в .gitignore отдельно -
# cleanup() гарантированно подчищает их за собой при любом завершении скрипта
# (успех, ошибка, Ctrl+C). Единственное исключение - если процесс убьют
# принудительно (kill -9/SIGKILL), тогда trap не сработает и файлы останутся
# на диске; в этом случае их можно смело удалить руками либо просто повторно
# запустить скрипт - он всё перезапишет.
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

# input.css (entry point для Tailwind CLI).
# ВАЖНО: этот файл перезаписывается безусловно при КАЖДОМ запуске скрипта
#        (не только если его нет) - он одноразовый, генерируется прямо здесь
#        через heredoc и удаляется в конце работы скрипта через cleanup()
#        (см. начало файла). Поэтому input.css не хранится в репозитории и
#        его не нужно редактировать руками - любые правки нужно вносить
#        в текст heredoc ниже, иначе они потеряются при следующей сборке.
# ВАЖНО: Tailwind так устроен, что он собирает в CSS только те классы, которые реально используются в исходниках (HTML,
#        Python и т.д.) Это очень круто, т.к. финальный CSS проекта будет минимальным по размеру!
#        Чтобы Tailwind знал, где искать классы, нужно указать ему исходники через директиву @source в input.css
#        (см. подробный комментарий прямо над самими директивами @source внутри heredoc ниже).
cat > "$TAILWIND_DIR/input.css" <<'EOF'
/*
  input.css — точка входа для сборки prod-версии Tailwind CSS (Tailwind CLI).

  Собирается командой `npm run build` (см. package.json в этой же папке) в
  файл public/static/css/tailwind.min.css, который подключается в _base.html
  для production (когда settings.DEBUG == False).

  Здесь же подключаются кастомные @theme/@layer директивы проекта из общего
  файла lpon_site/templates/css/tailwind-custom.css — того же самого файла,
  который в dev-режиме подключается через {% include %} внутрь инлайнового
  <style type="text/tailwindcss"> в _base.html. Это обеспечивает единый
  источник кастомных стилей для dev и prod
*/
@import "tailwindcss";
@import "../../lpon_site/templates/css/tailwind-custom.css";

/* Директива @source указывает Tailwind, ГДЕ искать реально используемые
   классы (см. общее пояснение про @source выше, перед heredoc). Пути ниже
   заданы относительно этого файла (frontend-assembly/tailwind/input.css),
   поэтому "../../" ведёт в корень проекта. Если появятся новые каталоги с
   разметкой/классами (например, отдельное приложение или папка partials
   за пределами уже перечисленных путей), их нужно будет добавить сюда
   отдельной строкой @source - иначе Tailwind не увидит использованные в
   них классы и просто не включит их в итоговый tailwind.min.css. */
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
