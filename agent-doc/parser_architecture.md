# Архитектура парсера и валидации данных

**Дата:** 2026-07-15  
**Последний обновленно:** 2026-07-15  
**Статус:** В разработке ✏️

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
│  l_source_type (excel/csv/url)│
│  k_source_to_seller ──────────┼──► TbSeller
│  source_file (FilerFileField) │
│  s_source_url                 │
│  j_source_metadata (struktura)│    (metadata описывает столбцы, вкладки и т.д.)
└─────────────────────────────────┘

TbOffer ◄──┐
           │
TbSource ──┴─► TbItem ──────► TbArticle (текст, SEO, slug, картинка)
           │
           └──► TbLabel, TbArtist, TbMusicStyle
                (все через TbArticle)
```

### Валидация (текущая реализация)

**Файл:** `lpon_site/frontend/utils_validators.py`

**Функция:** `validate_for_duplicates()`
- Проверяет основное поле (s_label, s_artist и т.д.)
- Проверяет синонимы в j_*_metadata[SYN_EN]
- Возвращает список найденных дубликатов с типом совпадения

**Типы совпадений:**
1. **EXACT_MATCH** — точное совпадение основного поля (s_label == s_label)
2. **FIND_IN_SYNONYM** — основное поле текущей записи найдено в синонимах другой
3. **EXACT_SYNONYM_MATCH** — синонимы текущей записи совпадают с синонимами другой

**Где вызывается:**
- ✅ В админке: `admin.py` (переопределение `clean()` формы) → показывает ошибку пользователю
- ✅ В моделях: `save()` методы → выбрасывают `ValidationError`
- ❌ В парсере: **НЕТ** (парсер еще не создан)

### Конфликты синонимов (TODO)

**Сценарий 1: FIND_IN_SYNONYM**
```python
# В БД уже есть
Artist(pk=1, s_artist="Beatles", j_artist_metadata={"SYN_EN": ["The Beatles", "Beatles"]})

# Парсер хочет создать
Artist(pk=None, s_artist="The Beatles", j_artist_metadata={"SYN_EN": []})

# Валидатор: основное поле "The Beatles" найдено в синонимах существующей записи!
# Текущее поведение: ValidationError (блокировка)
# TODO: Отправить в очередь, ждать решения админа
```

**Сценарий 2: EXACT_SYNONYM_MATCH**
```python
# В БД
Label(pk=1, s_label="Sony", j_label_metadata={"SYN_EN": ["Sony Records", "Sony Music"]})

# Парсер хочет
Label(pk=None, s_label="Sony Music", j_label_metadata={"SYN_EN": ["Sony Records", "Sony Music"]})

# Валидатор: синонимы совпадают!
# Текущее поведение: ValidationError
# TODO: Отправить в очередь, ждать решения админа
```

## Архитектура парсера (требуемая)

### Компоненты

```
┌──────────────────────────────────────────────────────────────┐
│                      DJANGO ADMIN                            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Приложение "Parser" (новое приложение)                 │ │
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
│  │ 4. Если конфликт → создать запись в ValidatorQueue   │ │
│  │ 5. Если OK → создать модель (TbLabel, TbArtist и т.д.)│ │
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

### Таблица ValidatorQueue (новая модель)

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
    l_conflict_type = CharField(choices=ConflictType)

    # Данные для конфликта
    l_model_type = CharField()                       # Какая модель (TbLabel, TbArtist и т.д.)
    model_pk = IntegerField(null=True)               # PK существующей записи в БД
    j_incoming_data = JSONField()                    # Данные от парсера (весь объект)
    j_duplicates = JSONField()                       # Результат validate_for_duplicates()

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
# tasks.py (Celery)
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
            duplicates = validate_for_duplicates(
                model_class=TbArtist,
                instance_pk=None,
                main_field_value=artist_data['s_artist'],
                metadata_dict=artist_data['j_artist_metadata'],
                main_field_name='s_artist',
                metadata_field_name='j_artist_metadata',
            )
            
            if duplicates:
                # КОНФЛИКТ! Отправляем в очередь
                queue_item = ValidatorQueue.objects.create(
                    k_source=source,
                    l_model_type='TbArtist',
                    l_conflict_type=duplicates[0][VALIDATE_KEY__MATCH_TYPE],
                    j_incoming_data=artist_data,
                    j_duplicates=duplicates,
                )
                # Отправляем сигнал (Redis уведомление админу)
                send_to_redis_queue('parser:conflicts:new', {
                    'queue_id': queue_item.id,
                    'model': 'TbArtist',
                    'conflict': duplicates[0]['match_type'],
                    'data': artist_data,
                })
            else:
                # Нет конфликта - создаём запись
                artist = TbArtist.objects.create(**artist_data)
                logger.info(f"Artist created: {artist.id}")
                
        except Exception as e:
            logger.error(f"Parse error in row {row}: {e}")
            continue
```

### Фаза 2: Админка (приложение Parser)

```python
# admin.py (новое приложение parser)
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
            instance.save(skip_validation=True)  # Пропускаем валидацию
            item.l_status = ValidatorQueue.Status.APPROVED
            item.s_admin_decision = 'create_new'
            item.k_resolved_by = request.user
            item.t_resolved = now()
            item.save()
```

### Фаза 3: Обработка решения админа

```python
# signals.py (новое приложение parser)

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

### 1. Новое приложение `parser`

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

# Конфигурация Celery (если еще нет)
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
```

**frontend/models.py:**
```python
# В методе save() моделей добавить параметр
def save(self, *args, skip_validation=False, **kwargs):
    if not skip_validation:
        # Стандартная валидация
        validate_and_raise_for_duplicates(...)
    super().save(*args, **kwargs)
```

**frontend/utils.py:**
```python
# Добавить функцию отправки в Redis
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
- [ ] Написать Celery tasks для парсинга Excel/CSV
- [ ] Добавить обработку решений админа через signals
- [ ] Интегрировать Redis уведомления админу
- [ ] Добавить параметр `skip_validation` в save() методы
- [ ] Написать тесты для парсера и валидации
- [ ] Документация для парсера (как использовать)

## Примечания

1. **Redis vs БД для очереди?** → Используем БД (ValidatorQueue модель) как основное хранилище, Redis только для уведомлений админу в реальном времени
2. **Async валидация?** → Парсер работает в Celery, валидация синхронна внутри задачи
3. **Миграция истории?** → Поле `t_history_created` уже `editable=True` в TbOfferHistory, так что админ может вручную добавлять исторические данные
4. **Конфликты в админке?** → `ValidatorQueue` блокирует парсер от создания дубликатов. Админ сам решает что делать.

## Ссылки на существующий код

- Валидаторы: `lpon_site/frontend/utils_validators.py`
- Модели: `lpon_site/frontend/models.py` (методы save() для TbArtist, TbItem, TbLabel, TbSeller, TbMusicStyle)
- TODO про Redis: `lpon_site/frontend/utils.py` (в функции `create_or_get_related_article()`)
- TODO про историю: `lpon_site/frontend/models.py` (в `TbOffer.save()`)
