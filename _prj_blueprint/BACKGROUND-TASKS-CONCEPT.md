## ПОТОК ДАННЫХ (чистая архитектура) ДРАФТ

```text
1️⃣ ИСТОЧНИК ДОБАВЛЕН
   ├─ Пользователь добавляет новый источник (TbSource)
   └─ Создается задание в Redis: `job:parse_source:123`

2️⃣ ФОНОВЫЙ ВОРКЕР (Celery/APScheduler)
   ├─ Видит задание в Redis
   ├─ Начинает парсить (не пишет в prod БД!)
   ├─ Получает: Style["Rock"], Artist["The Beatles"], Label["Sony"]
   ├─ Кидает КАЖДЫЙ в Redis как **виртуальный объект**
   │  └─ `pending:style:1` → {"title": "Rock", "source": "Discogs", ...}
   │  └─ `pending:artist:2` → {"title": "The Beatles", "source": "MusicBrainz", ...}
   └─ Смотрит: есть ли в product БД? Если НЕТ → в Redis очередь

3️⃣ АДМИНКА ДЖАНГО (виртуальная вкладка "Ожидающие задачи")
   ├─ Админ видит в Redis список
   ├─ Видит: Rock (похож на existing Rock?), The Beatles (новый?), Sony (уже есть)
   ├─ **ПОТЫКАЛ**:
   │  ├─ Rock → "Мержить с existing Rock" → задание в Redis
   │  ├─ The Beatles → "Одобрить" → задание в Redis
   │  └─ Sony → "Пропустить" → удалить из Redis
   └─ Каждое действие → новое задание в Redis

4️⃣ ФОНОВЫЙ ВОРКЕР II (финальный штрих)
   ├─ Видит задание: "merge Rock с ID:5"
   │  └─ Делает: добавляет синонимы, сохраняет в product БД
   ├─ Видит задание: "create The Beatles"
   │  └─ Пишет вреальную БД → TbArtist создана
   └─ После каждого успеха → **удалить из Redis**

5️⃣ ПРОДАКТ БД (в итоге)
   └─ Только валидные, одобренные, обработанные данные
   └─ No garbage, ID подряд
```

# Архитектура

```text
Парсер                  Redis (очередь)         Админка                 Воркер              БД
   │                          │                    │                       │                  │
   ├──parse_source───────────→│                    │                       │                  │
   │                          │                    │                       │                  │
   │                  ┌─pending:style:1            │                       │                  │
   │                  ├─pending:artist:1   ←─ Админ видит видит здесь      │                  │
   │                  └─pending:label:1     потыкает кнопки                │                  │
   │                          │                    │                       │                  │
   │                          │        "merge Rock"│                       │                  │
   │                          │←───────────────────│ →─ job:merge:1 ──────→│                  │
   │                          │                    │                       ├─→ UPDATE Style  →│
   │                          │                    │                       │  delete from Redis
   │                          │        "create Beatles"                    │                  │
   │                          │←──────────────────→─ job:create:2 ────────→│                  │
   │                          │                    │                       ├─→ INSERT Artist ─│
   │                          │                    │                       │  delete from Redis
   │                          │                    │                       │                  │
   └───────────────────────────────────────────────────────────────────────────────────────────────────→
```

---

## КЛЮЧЕВЫЕ ПРИНЦИПЫ

- **Чистая БД**: product база получает только одобренные, валидные данные
- **ID подряд**: мнимизирукет удаления (delete), INSERT данных парсинга только при одобрении
- **Single Source of Truth**: пока не одобрено администратором → данные ТОЛЬКО в Redis
- **Асинхронность**: парсер не блокирует админку, админка не блокирует парсер
- **Откат дешевый**: удалить из Redis дешевле, чем восстанавливать из БД

---

## КОМПОНЕНТЫ REDIS ОЧЕРЕДИ

```
tasks:pending        ← Очередь неодобренных задач (парсер → сюда)
  └─ pending:style:1
  └─ pending:artist:2
  └─ pending:label:3

tasks:approved       ← Очередь одобренных (админ → сюда)
  └─ {type: 'create', id: 'style:1', data: {...}}
  └─ {type: 'merge', id: 'artist:1', merge_with_id: 5}
  └─ {type: 'skip', id: 'label:3'}

tasks:completed      ← История завершённых (воркер → сюда)
tasks:failed         ← История ошибок (воркер → сюда)
```

---

## ДЕЙСТВИЯ В АДМИНКЕ (виртуальная вкладка)

Админ видит Redis очередь и кликает:

1. **"✅ Одобрить"** → `job:create:style:1` → Воркер пишет в БД
2. **"🔗 Мержить с ID:5"** → `job:merge:style:1:with:5` → Воркер обновляет existing
3. **"❌ Пропустить"** → Удалить из Redis (ничего не пишется)
4. **"📝 Отредактировать"** → Изменить JSON в оптимистичной форме → сохранить как новое задание

---

## ПАРСЕР (упрощённо)

```python
def parse_source(source_id):
    source = TbSource.objects.get(id=source_id)
    
    for style_name in PARSED_STYLES:
        # 1. Ищем существующий стиль или по названию или по алиасам
        existing = TbMusicStyle.objects.filter(
            Q(s_style_name__iexact=style_name) |
            Q(j_style_synonyms__contains=style_name)
        ).first()
        
        if existing:
            # ✅ МАТЧИНГ СРАБОТАЛ → пишем сразу в БД
            if style_name not in existing.j_style_synonyms:
                existing.j_style_synonyms.append(style_name)  # Запомнили синоним!
                existing.save()
        else:
            # ❌ НОВЫЙ СТИЛЬ → в Redis очередь на одобрение
            redis.lpush('tasks:pending', {...})
    
    # В метаданных источника сохраняем прогресс парсинга
    source.j_source_metadata['last_parsed_line'] = current_row_number
    source.j_source_metadata['total_lines'] = total_rows
    source.j_source_metadata['parsed_at'] = timezone.now().isoformat()
    source.save()
```

---

## АДМИНКА (упрощённо)

```python
class PendingTaskAdmin(admin.ModelAdmin):
    # Не наследуем от ModelAdmin (нет моделей!)
    # Вместо этого: читаем Redis, рендерим как таблицу
    
    def changelist_view(self, request):
        # Получаем из Redis
        tasks = [json.loads(redis.get(key)) for key in redis.keys('pending:*')]
        # Выводим нетипичную таблицу с кнопками: Одобрить, Мержить, Пропустить
```

---

## ФОНОВЫЙ ВОРКЕР (упрощённо)

```python
def process_approved_tasks():
    while True:
        task = redis.lpop('tasks:approved')
        
        try:
            if task['type'] == 'create':
                # Пишем в product БД
                TbMusicStyle.objects.create(title=task['title'], ...)
            elif task['type'] == 'merge':
                # Обновляем existing + добавляем синонимы
                style = TbMusicStyle.objects.get(id=task['merge_with_id'])
                style.j_style_synonyms.append(task['title'])
                style.save()
            
            # Успех → удалить из Redis
            redis.delete(task['_redis_key'])
            redis.lpush('tasks:completed', task)
        except Exception as e:
            redis.lpush('tasks:failed', {**task, 'error': str(e)})
```

---

## ТЕХНОЛОГИЧЕСКИЙ СТЕК

- **Redis** — очередь + кэш виртуальных объектов
- **Celery** или **APScheduler** — фоновый воркер для парсера и финального сохранения
- **Django Admin** — кастомная вкладка для управления очередью
- **PostgreSQL/SQLite** — product database (только одобренные данные)

---

## ВЕТКА: ПРЯМОЕ ПОПАДАНИЕ В БД (когда матчинг сработал)

Если парсер нашел алиас или группа уже в БД → **обходим очередь**, пишем сразу:

```python
def parse_source(source_id):
    source = TbSource.objects.get(id=source_id)
    
    for style_name in PARSED_STYLES:
        # 1. Ищем существующий стиль или по названию или по алиасам
        existing = TbMusicStyle.objects.filter(
            Q(s_style_name__iexact=style_name) |
            Q(j_style_synonyms__contains=style_name)
        ).first()
        
        if existing:
            # ✅ МАТЧИНГ СРАБОТАЛ → пишем сразу в БД
            if style_name not in existing.j_style_synonyms:
                existing.j_style_synonyms.append(style_name)  # Запомнили синоним!
                existing.save()
        else:
            # ❌ НОВЫЙ СТИЛЬ → в Redis очередь на одобрение
            redis.lpush('tasks:pending', {...})
    
    # В метаданных источника сохраняем прогресс парсинга
    source.j_source_metadata['last_parsed_line'] = current_row_number
    source.j_source_metadata['total_lines'] = total_rows
    source.j_source_metadata['parsed_at'] = timezone.now().isoformat()
    source.save()
```

---

## ИЗМЕНЕНИЕ ЦЕН (дополнительная ветка)

Когда уже существующий товар поменял цену → в отдельную очередь:

```
tasks:price_changes  ← Отдельная очередь 
  └─ {type: 'price_update', offer_id: 42, old_price: 100, new_price: 120}
  └─ {type: 'price_update', offer_id: 43, old_price: 200, new_price: 180}
```

**Обработка:**
- Фоновый воркер видит изменение цены
- Проверяет: изменилась ли существенно (> 5%)? 
- Если да → может требоваться одобрение (+1 задание в Redis)
- Если нет → пишет сразу в БД (TbOfferHistory записывается автоматически)

---

## МЕТАДАННЫЕ ОТСЛЕЖИВАНИЯ ПРОГРЕССА

В каждой **TbSource** должно быть поле `j_source_metadata`:

```python
j_source_metadata = JSONField(default=dict, help_text='Отслеживание парсинга и синонимы')

# Структура:
{
    "last_parsed_line": 4523,          # Докуда добежал парсер (для resume)
    "total_lines": 10000,              # Всего строк в файле
    "parsed_at": "2026-06-14T12:30:00",# Время последнего парсинга
    "status": "in_progress",            # in_progress | completed | failed
    "error_message": null,              # если failed, чтобы видно было почему
    
    # Найденные синонимы (стили, артисты, которые auto-matched)
    "matched_styles": {
        "Rock": 45,                     # Стиль 45 найден под названием "Rock"
        "rock": 45,                     # Вариант написания também сохранили
    },
    "matched_artists": {
        "The Beatles": 12,
        "Beatles, The": 12,
    }
}
```

Если парсер упал на строке 4523 → перезапуск продолжится с 4524, а не с начала!

---

## МАСШТАБИРУЕМОСТЬ: REDIS В ПАМЯТИ vs PERSISTENCE

### Проблема: 10k+ задач при загрузке большого Excel

```
Excel с 10,000 позиций
  ├─ 10k артистов
  ├─ 5k стилей
  ├─ 2k лейблов
  └─ 15k общих задач в очереди
```

Redis хранит в памяти по умолчанию ➜ контейнер перестартует ➜ всё теряется!

**Решение: RDB + AOF Persistence**

```yaml
# docker-compose.yml для Redis
redis:
  image: redis:7-alpine
  volumes:
    - redis-data:/data
  command: >
    redis-server
    --appendonly yes
    --appendfsync everysec
    --save 900 1
    --maxmemory 2gb
    --maxmemory-policy allkeys-lru
```

- **RDB snapshots** — снимок каждые 15 минут
- **AOF log** — каждая команда лог записывается на диск
- **maxmemory-policy** — если память 2GB переполнится, удаляются старые задачи (но только pending, не approved!)
- **Persistence**: при рестарте контейнера Redis восстановит все задачи из AOF

---

## ПАРАЛЛЕЛЬНАЯ ОБРАБОТКА (масштабирование)

Если задач много → **несколько воркеров**, каждый обрабатывает свой тип:

```python
# Worker 1: Парсит (пишет в tasks:pending)
celery_app.send_task('parser.parse_source', args=[source_id])

# Worker 2: Обрабатывает стили (слушает tasks:approved тип='style')
@app.task
def process_style_task(task_data):
    # обновить БД

# Worker 3: Обрабатывает артистов (слушает tasks:approved тип='artist')
@app.task
def process_artist_task(task_data):
    # обновить БД

# Worker 4: Обрабатывает цены (слушает tasks:price_changes)
@app.task
def update_offer_price(task_data):
    # обновить цену
```

Каждый воркер работает в отдельном потоке/процессе ➜ параллелизм!

---

## FLOW ПРИНЦИПИАЛЬНАЯ СХЕМА (обновлённая)

```
                    ┌──────────────────────────────────┐
                    │  ПАРСЕР (Worker 1)               │
                    │  Читает Excel/CSV/JSON           │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────┴────────────┐
                    │                           │
            ┌───────▼───────────┐   ┌─────────▼──────────┐
            │ Матч сработал?    │   │ Новые данные?      │
            │ (aliasing)        │   │ (неизвестны)       │
            └────┬──────────────┘   └─────────┬──────────┘
                 │ Yes                        │ No
                 │                            │
        ┌────────▼────────────┐     ┌────────▼────────────┐
        │ СРАЗУ В БД          │     │ tasks:pending       │
        │ + j_style_synonyms  │     │ (очередь нужнофала) │
        │ + metadata['matched']     │ (ждут одобрения)    │
        └────────┬────────────┘     └────────┬────────────┘
                 │                           │
                 │                    АДМИНКА ДЖАНГО
                 │                    (виртуальная таблица)
                 │                           │
                 │                    ┌──────┴──────┐
                 │                    │  ✅ ❌ 🔗   │
                 │                      (Approve/Skip/Merge)
                 │                    │             │
                 │            ┌───────▼─────┐       │
                 │            │ tasks:      │       │
                 │            │ approved    │       │
                 │            └───────┬─────┘       │
                 │                    │             │
                 └──────────┬─────────┴─────────────┘
                            │
                     Worker 2,3,4...
                            │
                     ┌──────▼──────┐
                     │ PRODUCT БД  │
                     │ (валидные)  │
                     └─────────────┘
```

---

## ДОПОЛНИТЕЛЬНЫЕ МЕТАДАННЫЕ ДЛЯ КАЖДОЙ ЗАДАЧИ

```python
# Каждая задача в Redis содержит:
task = {
    'id': 'pending:style:123',
    'type': 'style',                    # или 'artist', 'label', 'price_change'
    'data': {'title': 'Rock', ...},
    
    # Откуда пришла
    'source_id': 42,
    'source_name': 'Discogs API',
    'parsed_line': 4523,
    
    # Когда создана
    'created_at': '2026-06-14T12:00:00',
    'ttl_seconds': 86400,               # жить 24 часа, потом удалить
    
    # Статус обработки
    'attempts': 0,                      # сколько раз пытались обработать
    'last_error': null,
}
```

---

## ИТОГОВАЯ АРХИТЕКТУРА (расширенная)

```
ИСТОЧНИКИ (Excel/API)
    ↓ (15k записей)
┌──────────────────────────────────────────────────┐
│ REDIS ОЧЕРЕДИ (в памяти + AOF persistence)       │
│  ├─ tasks:pending (очередь неодобренных)         │
│  ├─ tasks:approved (одобренные)                  │
│  ├─ tasks:price_changes (изменения цен)          │
│  ├─ tasks:matched (уже в БД + синонимы)          │
│  ├─ tasks:completed (завершённые)                │
│  └─ tasks:failed (ошибки)                        │
└──────────────────────────────────────────────────┘
    ↓ (видит админка)         ↓ (видят воркеры)
┌──────────────────┐     ┌────────────────────┐
│ АДМИНКА ДЖАНГО   │     │ WORKERS (Celery)   │
│ (виртуальная     │     │ ├─ parse_source    │
│  таблица)        │     │ ├─ process_style   │
│ Действия:        │     │ ├─ process_artist  │
│  ok/del/edit/... │     │ └─ update_prices   │
└──────────────────┘     └────────────────────┘
         ↓                        ↓
         └──────────┬─────────────┘
                    ↓
        ┌─────────────────────┐
        │ PRODUCT БД          │
        │ (только валидные)   │
        │ + metadata progress │
        │ + aliases           │
        └─────────────────────┘
```
