#!/usr/bin/env bash
# Скрипт создаёт временную рабочую папку, ставит зависимости через `npm ci`, собирает
# минимизированный бандл и затем сам удаляет временные `src/` и `node_modules/`.
# В проекте остаётся только готовая статика:
# * `public/static/codemirror/editor.js`
#
# Запуск:
# bash ./frontend-assembly/build-codemirror6.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$ROOT_DIR/../public/static/codemirror"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/codemirror6.XXXXXX")"

log() {
  printf '[codemirror6] %s\n' "$*"
}

fail() {
  printf '[codemirror6] %s\n' "$*" >&2
  exit 1
}

cleanup() {
  rm -rf "$WORK_DIR"
  rm -rf "$ROOT_DIR/src" "$ROOT_DIR/node_modules"
}

trap cleanup EXIT INT TERM

if ! command -v npm >/dev/null 2>&1; then
  fail 'Не найден `npm`. Установи Node.js и повтори сборку.'
fi

if [[ ! -f "$ROOT_DIR/package.json" ]]; then
  fail "Не найден package.json: $ROOT_DIR/package.json"
fi

if [[ ! -f "$ROOT_DIR/package-lock.json" ]]; then
  fail "Не найден package-lock.json: $ROOT_DIR/package-lock.json"
fi

mkdir -p "$WORK_DIR/src" "$OUTPUT_DIR"
cp "$ROOT_DIR/package.json" "$ROOT_DIR/package-lock.json" "$WORK_DIR/"

cat > "$WORK_DIR/src/editor.js" <<'EOF'
import { Compartment, EditorState } from '@codemirror/state';
import { EditorView } from '@codemirror/view';
import { defaultHighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { html } from '@codemirror/lang-html';
import { javascript } from '@codemirror/lang-javascript';
import { css } from '@codemirror/lang-css';
import { solarizedDark, solarizedLight } from '@uiw/codemirror-theme-solarized';
import { lineNumbers } from '@codemirror/view';

const themeCompartment = new Compartment();

function isDarkTheme() {
  const rootTheme = document.documentElement.dataset.theme;

  if (rootTheme === 'dark') {
    return true;
  }

  if (rootTheme === 'light') {
    return false;
  }

  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function reconfigureTheme(view) {
  view.dispatch({
    effects: themeCompartment.reconfigure(isDarkTheme() ? solarizedDark : solarizedLight),
  });
}

function initCodeMirrorEditors() {
  document.querySelectorAll('textarea[data-codemirror-editor]').forEach((textarea) => {
    const language = textarea.dataset.language || 'html';
    const initialDoc = textarea.value ?? '';
    const wrapper = document.createElement('div');
    wrapper.className = 'cm6-editor-wrapper';
    textarea.insertAdjacentElement('beforebegin', wrapper);
    textarea.hidden = true;

    const syncTextarea = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        textarea.value = update.state.doc.toString();
      }
    });

    const extensions = [
      lineNumbers(),
      EditorView.lineWrapping,
      syntaxHighlighting(defaultHighlightStyle),
      syncTextarea,
      themeCompartment.of(isDarkTheme() ? solarizedDark : solarizedLight),
    ];

    if (language === 'javascript') {
      extensions.unshift(javascript());
    } else if (language === 'css') {
      extensions.unshift(css());
    } else {
      extensions.unshift(html());
    }

    const state = EditorState.create({
      doc: initialDoc,
      extensions,
    });

    const view = new EditorView({
      state,
      parent: wrapper,
    });

    reconfigureTheme(view);

    const observer = new MutationObserver(() => reconfigureTheme(view));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme', 'class'],
    });

    const colorScheme = window.matchMedia('(prefers-color-scheme: dark)');
    colorScheme.addEventListener('change', () => reconfigureTheme(view));

    textarea.value = view.state.doc.toString();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCodeMirrorEditors, { once: true });
} else {
  initCodeMirrorEditors();
}
EOF

log "СОБИРАЮ CodeMirror 6 ДЛЯ ФРОНТЕНДА АДМИНКИ ПРОЕКТА"
log "Временная рабочая папка: $WORK_DIR"
cd "$WORK_DIR"

log 'Устанавливаю зависимости через npm ci'
npm ci

log 'Собираю CodeMirror 6'
export CM6_OUTPUT_DIR="$OUTPUT_DIR"
npm run build

log 'ГОТОВО'
