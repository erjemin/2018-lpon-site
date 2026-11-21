# Архитектура парсера и валидации данных

**Дата:** 2026-07-15  
**Последний обновленно:** 2026-07-15  
**Статус:** черновик; парсер, очередь и приложение `parser` в коде отсутствуют (план)  
**Дата и время проверки:** 2026-11-21 01:30  
**Статус проверки:** сверено с `models.py`, `constants.py`, `utils_validators.py`, `utils.py`, `admin.py`, `pyproject.toml`; не проверялись внешние библиотеки чтения Excel и сама схема очереди (их нет в проекте).

> Важно: всё, что в этом документе описано как «требуемая архитектура» (приложение `parser`, `ValidatorQueue`, Celery, Redis, signals, `skip_validation`), **план, в коде нет**. Celery, Redis и библиотек чтения Excel/CSV/HTML нет и в `pyproject.toml`. Документ `BACKGROUND-TASKS-CONCEPT.md` предлагает другой вариант (очередь целиком в Redis, без модели в БД); решение не принято, см. раздел «Примечания».

## Обзор проблемы

Система должна поддерживать импорт данных из различных источников:
- Excel/CSV файлы от продавцов и издателей
- Парсинг URL-страниц с каталогами
- Ручной ввод данных в админке
- Будущие API интеграции

**Основной вызов:** Валидация и обнаружение конфликтов (дубликаты, совпадения в синонимах) требует **пользовательского участия** для принятия решений. Нельзя просто блокировать или автоматически удалять/объединять данные.

## Текущее состояние (MVP)

### Модели и структура

```
┌─ TbSource (Excel, CSV, URL) ──┐
│  s_source_name                │
│  l_source_type (excel/csv/url/│
│     '??' = другое, SourceType)│
│  k_source_to_seller ──────────┼──► TbSeller
│  t_source_data (дата данных)  │
│  source_file (FilerFileField) │
│  s_source_url                 │
│  j_source_metadata (структура)│    (metadata описывает столбцы, вкладки и т.д.)
└─────────────────────────────────┘

TbSource ──(1:M, k_offer_to_source)──► TbOffer
TbOffer ──(FK)──► TbItem, TbLabel, TbArticle (опционально)
TbItem ──(M2M)──► TbArtist (k_item_to_artist), TbMusicStyle (k_item_to_style)
TbItem, TbArtist, TbLabel, TbMusicStyle, TbSeller ──(1:1)──► TbArticle
                                  (текст, SEO, slug, картинка)
TbOffer ◄── TbOfferHistory (история цены и количества)
```

Исправлено при сверке: источник связан не с `TbItem`, а с `TbOffer` (`TbOffer.k_offer_to_source`); артисты и стили связаны с `TbItem` через M2M, а лейбл с `TbOffer` (`k_offer_to_label`).

### Валидация (текущая реализация)

**Файл:** `lpon_site/frontend/utils_validators.py`

**Функция:** `validate_for_duplicates()`
- Проверяет основное поле (s_label, s_artist и т.д.)
- Проверяет синонимы в j_*_metadata[SYN_EN] (константа `KEY_SYNONYM_EN = 'SYN_EN'` из `lpon_site/constants.py`)
- Возвращает **словарь** (не список!) вида `{MODEL: имя_модели, MATCH_TYPE: ValidateMatchType, MATCH_VALUE: QuerySet}`; при отсутствии конфликтов в словаре только ключ `MODEL`. Ключи заданы константами `VALIDATE_KEY__MODEL`, `VALIDATE_KEY__MATCH_TYPE`, `VALIDATE_KEY__VALUE`. Проверка идёт по порядку и останавливается на первом найденном типе.

**Типы совпадений** (`ValidateMatchType`, `IntEnum` в `lpon_site/constants.py`):
1. **IS_DUPLICATE** (1) — точное совпадение основного поля (s_label == s_label); в старой редакции документа назван EXACT_MATCH
2. **FIND_IN_SYNONYM** (2) — основное поле текущей записи найдено в синонимах другой
3. **EXACT_SYNONYM_MATCH** (3) — синонимы текущей записи совпадают с синонимами другой
4. **PARTIAL_MATCH** (4) — частичное совпадение по словам (в документе раньше не упоминался); не блокирует, в `save()` только логируется
5. **PARTIAL_MATCH__RISK_SHORT_WORDS** (5) — то же по коротким словам (короче `MIN_SYNONYM_WORD_LENGTH = 4`), высокий риск ложных срабатываний

**Где вызывается:**
- Есть, в админке: формы в `admin.py` вызывают `validate_entity_for_admin_form()` из `clean()`; ошибка показывается пользователю (проверку можно обойти GET-параметром `ignore_validate`)
- Есть, в моделях: `save()` у `TbMusicStyle`, `TbArtist`, `TbItem`, `TbLabel` вызывает `validate_and_raise_for_duplicates()` и бросает `ValidationError` при типах 1-3. У `TbSeller` вызова нет
- Нет, в парсере: парсера ещё нет

Примечание: в `TbItem` поле метаданных называется `j_item_metadata` и оно общее для ключей характеристик и синонимов; в `TbLabel` и `TbArtist` это `j_label_metadata` и `j_artist_metadata`, в `TbMusicStyle` `j_style_metadata`.

### Конфликты синонимов (TODO)

**Сценарий 1: FIND_IN_SYNONYM**
```python
# В БД уже есть
TbArtist(pk=1, s_artist="Beatles", j_artist_metadata={"SYN_EN": ["The Beatles", "Beatles"]})

# Парсер хочет создать
TbArtist(pk=None, s_artist="The Beatles", j_artist_metadata={"SYN_EN": []})

# Валидатор: основное поле "The Beatles" найдено в синонимах существующей записи!
# Текущее поведение: ValidationError (блокировка)
# TODO: Отправить в очередь, ждать решения админа
```

**Сценарий 2: EXACT_SYNONYM_MATCH**
```python
# В БД
TbLabel(pk=1, s_label="Sony", j_label_metadata={"SYN_EN": ["Sony Records", "Sony Music"]})

# Парсер хочет
TbLabel(pk=None, s_label="Sony Music", j_label_metadata={"SYN_EN": ["Sony Records", "Sony Music"]})

# Валидатор: синонимы совпадают!
# Текущее поведение: ValidationError
# TODO: Отправить в очередь, ждать решения админа
```

## Архитектура парсера (требуемая)

**План, в коде нет.** Нет приложения `parser`, модели `ValidatorQueue`, Celery, Redis, signals. Ниже схема целевой архитектуры.

Соглашение о метаданных (идея, не принято окончательно): ключи метаданных кассет и т.п. берутся из реестра `config/metadata-toml/default.toml` (см. `lpon--metadata-config.md`, `00_START_HERE.md`), а парсер приводит названия из источников к ключам реестра через `aliases` значений. Ключ синонимов названий сущностей (`SYN_EN`) в этот реестр не входит, он остаётся в `j_*_metadata` моделей-справочников.

### Компоненты

```
┌──────────────────────────────────────────────────────────────┐
│                      DJANGO ADMIN                            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Приложение "Parser" (план, в коде нет)                 │ │
│  │ ┌─────────────────────────────────────────────────────┐ │ │
│  │ │ Очередь валидации (ValidatorQueue model)            │ │ │
│  │ │ Содержит: состояние экземпляра, ошибки, решение... │ │ │
│  │ └─────────────────────────────────────────────────────┘ │ │
│  │ ┌─────────────────────────────────────────────────────┐ │ │
│  │ │ Admin list view + inline actions                   │ │ │
│  │ │ - Просмотр конфликта (дубликаты)                  │ │ │
│  │ │ - Кнопка "Создать новую запись"                   │ │ │
│  │ │ - Кнопка "Объединить/обновить синонимы"           │ │ │
│  │ │ - Кнопка "Пропустить"                             │ │ │
│  │ └─────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    БРОКЕР ОЧЕРЕДИ (Redis)                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ parser:validation:pending (ZSET)                        │ │
│  │ parser:validation:{queue_id}:data (STRING/JSON)         │ │
│  │ parser:validation:{queue_id}:duplicates (JSON)          │ │
│  │ parser:validation:{queue_id}:solution (STRING)          │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                      ПАРСЕР (Celery Task)                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ parse_excel() / parse_csv() / parse_url()              │ │
│  │                                                          │ │
│  │ Логика:                                                 │ │
│  │ 1. Читать источник (файл/URL)                          │ │
│  │ 2. Нормализовать данные                                │ │
│  │ 3. Валидировать через validate_for_duplicates()       │ │
│  │    (результат: словарь, а не список)                 │ │
│  │ 4. Если конфликт → создать запись в ValidatorQueue   │ │
│  │ 5. Если OK → создать модель (TbLabel, TbArtist и т.д.)│ │
│  │    (save() сам повторит проверку дубликатов)         │ │
│  │ 6. Отправить уведомление админу (Redis/сигнал)        │ │
│  │ 7. Продолжить обработку следующей строки              │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│              СИГНАЛЫ И УВЕДОМЛЕНИЯ (Django signals)          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ post_validate_conflict → Redis уведомление админу      │ │
│  │ post_admin_decision → Обновление очереди              │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Таблица ValidatorQueue (новая модель; план, в коде нет)

```python
class ValidatorQueue(models.Model):
    """
    Очередь конфликтов, требующих решения админа.
    """
    class Status(TextChoices):
        PENDING = 'pending'      # Ждёт решения админа
        APPROVED = 'approved'    # Админ одобрил - выполнить действие
        REJECTED = 'rejected'    # Админ отклонил
        MERGED = 'merged'        # Данные объединены с существующей записью
        SKIPPED = 'skipped'      # Заметка: пропущено

    class ConflictType(TextChoices):
        FIND_IN_SYNONYM = 'find_in_synonym'          # Основное поле в синонимах
        EXACT_SYNONYM_MATCH = 'exact_synonym_match'  # Синонимы совпадают
        OTHER = 'other'

    # Основные поля
    id = BigAutoField(primary_key=True)
    k_source = ForeignKey(TbSource, ...)            # Откуда пришли данные
    # ConflictType здесь неполон: в коде также есть IS_DUPLICATE (точный дубликат), PARTIAL_MATCH и
    # PARTIAL_MATCH__RISK_SHORT_WORDS (см. ValidateMatchType); состав очереди нужно согласовать с ним
    l_conflict_type = CharField(choices=ConflictType)

    # Данные для конфликта
    l_model_type = CharField()                       # Какая модель (TbLabel, TbArtist и т.д.)
    model_pk = IntegerField(null=True)               # PK существующей записи в БД
    j_incoming_data = JSONField()                    # Данные от парсера (весь объект)
    # Результат validate_for_duplicates(): значение MATCH_VALUE там QuerySet, в JSON его нужно
    # предварительно превратить в список pk (иначе не сериализуется)
    j_duplicates = JSONField()

    # Решение админа
    l_status = CharField(choices=Status, default=Status.PENDING)
    s_admin_decision = CharField()                   # 'create_new' / 'merge' / 'skip'
    s_admin_notes = TextField()                      # Комментарий админа

    # Сервисные поля
    t_created = DateTimeField(auto_now_add=True)
    t_resolved = DateTimeField(null=True)
    k_resolved_by = ForeignKey(User, null=True)     # Какой админ принял решение

    class Meta:
        verbose_name = 'Конфликт валидации'
        ordering = ['-t_created']
        indexes = [
            Index(fields=['l_status', '-t_created']),
            Index(fields=['k_source', 'l_status']),
        ]
```

## Процесс работы

### Фаза 1: Импорт данных (парсер)

```python
# tasks.py (Celery) -- план, в коде нет; Celery и Redis не входят в зависимости pyproject.toml
@celery.task
def parse_and_validate_excel(source_id: int):
    """
    1. Читает Excel из TbSource
    2. Парсит строки
    3. Валидирует каждую запись
    4. Создаёт или отправляет в очередь
    """
    source = TbSource.objects.get(pk=source_id)
    
    for row in read_excel(source.source_file):
        try:
            # Нормализуем данные
            artist_data = {
                's_artist': row['Artist Name'],
                'j_artist_metadata': {'SYN_EN': [row.get('Aliases', '')]}
            }
            
            # Валидируем
            # duplicates -- словарь: пустой по смыслу, если в нём нет ключа MATCH_TYPE
            duplicates = validate_for_duplicates(
                model_class=TbArtist,
                instance_pk=None,
                main_field_value=artist_data['s_artist'],
                metadata_dict=artist_data['j_artist_metadata'],
                main_field_name='s_artist',
                metadata_field_name='j_artist_metadata',
            )
            
            if duplicates.get(VALIDATE_KEY__MATCH_TYPE):
                # КОНФЛИКТ! Отправляем в очередь
                queue_item = ValidatorQueue.objects.create(
                    k_source=source,
                    l_model_type='TbArtist',
                    l_conflict_type=duplicates[VALIDATE_KEY__MATCH_TYPE],
                    j_incoming_data=artist_data,
                    j_duplicates=[d.pk for d in duplicates[VALIDATE_KEY__VALUE]],
                )
                # Отправляем сигнал (Redis уведомление админу)
                send_to_redis_queue('parser:conflicts:new', {
                    'queue_id': queue_item.id,
                    'model': 'TbArtist',
                    'conflict': duplicates[VALIDATE_KEY__MATCH_TYPE],
                    'data': artist_data,
                })
            else:
                # Нет конфликта - создаём запись (create() вызывает save(), а он повторно проверяет дубликаты
                # и сам добавляет название в SYN_EN)
                artist = TbArtist.objects.create(**artist_data)
                logger.info(f"Artist created: {artist.id}")
                
        except Exception as e:
            logger.error(f"Parse error in row {row}: {e}")
            continue
```

### Фаза 2: Админка (приложение Parser)

```python
# admin.py (новое приложение parser; план, в коде нет)
@admin.register(ValidatorQueue)
class ValidatorQueueAdmin(admin.ModelAdmin):
    """
    Админка для работы с очередью конфликтов.
    """
    list_display = [
        'id', 'l_model_type', 'l_conflict_type', 'l_status',
        'source_link', 'duplicates_summary', 't_created'
    ]
    list_filter = ['l_status', 'l_conflict_type', 'l_model_type', 't_created']
    readonly_fields = ['j_incoming_data', 'j_duplicates', 'k_source']
    
    fieldsets = (
        ('Конфликт', {
            'fields': ['l_model_type', 'l_conflict_type', 'k_source', 'model_pk']
        }),
        ('Входящие данные', {
            'fields': ['j_incoming_data']
        }),
        ('Найденные дубликаты', {
            'fields': ['j_duplicates']
        }),
        ('Решение админа', {
            'fields': ['s_admin_decision', 's_admin_notes', 'l_status']
        }),
    )
    
    actions = ['action_create_new', 'action_merge_synonyms', 'action_skip']
    
    def action_create_new(self, request, queryset):
        """Админ решил: создать новую запись, игнорируя дубликаты"""
        for item in queryset:
            model_class = get_model_class(item.l_model_type)
            instance = model_class(**item.j_incoming_data)
            instance.save(skip_validation=True)  # Пропускаем валидацию (параметра skip_validation в коде нет)
            item.l_status = ValidatorQueue.Status.APPROVED
            item.s_admin_decision = 'create_new'
            item.k_resolved_by = request.user
            item.t_resolved = now()
            item.save()
```

### Фаза 3: Обработка решения админа

```python
# signals.py (новое приложение parser; план, в коде нет)
# Схематично: `j_*_metadata` здесь означает j_artist_metadata / j_label_metadata / j_style_metadata по модели

@receiver(post_save, sender=ValidatorQueue)
def on_admin_decision(sender, instance, created=False, **kwargs):
    """
    Обработать решение админа и применить действие.
    """
    if created or instance.l_status != ValidatorQueue.Status.APPROVED:
        return
    
    if instance.s_admin_decision == 'create_new':
        # Админ одобрил создание новой записи
        model_class = get_model_class(instance.l_model_type)
        model_instance = model_class(**instance.j_incoming_data)
        model_instance.save(skip_validation=True)
        
    elif instance.s_admin_decision == 'merge':
        # Админ решил объединить (добавить синонимы, и т.д.)
        existing_pk = instance.model_pk
        incoming_data = instance.j_incoming_data
        
        model_class = get_model_class(instance.l_model_type)
        existing = model_class.objects.get(pk=existing_pk)
        
        # Добавляем синонимы из входящих данных
        existing_meta = existing.j_*_metadata or {}
        existing_synonyms = existing_meta.get(KEY_SYNONYM_EN, [])
        incoming_synonyms = incoming_data.get('j_*_metadata', {}).get(KEY_SYNONYM_EN, [])
        
        # Объединяем и сохраняем
        existing_meta[KEY_SYNONYM_EN] = list(set(existing_synonyms + incoming_synonyms))
        existing.j_*_metadata = existing_meta
        existing.save(skip_validation=True)
```

## Файлы для создания

### 1. Новое приложение `parser` (план, в коде нет)

Каталог приложений: `lpon_site/` (рядом с `frontend/`), настройки в `lpon_site/lpon_site/settings.py`.

```
lpon_site/parser/
├── __init__.py
├── models.py           # ValidatorQueue
├── admin.py            # ValidatorQueueAdmin + actions
├── signals.py          # Обработка решений админа
├── tasks.py            # Celery tasks для парсинга
├── apps.py
└── migrations/
```

### 2. Изменения в existing коде

**settings.py:**
```python
INSTALLED_APPS = [
    ...,
    'parser',  # Новое приложение
]

# Конфигурация Celery (в проекте её нет; в Docker-файлах сервиса Redis тоже нет; пакеты celery и redis
# в pyproject.toml не добавлены)
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
```

**frontend/models.py:**
```python
# В методе save() моделей (TbMusicStyle, TbArtist, TbItem, TbLabel) добавить параметр
# (сейчас они вызывают validate_and_raise_for_duplicates безусловно)
def save(self, *args, skip_validation=False, **kwargs):
    if not skip_validation:
        # Стандартная валидация
        validate_and_raise_for_duplicates(...)
    super().save(*args, **kwargs)
```

**frontend/utils.py:**
```python
# Добавить функцию отправки в Redis (в utils.py её нет; есть только комментарий-TODO в
# create_or_get_related_article())
def send_to_redis_queue(queue_name: str, data: dict):
    """Отправить уведомление в Redis"""
    import redis
    import json
    
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.lpush(queue_name, json.dumps({
        'timestamp': datetime.now().isoformat(),
        **data
    }))
```

## TODO задачи

- [ ] Создать приложение `parser` с моделью `ValidatorQueue`
- [ ] Реализовать админку `ValidatorQueueAdmin` с actions
- [ ] Выбрать и добавить зависимости (celery, redis, openpyxl/pandas и т.п.; сейчас в pyproject.toml их нет)
- [ ] Написать Celery tasks для парсинга Excel/CSV
- [ ] Добавить обработку решений админа через signals
- [ ] Интегрировать Redis уведомления админу
- [ ] Добавить параметр `skip_validation` в save() методы
- [ ] Написать тесты для парсера и валидации
- [ ] Документация для парсера (как использовать)

## Примечания

1. **Redis vs БД для очереди?** → Используем БД (ValidatorQueue модель) как основное хранилище, Redis только для уведомлений админу в реальном времени. **Спорно:** `BACKGROUND-TASKS-CONCEPT.md` предлагает противоположное (до одобрения данные только в Redis); решение за владельцем проекта
2. **Async валидация?** → Парсер работает в Celery, валидация синхронна внутри задачи
3. **Миграция истории?** → Поле `t_history_created` в `TbOfferHistory` редактируемое (`default=timezone.now`, не `auto_now_add`), так что исторические данные можно вносить вручную. Проверено по коду.
4. **Конфликты в админке?** → План: `ValidatorQueue` блокирует парсер от создания дубликатов, админ сам решает что делать. Сейчас вместо очереди парсер получил бы `ValidationError` из `save()`.

## Ссылки на существующий код

- Валидаторы: `lpon_site/frontend/utils_validators.py`
- Модели: `lpon_site/frontend/models.py` (методы save() с проверкой дубликатов: TbArtist, TbItem, TbLabel, TbMusicStyle; у TbSeller проверки нет)
- Константы: `lpon_site/lpon_site/constants.py` (`KEY_SYNONYM_EN`, `ValidateMatchType`, `VALIDATE_KEY__*`, `SourceType`, `MIN_SYNONYM_WORD_LENGTH`)
- TODO про Redis: `lpon_site/frontend/utils.py` (в функции `create_or_get_related_article()`)
- TODO про историю: `lpon_site/frontend/models.py` (в `TbOffer.save()`, про `j_history_metadata`)
