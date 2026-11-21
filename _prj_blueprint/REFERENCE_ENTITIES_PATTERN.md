# Паттерн создания справочников: автоматизация статей, синонимов и валидации

**Дата:** 2026-07-15  
**Дата и время проверки:** 2026-11-21 01:30
**Статус проверки:** сверено с `models.py`, `utils.py`, `utils_validators.py`, `constants.py`, `admin.py` (имена, поля, алгоритмы); блоки про парсер, `ValidatorQueue`, Celery и внешние метаданные в коде отсутствуют (план); тексты сообщений админки и работа форм в браузере не проверялись.

**Что изменилось по итогам проверки:** исправлены имена типов совпадений (`EXACT_MATCH` на самом деле `IS_DUPLICATE`), алгоритм поиска и создания статьи, формат технического заголовка статьи, описание обновления синонимов, пути файлов. Парсерные части помечены как план; примеры метаданных для `TbItem` помечены устаревшими (ключи теперь описывает конфиг TOML). Автотестов на этот паттерн нет (`frontend/tests.py` пустой).

## Обзор

Система содержит 5 **справочных сущностей** (Reference Entities) которые описывают каталог:

| Модель      | Таблица      | Назначение                               | Связь с TbArticle |
|-------------|--------------|------------------------------------------|-------------------|
| Лейбл       | TbLabel      | Издатель, лейбл, дистрибьютор            | 1:1 OneToOne      |
| Исполнитель | TbArtist     | Артист, группа, бренд                    | 1:1 OneToOne      |
| Товар       | TbItem       | Альбом, релиз, носитель, аксессуар       | 1:1 OneToOne      |
| Стиль       | TbMusicStyle | Музыкальный жанр                         | 1:1 OneToOne      |
| Продавец    | TbSeller     | Магазин, продавец, издатель-дистрибьютор | 1:1 OneToOne      |

Все 5 моделей используют **единый паттерн**:
1. Автоматическое создание связанной статьи (если нет)
2. Управление синонимами в метаданных
3. Валидация дубликатов через админку
4. Подготовка к парсингу с очередью конфликтов (план, в коде нет: очереди конфликтов, парсера и `ValidatorQueue` нет)

Уточнение по коду: пункты 2 и 3 (синонимы и валидация) реализованы для `TbLabel`, `TbArtist`, `TbItem`, `TbMusicStyle`. У `TbSeller` в `save()` синонимов и валидации нет, только автоматическое создание статьи.

## Архитектура: TbArticle как связующее звено

```text
┌─────────────────────────────────────────────────────────────┐
│                      TbArticle                              │
│  (текст, SEO, картинка, слаг — для всех справочников)       │
│                                                             │
│  Поля:                                                      │
│  • s_article_title: "Label: Sony"                           │
│  • l_article_type: "label"                                  │
│  • slug: "label-sony" (URL-идентификатор)                   │
│  • k_article_to_image: ссылка на картинку (логотип, фото)   │
│  • seo_title, seo_description: для поисковиков и llm        │
│  • s_article_teaser_html, s_article_content_html: текст     │
└─────────────────────────────────────────────────────────────┘
         ▲                ▲                ▲           ▲
         │                │                │           │
       1:1              1:1              1:1         1:1
         │                │                │           │
┌────────┴────┐  ┌────────┴─────┐  ┌────────┴────┐  ┌──┴──────────┐
│   TbLabel   │  │   TbArtist   │  │    TbItem   │  │ TbMusicStyle│
│             │  │              │  │             │  │             │
│ s_label     │  │ s_artist     │  │ s_item      │  │ s_style_name│
│ j_metadata  │  │ j_metadata   │  │ j_metadata  │  │ j_metadata  │
│ (синонимы)  │  │ (синонимы)   │  │ (синонимы)  │  │ (синонимы)  │
└─────────────┘  └──────────────┘  └─────────────┘  └─────────────┘

TbSeller аналогично, без синонимов (используется редко)
```

> Уточнение: заголовок и slug на схеме иллюстративные. В коде технический заголовок статьи строится как `[<verbose_name модели>] <значение поля> (auto-make)` (например `[Лейбл] Sony (auto-make)`), поле `s_article_title` уникально. Slug строится через `make_slug()` из значения основного поля (транслитерация `pytils`, без префикса типа); значение по умолчанию берётся из транслитерации `verbose_name`. Тип статьи (`ArticleType`) определён в `lpon_site/lpon_site/constants.py` и доступен как `TbArticle.ArticleType`. При удалении справочника статья остаётся; при удалении статьи FK справочника обнуляется (`on_delete=SET_NULL`).

## Жизненный цикл справочника (на примере TbLabel)

### Фаза 1: Создание в админке

```python
# Админ создает новый лейбл через Django Admin форму
# Заполняет: s_label="Sony Music", j_label_metadata={"SYN_EN": [...]}

# При сохранении форма вызывает label.save()
```

### Фаза 2: Валидация синонимов (админка)

```python
# Функция validate_for_duplicates() проверяет по порядку (на проверках 1 и 2 останавливается и
# возвращает результат сразу). Возвращает не список, а словарь:
# {MODEL: имя модели, MATCH_TYPE: ValidateMatchType, MATCH_VALUE: QuerySet найденных записей}.
# Типы: IS_DUPLICATE=1, FIND_IN_SYNONYM=2, EXACT_SYNONYM_MATCH=3, PARTIAL_MATCH=4,
# PARTIAL_MATCH__RISK_SHORT_WORDS=5 (константы в lpon_site/constants.py).
# Админка вызывает validate_entity_for_admin_form(), а save() модели повторно проверяет через
# validate_and_raise_for_duplicates() как страховку.

# 1. IS_DUPLICATE (ранее в документе EXACT_MATCH): s_label == s_label в других записях (без учёта регистра)?
#    Результат: "Sony Music" уже есть в базе
#    Действие: Форма показывает ошибку, блокирует сохранение

# 2. FIND_IN_SYNONYM: s_label найден в синонимах других записей?
#    Результат: "Sony Music" найден в синонимах записи TbLabel(pk=5)
#    Действие: Админ видит список дубликатов, решает что делать

# 3. EXACT_SYNONYM_MATCH: синонимы разных лейблов совпадают?
#    Результат: {"SYN_EN": ["Sony", "Sony Music"]} уже есть в записи TbLabel(pk=3)
#    Действие: в админке по комментариям кода администратор подтверждает, и конфликтующие синонимы
#    удаляются из других записей (remove_conflicting_synonyms_from_duplicates); в save() вне админки
#    это блокируется ValidationError. Поведение формы в браузере не проверялось.
# 
# 4. PARTIAL_MATCH: частичное совпадение синонимов
#    Не критичные совпадения. s_label и синонимы из метаданных разбиваются по словам, ищутся совпадения слов.
#    Админ видит предупреждение. Для коротких слов (Inc, Ltd т.п.) может много ложных срабатываний. Админу показывается
#    список слов-совпадений, он с чем они совпали, и решает что делать.
#    Порог "короткого слова" это MIN_SYNONYM_WORD_LENGTH = 4 (constants.py); такие совпадения получают тип
#    PARTIAL_MATCH__RISK_SHORT_WORDS. В save() частичные совпадения не блокируют, а только пишутся в лог.
```

### Фаза 3: Автоматическое создание статьи

```python
# Если админ одобрил - вызывается label.save()

def save(self, *args, **kwargs):
    # Шаг 1: Валидация синонимов
    validate_and_raise_for_duplicates(self, 's_label', 'j_label_metadata')
    
    # Шаг 2: Обновление синонимов метаданных
    update_synonyms_in_metadata(self, 's_label', 'j_label_metadata')
    
    # Шаг 3: Создание или получение связанной статьи
    article = create_or_get_related_article(
        self,
        TbArticle.ArticleType.LABEL,  # тип статьи
        's_label',                      # основное поле
        'j_label_metadata',             # метаданные
        'k_label_to_article'            # FK на статью
    )
    self.k_label_to_article = article
    
    # Шаг 4: Сохранение
    super().save(*args, **kwargs)
```

**Что делает `create_or_get_related_article()`:**

> Прежний код-пример в этом разделе устарел (поиск статьи по заголовку и типу, `TbArticle.objects.create(...)`, заголовок `"Label: ..."`). Реальный алгоритм описан ниже.

```python
def create_or_get_related_article(
    instance,                  # TbLabel, TbArtist и т.д.
    article_type,              # TbArticle.ArticleType.LABEL
    main_field_name,           # 's_label'
    metadata_field_name,       # 'j_label_metadata'
    related_fk_field_name      # 'k_label_to_article' (параметр называется related_fk_field_name)
):
    # 1. Если FK уже указывает на статью (getattr(instance, related_fk_field_name)) - вернуть её.
    #    Поиска по заголовку или типу нет, запросов в БД на этом шаге нет.
    #    Поэтому переименование справочника не создаёт вторую статью.

    # 2. Иначе создать новую статью (TbArticle(...).save()):
    #    s_article_title      = f"[{verbose_name}] {значение} (auto-make)"   # уникальное поле
    #    s_article_title_html = значение
    #    seo_title            = значение
    #    seo_keywords         = синонимы (SYN_EN), verbose_name, slug по умолчанию
    #    seo_description      = f"{значение} ({verbose_name}): информация."
    #    l_article_type       = article_type
    #    b_article_published  = True
    #    slug                 = make_slug(значение, slug_default=транслитерация verbose_name)
    #    (если slug занят, TbArticle.save() добавляет счётчик -1, -2 ...)

    # 3. Вернуть статью; сама модель делает self.k_label_to_article = article.
    #    TODO в коде: уведомление в Redis для будущего парсера (план, не реализовано).
```

## Синонимы: управление и валидация

### Как формируются синонимы

Синонимы хранятся в JSONField `j_*_metadata` в формате:

```json
{
  "SYN_EN": [
    "The Beatles",
    "Beatles",
    "Beatles, The",
    "The Fab Four"
  ],
  "other_data": {...}
}
```

### Автоматическое обновление синонимов при сохранении

**Функция `update_synonyms_in_metadata()`:**

> Прежний код-пример устарел: атрибута `instance._original_value` в коде нет, константы `MIN_SYNONYM_WORD_LENGTH` при обновлении синонимов не используются, сортировки списка нет. Реальная логика ниже.

```python
def update_synonyms_in_metadata(instance, main_field_name, metadata_field_name):
    """
    При каждом сохранении (utils.py):
    1. Новая запись (pk is None): добавляем текущее значение основного поля в SYN_EN.
    2. Редактирование: старое значение читается отдельным запросом из БД
       (model_class.objects.get(pk=instance.pk)). Если значение изменилось, в SYN_EN
       добавляются и старое, и новое (если их там ещё нет).
    3. Дубликаты в списке убираются с сохранением порядка (list(dict.fromkeys(...))),
       порядок и ручные правки админа сохраняются; короткие слова не отфильтровываются.
    4. Если ключа SYN_EN нет или он не список, создаётся пустой список (KEY_SYNONYM_EN = 'SYN_EN').
    """
```

### Валидация синонимов при сохранении

```python
# Проверяем: все ли синонимы уникальны?

validate_for_duplicates(
    model_class=TbLabel,
    instance_pk=label.id,
    main_field_value=label.s_label,
    metadata_dict=label.j_label_metadata,
    main_field_name='s_label',
    metadata_field_name='j_label_metadata',
)

# validate_for_duplicates() возвращает словарь (см. выше), а не список.
# Если найдены дубликаты (IS_DUPLICATE, FIND_IN_SYNONYM, EXACT_SYNONYM_MATCH):
# - В админке: показываем форму с ошибкой + список дубликатов
# - В save() вне админки: ValidationError (validate_and_raise_for_duplicates)
# - В парсере (план, в коде нет): создаём запись в ValidatorQueue для админа
```

## Админка: как это видит пользователь

### Создание нового лейбла

```
Админ заполняет форму:
┌────────────────────────────┐
│ Название лейбла*           │
│ [ Sony Music           ]   │
│                            │
│ Метаданные (JSON)          │
│ { "SYN_EN": [...] }        │
│                            │
│ [ Сохранить ]              │
└────────────────────────────┘

При сохранении:
1. Проверяются синонимы (IS_DUPLICATE, FIND_IN_SYNONYM и далее)
2. Если конфликт → показывается ошибка:
   "Найдено совпадение! Существующие записи: [List]"
   
3. Если ОК → статья создаётся автоматически
   "Лейбл создан. Связанная статья: Label: Sony Music"
```

### Обновление существующего лейбла

```
Админ меняет название (например, опечатка):
[ Sony Musik ] → [ Sony Music ]

1. Синонимы обновляются: добавляются оба варианта
2. Статья остаётся той же (slug не меняется)
3. Сохраняется историчность: "был Sony Musik, теперь Sony Music"
```

### Ошибки при сохранении

```
Сценарий: Админ пытается создать дубликат

┌─────────────────────────────────────────────┐
│ ОШИБКА: TbLabel.save()                      │
│ Найдено совпадение в синонимах!             │
│ Разрешите на уровне админки.                │
│ PK конфликтующих записей: [1, 5, 12]       │
│                                             │
│ Подробно: "Sony Music" найдено в            │
│ синонимах TbLabel(pk=5)                     │
└─────────────────────────────────────────────┘

Решение: Админ либо меняет название, либо
объединяет с существующей записью вручную.
```

> Формулировки сообщений в блоках выше иллюстративные. Реальные тексты формируются в `validate_and_raise_for_duplicates()` и `generate_admin_save_message()` (`utils_validators.py`) и могут отличаться. Поля формы в админке: `s_label`, `j_label_metadata` и др. (редактор метаданных на CodeMirror).

## Применение ко всем 5 моделям

> Формат названия статьи для каждой модели ниже (`"Label: ..."`, `"Artist: ..."` и т.д.) устарел. Реально: `[<verbose_name>] <значение> (auto-make)`, где `verbose_name`: `Лейбл`, `Исполнитель`, `Музыкальный стиль`, `Товар в каталоге (релиз, носитель, аксессуар)`, `Продавец`. Значения `ArticleType`: `label`, `artist`, `style`, `item`, `seller`.

### TbLabel (Лейблы)

```python
class TbLabel(models.Model):
    s_label: str (уникальный)           # "Sony Music", "Мелодия"
    j_label_metadata: JSON              # {"SYN_EN": [...]}
    k_label_to_article: FK → TbArticle  # автоматическое создание
    
    # ArticleType: LABEL
    # Формат названия: "Label: Sony Music"
```

### TbArtist (Исполнители)

```python
class TbArtist(models.Model):
    s_artist: str (уникальный)          # "The Beatles", "David Bowie"
    j_artist_metadata: JSON             # {"SYN_EN": [...]}
    k_artist_to_article: FK → TbArticle # автоматическое создание
    
    # ArticleType: ARTIST
    # Формат названия: "Artist: The Beatles"
```

### TbMusicStyle (Стили)

```python
class TbMusicStyle(models.Model):
    s_style_name: str (уникальный)      # "Rock", "Jazz"
    j_style_metadata: JSON              # {"SYN_EN": [...]}
    k_style_to_article: FK → TbArticle  # автоматическое создание
    
    # ArticleType: STYLE
    # Формат названия: "Style: Rock"
```

### TbItem (Товары/Релизы)

```python
class TbItem(models.Model):
    s_item: str (уникальный)            # "Abbey Road (LP)"
    j_item_metadata: JSON               # {"SYN_EN": [...]}
    k_item_to_article: FK → TbArticle   # автоматическое создание
    
    # ArticleType: ITEM
    # Формат названия: "Item: Abbey Road (LP)"  (устарело, см. выше)
    # Дополнительно: k_item_to_artist (M2M на TbArtist), k_item_to_style (M2M на TbMusicStyle),
    # s_item_date (текстовая дата)
```

### TbSeller (Продавцы)

```python
class TbSeller(models.Model):
    s_seller: str (уникальный)          # "Клюква Records", "Amazon"
    j_seller_metadata: JSON             # (синонимы не используются)
    k_seller_to_article: FK → TbArticle # автоматическое создание
    
    # ArticleType: SELLER
    # Формат названия: "Seller: Клюква Records"
    # НЕ имеет синонимов (редко меняется, используется редко)
    # Дополнительно в модели: l_seller_type (seller/label/diy/crowdfunding/other), l_seller_currency (валюта)
    # j_seller_metadata допускает null
```

## Парсинг (будущее): интеграция с очередью конфликтов

> План, в коде нет: парсера, `ValidatorQueue`, Celery, Redis и Discogs-клиента в проекте нет (в `pyproject.toml` Celery не заявлен). `save()` при дубликатах только бросает `ValidationError`; в `create_or_get_related_article()` лежит лишь TODO про уведомление в Redis. Всё ниже в этом разделе описывает замысел.

### Сценарий: парсер вытащил данные из Discogs

```python
# Парсер получил из Discogs:
incoming_data = {
    's_artist': 'The Beatles',
    'j_artist_metadata': {
        'SYN_EN': ['Beatles', 'The Fab Four'],
        'DISCOGS_ID': 123456,
        'COUNTRY': 'UK',
        'FORMED': '1960',
    }
}

# Парсер пытается создать TbArtist(**incoming_data)
artist = TbArtist(**incoming_data)
artist.save()  # Вызывает валидацию

# Если есть конфликт (FIND_IN_SYNONYM, EXACT_SYNONYM_MATCH):
# - Парсер ловит ValidationError
# - Создаёт запись в ValidatorQueue
# - Админ получает уведомление про конфликт
# - Админ решает: создать новую / объединить / пропустить
```

### Структура ValidatorQueue для справочников (план, в коде нет)

```python
ValidatorQueue(
    k_source=excel_file_source,
    l_model_type='TbArtist',
    l_conflict_type='FIND_IN_SYNONYM',  # тип конфликта
    model_pk=None,  # это новая запись (или PK существующей)
    
    j_incoming_data={
        's_artist': 'The Beatles',
        'j_artist_metadata': {'SYN_EN': [...], 'DISCOGS_ID': ...}
    },
    
    j_duplicates=[
        {
            'pk': 15,
            's_artist': 'Beatles',
            'matched_value': 'The Beatles',
            'match_type': 'FIND_IN_SYNONYM',
            'reason': 'Найдено в синонимах'
        }
    ],
    
    l_status='pending',  # Ждёт решения админа
    s_admin_decision=None,  # Админ ещё не решил
)
```

### Решения админа

```
1. "create_new" — создать новую запись (с дубликатом)
   Когда: Если это действительно разные сущности (например, 
   The Beatles (группа) vs The Beatles (альбом))

2. "merge" — объединить с существующей
   Когда: Если это одна и та же сущность, только разные названия
   Действие: Добавить синонимы в существующую запись

3. "skip" — пропустить
   Когда: Данные некорректны или дубликаты действительно
   Действие: Ничего не создавать, просто пропустить
```

## Метаданные для парсинга: проверить, можно что-то вытащить из внешних источников

> План, в коде нет, плюс частично устарело. В `constants.py` для артистов, лейблов, стилей и продавцов определены только ключи `SYN_EN` и `SYN_RU` (`KEY_SYNONYM_EN`, `KEY_SYNONYM_RU`); остальные ключи ниже (`DISCOGS_ID`, `FORMED`, `COUNTRY` и т.д.) только предложения. Блоки JSON ниже содержат комментарии `//` и висячие запятые, это не валидный JSON. Для `TbItem` ключи метаданных теперь описываются конфигом TOML (`config/metadata-toml/default.toml`, см. `00_START_HERE.md` и `lpon--metadata-config.md`), а в `constants.py` имена ключей другие (`media_type`, `media_format`, `release_year`, `market`, `catalog_num`, `barcode` и др.).

### Из Discogs (для всех справочников)

```json
{
  "DISCOGS_ID": 123456,           // ID записи в Discogs
  "DISCOGS_URL": "https://...",   // Ссылка на Discogs
  "DISCOGS_UPDATED": "2024-01-15",// Дата обновления на Discogs
  "SYN_EN": [                      // Синонимы на английском
    "Alternative name",
    "Another variant"
  ]
}
```

### Для TbArtist (исполнители) — из Discogs, MusicBrainz

```json
{
  "ARTIST_TYPE": "Group",         // Solo, Group, Orchestra, Character
  "FORMED": "1960",               // Год образования
  "DISBANDED": null,              // Год распада (если есть)
  "COUNTRY": "GB",                // Страна (ISO 3166-1)
  "AREA": "United Kingdom",       // Регион
  "MEMBERS": [                    // Участники (для групп)
    {"name": "John Lennon", "role": "Vocals"},
    {"name": "Paul McCartney", "role": "Bass"},
  ],
  "WEBSITE": "https://beatles.com",       // Официальный сайт
  "WIKIPEDIA": "https://en.wikipedia.org/...",  // Статья
  "MUSICBRAINZ_ID": "uuid-here",  // MusicBrainz ID
  "BIOGRAPHY": "Краткая биография...",  // Текст для статьи
  "IMG_URL": "https://...",       // Ссылка на изображение
  "YANDEX_MUSIC_ID": 123456,        // ID на Яндекс.Музыке
  "SPOTIFY_ID": "spotify-id",         // ID на Spotify
  "SYN_EN": [...],
  "SYN_RU": [...]                 // Синонимы на русском
}
```

### Для TbLabel (лейблы) — из Discogs, MusicBrainz

```json
{
  "LABEL_TYPE": "Production",     // Production, Reissue, Distributor
  "FOUNDED": "1945",              // Год основания
  "COUNTRY": "USA",               // Страна
  "HEADQUARTERS": "New York, NY", // Штаб-квартира
  "PARENT_LABEL": 456789,         // ID материнского лейбла (Discogs)
  "WEBSITE": "https://sony.com",  // Официальный сайт
  "WIKIPEDIA": "https://...",     // Статья
  "CONTACT_EMAIL": "info@...",    // Email контакта
  "CONTACT_PHONE": "+1-234-567",  // Телефон
  "COMPANY_SIZE": "Large",        // Small, Medium, Large, Mega
  "DISCOGS_CATALOG_PREFIX": "SR", // Префикс каталога
  "IMG_LOGO": "https://...",      // Логотип
  "SYN_EN": [...],
  "SYN_RU": [...]
}
```

### Для TbItem (релизы/альбомы) — из Discogs, MusicBrainz (устарело: ключи ниже не совпадают с принятым решением, метаданные товара описывает конфиг TOML)

```json
{
  "ITEM_TYPE": "Album",           // Album, Single, EP, Compilation
  "RELEASE_DATE": "1969-09-26",   // Дата выхода
  "FORMAT": "Vinyl LP",           // Vinyl LP, CD, Cassette, Digital
  "COUNTRY": "GB",                // Страна выхода
  "BARCODE": "093624892340",      // Штрихкод
  "DISCOGS_ID": 987654,           // ID мастер-релиза
  "MUSICBRAINZ_ID": "uuid",       // MusicBrainz ID
  "GENRES": ["Rock", "Pop"],      // Жанры (для синхронизации с TbMusicStyle)
  "CATALOG_NUMBER": "SR-123",     // Каталожный номер издателя
  "LANGUAGE": "English",          // Язык вокала/текста
  "TRACKS_COUNT": 14,             // Количество треков
  "DURATION": "42:30",            // Длительность альбома
  "RATING": 4.5,                  // Рейтинг на Discogs (1-5)
  "NOTES": "Limited edition...",  // Примечания
  "IMG_COVER": "https://...",     // Обложка альбома
  "YANDEX_MUSIC_ID": 123456,        // ID на Яндекс.Музыке
  "SPOTIFY_ID": "spotify-id",         // ID на Spotify
  "SYN_EN": [...],
  "SYN_RU": [...]
}
```

### Для TbMusicStyle (жанры/стили) — из Discogs, MusicBrainz, Wikipedia

```json
{
  "STYLE_TYPE": "Primary",        // Primary, Sub-genre
  "DESCRIPTION": "Rock music is...", // Описание жанра
  "ORIGIN_COUNTRY": "USA",        // Страна происхождения
  "ORIGIN_YEAR": "1950s",         // Период возникновения
  "PARENT_GENRE": "Rock",         // Основной жанр (для иерархии)
  "RELATED_STYLES": [             // Связанные жанры
    "Hard Rock",
    "Progressive Rock"
  ],
  "NOTABLE_ARTISTS": [            // Известные исполнители
    "The Beatles",
    "Rolling Stones"
  ],
  "WIKIPEDIA": "https://...",     // Статья в Википедии
  "IMG_ILLUSTRATION": "https://...", // Иллюстрация для жанра
  "SYN_EN": [...],
  "SYN_RU": [...]
}
```

### Для TbSeller (продавцы) — из веб-скрейпинга, API или Excel (для excel и ручного ввода заполнять руками)

```json
{
  "SELLER_TYPE": "Store",         // Store, Label, Distributor, Marketplace
  "FOUNDED": "2005",              // Год основания
  "COUNTRY": "RU",                // Страна
  "CITY": "Moscow",               // Город
  "ADDRESS": "ul. Pushkina, 42",  // Адрес
  "WEBSITE": "https://example.com", // Сайт
  "EMAIL": "sales@example.com",   // Email
  "PHONE": "+7-495-123-45-67",    // Телефон
  "SOCIAL_VK": "https://vk.com/...", // VKontakte
  "SOCIAL_INSTAGRAM": "https://...", // Instagram
  "SHIPPING_COUNTRIES": [         // Страны доставки
    "RU", "BY", "KZ"
  ],
  "PAYMENT_METHODS": [            // Методы оплаты
    "Card", "Bank transfer", "Cash"
  ],
  "RETURNS_POLICY": "7 days",     // Политика возврата
  "RATING": 4.8,                  // Рейтинг на платформе
  "REVIEWS_COUNT": 342,           // Количество отзывов
  "IMG_LOGO": "https://...",      // Логотип магазина
}
```

## Жизненный цикл в нескольких слов

```
Админка                          Парсер (будущее)
    │                               │
    ├─ Заполняет форму              ├─ Читает Discogs/Excel
    │  (название, синонимы)         │  (вытаскивает данные)
    │                               │
    ├─ Нажимает "Сохранить"         ├─ Вызывает Model.save()
    │                               │
    ├─ Валидация синонимов          ├─ Валидация синонимов
    │  (FIND_IN_SYNONYM?)           │  (конфликты?)
    │                               │
    ├─ Ошибка? → показать админу    ├─ Конфликт? → ValidatorQueue
    │                               │
    ├─ OK? → создать статью         ├─ OK? → создать модель
    │         автоматически         │        + статья автоматически
    │                               │
    └─ Данные целостны и готовы     └─ Админ решает позже
```

## Преимущества подхода

✓ **Единообразие**: 5 моделей работают по одному паттерну  
✓ **Автоматизация**: Статьи создаются сами, не нужна ручная работа  
✓ **Валидация**: Дубликаты и синонимы проверяются автоматически  
✓ **Контроль**: Админ видит конфликты и может принять решение  
✓ **Масштабируемость**: Легко добавить другие справочники (если нужны)  
✓ **SEO-дружественно**: Каждый справочник имеет URL через слаг  
✓ **История**: Изменения в названиях сохраняются через синонимы  
✓ **Готовность к парсерам**: Структура поддерживает будущую интеграцию

## Файлы реализации

- **Модели**: `lpon_site/frontend/models.py` (TbLabel, TbArtist, TbItem, TbMusicStyle, TbSeller)
- **Валидаторы**: `lpon_site/frontend/utils_validators.py` (`validate_for_duplicates`, `validate_and_raise_for_duplicates`, `validate_entity_for_admin_form`, `remove_conflicting_synonyms_from_duplicates`, `build_search_report`, `generate_admin_save_message`)
- **Хелперы**: `lpon_site/frontend/utils.py` (`create_or_get_related_article`, `update_synonyms_in_metadata`, `make_slug`, `normalize_string`, `super_normalize_string`)
- **Константы**: `lpon_site/lpon_site/constants.py` (`ArticleType`, `ValidateMatchType`, `KEY_SYNONYM_EN`, `KEY_SYNONYM_RU`, `MIN_SYNONYM_WORD_LENGTH`; в `settings.py` подтягиваются через `from .constants import *`)
- **Админка**: `lpon_site/frontend/admin.py` (`LabelAdmin`, `ArtistAdmin`, `MusicStyleAdmin`, `ItemAdmin`, `SellerAdmin`)
- **Парсер** (план, файлов нет): `lpon_site/parser/models.py` (ValidatorQueue), `tasks.py` (Celery задачи)

## TODO: интеграция парсера

По состоянию на 2026-11-21 ни один пункт не выполнен.

- [ ] Создать Celery tasks для парсинга Discogs/Excel
- [ ] Реализовать ValidatorQueue с админ-интерфейсом
- [ ] Добавить поддержку очереди конфликтов в моделях
- [ ] Интегрировать сбор метаданных из Discogs API
- [ ] Документировать API для парсера
- [ ] Написать тесты для валидации и парсинга
