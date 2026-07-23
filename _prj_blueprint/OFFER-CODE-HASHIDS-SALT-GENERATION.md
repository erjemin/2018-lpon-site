# Генерирование криптографической соли для OFFER_HASHIDS_SALT

## Для Development (локально)

Текущее значение в `.env`. Если база из dev будет перемещаться в продакшен, то соль не нужно будет заменять на уникальную для продакшена. А то все старые QR-коды перестанут работать.

Если все-таки нужно обновить соль, используйте Django custom command (см. ниже).

## Для Production (сервер)

**НИКОГДА** не используйте соль из примеров! Генерируйте новую для каждого окружения:

### Способ 1: Python (быстро)
```bash
python3 -c "import secrets; print(secrets.token_hex(16))"
```

Результат:
```
a7f3c82b9e1dEa6b5c8f2e3d0a9b4c7f
```

Скопируйте и обновите в `.env` на сервере:
```
OFFER_HASHIDS_SALT=a7f3c82b9e1dEa6b5c8f2e3d0a9b4c7f
```

### Способ 2: Linux/Mac (встроенный)
```bash
openssl rand -hex 16
```

### Способ 3: Более надежная соль (32 байта вместо 16)
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Результат (64 символа, очень стойко):
```
26aebe8af9efe7c5f81c64cb18846318cc81a83eaf15aedb7f4b8a80990c9676
```

## Важные правила

1. **Уникальная для каждого окружения** (каждой реализации LPON под каждого сейлера)
   - Dev ≠ Staging ≠ Production
   - Разные соли = разные коды для одного ID

2. **Никогда не меняйте в production!**
   - Если поменяете соль → старые коды перестанут работать
   - Существующие QR-коды станут невалидными
   - Существующие ID в базе не будут декодироваться
   - **Если все же нужно изменить:** используйте custom command `regenerate_offer_codes` (см. ниже)

3. **Хранить в .env (не в репозитории)**
   - `.env` в .gitignore ✓
   - `.env.example` содержит шаблон ✓

## Проверка качества соли

```python
import secrets

# Хорошая соль (минимум 32 символа, hex-формат)
salt = secrets.token_hex(16)  # ✓
salt = secrets.token_hex(32)  # ✓✓ еще лучше

# Плохие соли
salt = "my-password"          # ✗ слишком короткая
salt = "12345678"             # ✗ предсказуемая
salt = "qwerty123"            # ✗ слабая энтропия
```

## Параметры OFFER_HASHIDS_MIN_LENGTH

| Кол-во оферов | min_length | Пример       | Примечание                            |
|---------------|------------|--------------|---------------------------------------|
| До 1 000      | 4          | `a1bC`       | Слишком короткие, может быть коллизии |
| До 10 000     | 5          | `a1bCd`      | Хорошо для небольших каталогов        |
| До 100 000    | 6          | `a1bCdE`     | **РЕКОМЕНДУЕМО** для начала           |
| До 1 000 000  | 8          | `a1bCdEfG`   | Для больших каталогов                 |
| Более 1M      | 10         | `a1bCdEfGhI` | Очень большие каталоги                |

**Текущее значение:** `OFFER_HASHIDS_MIN_LENGTH=6` (оптимально)

## Как увеличить при необходимости?

Если вырос каталог:

1. Обновите в `.env`:
   ```
   OFFER_HASHIDS_MIN_LENGTH=8
   ```

2. Перезагрузите приложение

3. **Старые коды останутся валидными!** (hashids декодирует любой код независимо от min_length)

4. Новые офферы будут кодироваться с длиной 8

## Django Custom Command: `regenerate_offer_codes`

**Расположение:** `lpon_site/frontend/management/commands/regenerate_offer_codes.py`

Используется для проверки, восстановления и перегенерации s_offer_code офферов.

### Три режима работы

#### 1. Проверка кодов (режим `--check`)

Декодирует все коды обратно в ID и проверяет корректность:

```bash
# Быстрая проверка
cd lpon_site && poetry run python manage.py regenerate_offer_codes --check

# С подробным выводом
cd lpon_site && poetry run python manage.py regenerate_offer_codes --check --verbose
```

#### 2. Исправление некорректных кодов (режим `--fix-broken`)

Обновляет только коды, которые не декодируются правильно:

```bash
# Пробный запуск (ничего не сохранит)
cd lpon_site && poetry run python manage.py regenerate_offer_codes --fix-broken --dry-run

# Реальное исправление
cd lpon_site && poetry run python manage.py regenerate_offer_codes --fix-broken
```

**Использование:** Когда некоторые коды повреждены или закодированы неправильно (например, после сбоя БД).

#### 3. Полное обновление всех кодов (по умолчанию)

Перегенерирует ВСЕ коды на основе текущего OFFER_HASHIDS_SALT:

```bash
# Пробный запуск
cd lpon_site && poetry run python manage.py regenerate_offer_codes --dry-run

# Реальное обновление
cd lpon_site && poetry run python manage.py regenerate_offer_codes
```

**ВНИМАНИЕ:** Используется только при смене OFFER_HASHIDS_SALT на production!

### Примеры использования

**Сценарий 1: Проверка целостности после сбоя**
```bash
# Сначала проверяем что сломалось
cd lpon_site && poetry run python manage.py regenerate_offer_codes --check

# Если есть некорректные коды - исправляем
cd lpon_site && poetry run python manage.py regenerate_offer_codes --fix-broken
```

**Сценарий 2: Миграция на новый сервер с новой солью**
```bash
# 1. Обновляем .env с новой солью
OFFER_HASHIDS_SALT=новая_соль_из_secrets

# 2. Перегенерируем все коды (пробный запуск сначала)
cd lpon_site && poetry run python manage.py regenerate_offer_codes --dry-run

# 3. Если хорошо - реальное обновление
cd lpon_site && poetry run python manage.py regenerate_offer_codes

# 4. Проверяем что все работает
cd lpon_site && poetry run python manage.py regenerate_offer_codes --check
```

### Опции команды

```
--check              Проверить корректность всех кодов (декодировать обратно в id)
--fix-broken         Обновить только коды которые не декодируются правильно
--dry-run            Показать что будет изменено, но не сохранять
--verbose            Показывать подробный прогресс для каждого оффера
```

Использование:

```bash
# Проверка
python manage.py regenerate_offer_codes --check

# Исправление
python manage.py regenerate_offer_codes --fix-broken

# Полное обновление (при смене соли)
python manage.py regenerate_offer_codes
```
