# Генерирование криптографической соли для OFFER_HASHIDS_SALT

**Дата и время проверки:** 2026-11-21 01:30
**Статус проверки:** сверено с `settings.py`, `.env` и `.env.example`, `TbOffer.save()`, командой `regenerate_offer_codes` и поведением hashids 1.3.1 (проверено запуском); сама команда на реальной базе не запускалась.

**Что в коде:** соль и длина читаются из `.env` в `lpon_site/lpon_site/settings.py` (`OFFER_HASHIDS_SALT`, `OFFER_HASHIDS_MIN_LENGTH`, по умолчанию 6). Код `TbOffer.s_offer_code` (`max_length=12`, уникальный) строится в `TbOffer.save()` из `pk` через `Hashids`. Если в `.env` соли нет, `settings.py` молча берёт значение по умолчанию `your-secret-salt-change-me`; на продакшене это опасно (в документе раньше не упоминалось).

## Для Development (локально)

Текущее значение в `.env`. Если база из dev будет перемещаться в продакшен, то соль не нужно будет заменять на уникальную для продакшена. А то все старые QR-коды перестанут работать.

> Спорно (решение владельца): это противоречит правилу ниже «Dev ≠ Staging ≠ Production». Нужно выбрать одно: либо соль общая и переезжает вместе с базой, либо у каждого окружения своя, а база из dev в прод не переносится.

Если все-таки нужно обновить соль, используйте Django custom command (см. ниже).

## Для Production (сервер)

**НИКОГДА** не используйте соль из примеров! Генерируйте новую для каждого окружения:

### Способ 1: Python (быстро)
```bash
python3 -c "import secrets; print(secrets.token_hex(16))"
```

Результат:
```
a7f3c82b9e1dea6b5c8f2e3d0a9b4c7f
```

Скопируйте и обновите в `.env` на сервере (это только пример формата: `token_hex` выдаёт строчные hex-символы, 32 штуки для 16 байт):
```
OFFER_HASHIDS_SALT=a7f3c82b9e1dea6b5c8f2e3d0a9b4c7f
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
| До 1 000      | 4          | `a1bC`       | Короткие; легче угадать (коллизий нет, см. ниже) |
| До 10 000     | 5          | `a1bCd`      | Хорошо для небольших каталогов        |
| До 100 000    | 6          | `a1bCdE`     | **РЕКОМЕНДУЕМО** для начала           |
| До 1 000 000  | 8          | `a1bCdEfG`   | Для больших каталогов                 |
| Более 1M      | 10         | `a1bCdEfGhI` | Очень большие каталоги                |

**Текущее значение:** `OFFER_HASHIDS_MIN_LENGTH=6` (оптимально)

Уточнение по проверке на hashids 1.3.1: коллизий у коротких кодов нет, кодирование взаимно однозначно (для 20 000 id при `min_length=4` получено 20 000 разных кодов). `min_length` только добавляет заполнение до нужной длины, поэтому он влияет на длину кода и сложность угадывания, а не на уникальность. Поле `TbOffer.s_offer_code` имеет `max_length=12`, значит `min_length` больше 12 ставить нельзя. Hashids не является криптостойкой защитой: это обратимое кодирование, секретность держится только на соли.

## Как увеличить при необходимости?

Если вырос каталог:

1. Обновите в `.env`:
   ```
   OFFER_HASHIDS_MIN_LENGTH=8
   ```

2. Перезагрузите приложение

3. **Старые коды перестанут декодироваться (устарело прежнее утверждение «останутся валидными»).** Проверено запуском: код, созданный при `min_length=6`, при `min_length=8` не декодируется (`decode` возвращает пустой результат). Поэтому после смены длины нужно перегенерировать коды командой `regenerate_offer_codes` (так же, как при смене соли) и учесть уже напечатанные QR-коды: они перестанут работать.

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

**ВНИМАНИЕ:** Используется только при смене OFFER_HASHIDS_SALT (или OFFER_HASHIDS_MIN_LENGTH) на production! Команда сохраняет коды прямым `update()`, минуя `TbOffer.save()` и историю цен. Режимы `--check` и `--fix-broken` выбираются флагами; без флагов запускается полное обновление.

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
