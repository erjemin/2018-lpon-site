# CodeMirror 6 для Django Admin на LPON.RU

## Обзор

CodeMirror 6 — это мощный редактор кода/текста для использования в Django Admin. 
Используется для редактирования HTML, JavaScript, CSS и других текстовых полей со синтаксис-хайлайтингом.

## Структура проекта

```
frontend-assembly/
├── package.json              # Зависимости CodeMirror 6 (обновляй версии здесь!)
├── package-lock.json         # Заблокированные версии (обновляется через npm install)
├── build-codemirror6.sh      # Скрипт сборки (создает минифицированный бандл)
└── README.md

public/static/codemirror/
├── editor.js                 # Готовый минифицированный бандл (427 KB, GZIP ~130 KB)
└── README.md
```

## Версии пакетов (обновлены 11 июня 2026)

```json
{
  "@babel/runtime": "7.29.7",
  "@codemirror/autocomplete": "6.20.3",
  "@codemirror/commands": "6.10.3",
  "@codemirror/lang-css": "6.3.1",
  "@codemirror/lang-html": "6.4.11",
  "@codemirror/lang-javascript": "6.2.5",
  "@codemirror/language": "6.12.3",
  "@codemirror/state": "6.6.0",
  "@codemirror/view": "6.43.1",
  "@uiw/codemirror-theme-solarized": "4.25.10",
  "esbuild": "0.28.0"
}
```

### Что обновилось
- `@babel/runtime` 7.29.2 → 7.29.7
- `@codemirror/autocomplete` 6.20.1 → 6.20.3
- `@codemirror/view` 6.41.0 → 6.43.1
- `@uiw/codemirror-theme-solarized` 4.25.9 → 4.25.10

## О package-lock.json

**НИКОГДА не удаляй `package-lock.json` из репозитория!**

### Почему package-lock.json важен

1. **Воспроизводимость** - гарантирует одинаковые версии пакетов на всех машинах
2. **Скрипт сборки использует `npm ci`** - это команда для CI/CD, работает с package-lock.json
3. **Безопасность** - lockfile содержит хеши пакетов, которые проверяются при установке

### Правильный workflow обновления

```bash
# 1. Обновляешь версии в package.json
# 2. Удаляешь node_modules (опционально, можешь оставить)
# 3. Запускаешь:
npm install

# 4. npm автоматически обновит package-lock.json
# 5. Коммитишь обновленные package.json и package-lock.json в гит
```

## Как собрать CodeMirror

### Один раз (после обновления версий пакетов)

```bash
# Обновляешь версии в frontend-assembly/package.json
# Затем запускаешь сборку:
bash ./frontend-assembly/build-codemirror6.sh
```

### Что делает скрипт

1. Создает временную рабочую папку
2. Копирует `package.json` и `package-lock.json` туда
3. Генерирует файл `src/editor.js` с интеграцией CodeMirror 6
4. Запускает `npm ci` для установки точно таких же версий
5. Запускает `npm run build` для минификации через esbuild
6. Копирует результат в `public/static/codemirror/editor.js`
7. Удаляет временные файлы и папки

### Размеры
- Минифицированный бандл: **427 KB** (js файл)
- После GZIP: ~**130 KB** (в половине случаев браузер будет получать сжатый файл)

## Как использовать CodeMirror в Django Admin

### 1. Подключи скрипт в template админки

Добавь в `lpon_site/templates/admin/base_site.html` (или создай этот файл):

```html
{% extends "admin/base_site.html" %}

{% block extrahead %}
  {{ block.super }}
  <link rel="stylesheet" href="{% static 'codemirror/editor.css' %}">
  <script type="module" src="{% static 'codemirror/editor.js' %}"></script>
  <style>
    /* Стили для обертки CodeMirror */
    .cm6-editor-wrapper {
      height: 400px;
      border: 1px solid #ccc;
      border-radius: 4px;
      margin-bottom: 20px;
      font-size: 14px;
    }
    
    .cm-editor {
      height: 100% !important;
      font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
    }
  </style>
{% endblock %}
```

### 2. Используй в ModelForm

В `frontend/admin.py` для текстовых полей используй виджет с `data-codemirror-editor`:

```python
from django import forms

class ArticleForm(forms.ModelForm):
    """Форма для статей с CodeMirror"""
    
    class Meta:
        model = TbArticle
        fields = '__all__'
        widgets = {
            's_article_teaser_html': forms.Textarea(attrs={
                'data-codemirror-editor': 'true',
                'data-language': 'html',
                'class': 'vLargeTextField',
            }),
            's_article_content_html': forms.Textarea(attrs={
                'data-codemirror-editor': 'true',
                'data-language': 'html',
                'class': 'vLargeTextField',
            }),
        }

class ArticleAdmin(admin.ModelAdmin):
    form = ArticleForm
    # ... остальная конфигурация
```

### 3. Поддерживаемые языки

CodeMirror автоматически определяет язык по атрибуту `data-language`:

- `html` (по умолчанию) - HTML/Vue/Svelte шаблоны
- `javascript` - JavaScript/TypeScript код
- `css` - CSS стили

Пример:
```html
<textarea data-codemirror-editor data-language="javascript">
let x = 42;
console.log(x);
</textarea>
```

## Фишки CodeMirror 6

### Подсветка синтаксиса
- HTML / CSS / JavaScript с красивой подсветкой
- Тема Solarized (dark/light) автоматически определяется по теме админки

### Возможности
- :leftwards_arrow_with_hook: Undo/Redo
- :mag: Find and Replace (Ctrl+H / Cmd+Ctrl+H)
- :keyboard: Автодополнение (Ctrl+Space)
- :arrow_right: Автоотступы
- :straight_ruler: Нумерация строк
- :paperclip: Перенос слов на новую строку

### Синхронизация
Все изменения в CodeMirror:
1. Живо синхронизируются в скрытое текстовое поле
2. При сохранении формы отправляются на сервер

## Проверка работы

1. Откройся на http://localhost:8000/admin/
2. Перейди в раздел "Статьи" (или другой с HTML полями)
3. Создай или отредактируй статью
4. В полях с HTML кодом должен появиться CodeMirror с подсветкой синтаксиса

Вместо обычного текстового поля должен быть редактор с:
- Нумерацией строк слева
- Подсветкой синтаксиса (теги, атрибуты, значения...)
- Темой Solarized (light или dark)

## Обновление CodeMirror в будущем

Когда выйдут новые версии пакетов:

```bash
# 1. Проверь обновления
cd frontend-assembly
npm outdated

# 2. При необходимости обнови версии в package.json вручную
# Или используй npm update (осторожнее, может нарушить совместимость)

# 3. Пересоздай package-lock.json
rm package-lock.json
npm install

# 4. Собери новый бандл
bash build-codemirror6.sh

# 5. Коммит обновов (если через гит)
git add package.json package-lock.json ../public/static/codemirror/editor.js
git commit -m "Update CodeMirror 6 and dependencies"
```

## Возможные ошибки и решения

### Ошибка: "npm: command not found"
```bash
# Установи Node.js
brew install node
```

### Ошибка: "не найден package-lock.json"
```bash
# Пересоздай его
cd frontend-assembly
npm install
bash build-codemirror6.sh
```

### CodeMirror не появляется в админке
1. Проверь, что `public/static/codemirror/editor.js` существует
2. Проверь, что `static/` папка будет скопирована при deploy
3. Запусти `python manage.py collectstatic` если используешь Django collectstatic

### Медленная загрузка админки
CodeMirror бандл ~427 KB - это нормально. Он:
- :white_check_mark: кэшируется браузером
- :white_check_mark: отправляется в GZIP (~130 KB)
- :white_check_mark: загружается асинхронно

Если всё еще медленно, можно:
1. Использовать CDN (например, jsDelivr)
2. Лениво загружать CodeMirror только на нужных страницах

## Файлы конфигурации

### frontend-assembly/package.json
Главный файл для управления версиями. Обновляй здесь версии пакетов.

### frontend-assembly/package-lock.json
**Не трогай вручную!** Обновляется автоматически через `npm install`.

### frontend-assembly/build-codemirror6.sh
Скрипт сборки. Не требует изменений если только не нужна другая сборка.

### public/static/codemirror/
**Не редактируй вручную!** Пересоздается каждый раз при запуске `build-codemirror6.sh`.

## Дополнительное чтение

- [CodeMirror 6 документация](https://codemirror.net/docs/guide/)
- [Доступные расширения](https://codemirror.net/docs/ref/)
- [Solarized тема](https://github.com/uiwjs/codemirror-theme-solarized)

