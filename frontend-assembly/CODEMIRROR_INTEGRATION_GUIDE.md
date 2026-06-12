# CodeMirror 6 для Django Admin на LPON.RU

## Обзор

Это руководство описывает, как использовать и обновлять сборку CodeMirror 6, которая используется для редактирования текстовых полей в админке Django.

## Структура проекта

- `frontend-assembly/`: Исходные файлы и скрипты для сборки.
  - `package.json`: Список зависимостей CodeMirror 6.
  - `package-lock.json`: Файл с зафиксированными версиями зависимостей. **Не редактировать вручную!**
  - `build-codemirror6.sh`: Скрипт, который генерирует и собирает финальный JS-бандл.
- `public/static/codemirror/`: Каталог с готовыми файлами для Django.
  - `editor.js`: Финальный, минифицированный JS-бандл. **Не редактировать вручную!**
  - `codemirror-styles.css`: Кастомные стили для интеграции с админкой.
  - `codemirror-patch.js`: JS-патч для управления размерами редактора.

## Как собрать бандл

После клонирования репозитория или обновления зависимостей, выполните:

```bash
# Перейдите в каталог сборки
cd frontend-assembly

# Установите зависимости и соберите бандл
bash ./build-codemirror6.sh
```

## Как использовать в Django Admin

### 1. Подключение в ModelAdmin

В вашем `admin.py` используйте `Media` класс для подключения необходимых файлов.

```python
# frontend/admin.py

class YourModelAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('codemirror/codemirror-styles.css',)
        }
        js = (
            'codemirror/editor.js',
            'codemirror/codemirror-patch.js',
        )
```

### 2. Активация для полей

Чтобы превратить стандартный `Textarea` в редактор CodeMirror, используйте кастомную форму или метод `formfield_for_dbfield` и добавьте к виджету специальные `data-` атрибуты.

```python
# frontend/admin.py

class YourModelAdmin(admin.ModelAdmin):
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        
        # Активируем CodeMirror для всех текстовых полей
        if isinstance(formfield.widget, forms.Textarea):
            formfield.widget.attrs['data-codemirror-editor'] = 'true'

            # Устанавливаем язык в зависимости от имени поля
            if 'j_' in db_field.name:
                # Обычно в моделях LPON поля с префиксом 'j_' содержат JSON
                formfield.widget.attrs['data-language'] = 'json'
            elif 'html' in db_field.name:
                formfield.widget.attrs['data-language'] = 'html'
            else:
                formfield.widget.attrs['data-language'] = 'text' # Обычный текст

            # Добавляем утилитарные CSS-классы для стилизации
            if db_field.name == 'i_img_sort':
                formfield.widget.attrs['class'] = 'codemirror-width-s codemirror-no-lines'
            elif db_field.name == 'j_seller_metadata':
                formfield.widget.attrs['class'] = 'codemirror-width-xl codemirror-min-height-m'

        return formfield
```

### 3. Поддерживаемые языки

- `javascript`
- `css`
- `json`
- `html` (по умолчанию, в него встроенны режимы подсветки синтенза HTML, XML, CSS и JavaScript)
- `text` (обычный текст, без подсветки синтакса, unocode-режим)

## Кастомизация

### Управление размерами и стилями

В файле `public/static/codemirror/codemirror-styles.css` определены утилитарные CSS-классы для управления внешним
видом редакторов:

- **Ширина**: `.codemirror-width-s`, `.codemirror-width-m`, `.codemirror-width-l`, `.codemirror-width-xl`
- **Минимальная высота**: `.codemirror-min-height-5` и `.codemirror-min-height-10` (по 5 и 10 строк соответственно)
- **Отключение номеров строк**: `.codemirror-no-lines`

Просто примените нужный класс к атрибуту `class` виджета в `admin.py`. По аналогии можно создавать свои классы
для своих настройек.

## Как добавить новый язык (например, jinja2 или xml)

1.  **Добавить зависимость**: Откройте `frontend-assembly/package.json` и добавьте в `devDependencies` новый языковой пакет. Версию выбирайте близкую к другим пакетам `@codemirror/lang-*`.

    ```json
    // package.json
    ...
    "@codemirror/lang-json": "6.0.1",
    "@codemirror/lang-xml": "6.1.0", // <-- Новая строка для добавления xml
    "@codemirror/language": "6.12.3",
    ...
    ```

2.  **Обновить скрипт сборки**: Откройте `frontend-assembly/build-codemirror6.sh` и внесите два изменения в секцию `cat > "$WORK_DIR/src/editor.js" <<'EOF'`:
    -   Добавьте импорт:
        ```javascript
        import { xml } from '@codemirror/lang-xml';
        ```
    -   Добавьте условие для его использования:
        ```javascript
        } else if (language === 'xml') {
          extensions.unshift(xml());
        }
        ```

3.  **Пересобрать бандл**:
    ```bash
    cd frontend-assembly
    npm install  # Установит новый пакет и обновит package-lock.json
    bash build-codemirror6.sh # Пересоберет editor.js с поддержкой XML
    ```

4.  **Использовать в админке**: Теперь вы можете использовать `data-language="xml"` для любого поля.

## Обновление зависимостей

1.  **Проверить устаревшие пакеты**:
    ```bash
    cd frontend-assembly
    npm outdated
    ```
2.  **Обновить версии**: Аккуратно обновите номера версий в `package.json`.
3.  **Установить обновления и пересобрать**:
    ```bash
    npm install
    bash build-codemirror6.sh
    ```
4.  **Закоммитить изменения**: Добавьте в коммит обновленные `package.json`, `package-lock.json` и `public/static/codemirror/editor.js`.
