# frontend/utils.py
# Служебные функции и хелперы проекта

import re
import pytils
import random
import logging
from bs4 import BeautifulSoup
from html import unescape
from etpgrf.config import HANGING_PUNCTUATION_SPACE_CHARS as SPACE_CHARS
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.db.models.expressions import RawSQL
from django.utils.html import mark_safe
from lpon_site.settings import (
    SLUG_MAX_LENGTH, KEY_SYNONYM,
    VALIDATE_KEY__MATCH_TYPE, VALIDATE_KEY__MODEL, VALIDATE_KEY__VALUE,
    ValidateMatchType
)

logger = logging.getLogger(__name__)


def normalize_string(s: str) -> str:
    """
    Нормализует строку: удаляет невидимые символы, начальные, конечные и дублирующие пробелы.

    Работает со ВСЕМИ типами пробельных символов (не-breaking space, thin space и т.д.).

    Args:
        s: Строка для нормализации

    Returns:
        str: Нормализованная строка (или пустая если была пуста)

    Пример:
        >> normalize_string("  Sony   Music  ")
        'Sony Music'
        >> normalize_string("Sony\u00a0\u202FMusic")  # с неразрывными пробелами
        'Sony Music'
    """
    if not s:
        return ""

    result = str(s)

    # Удаляем невидимые символы (не заменять, а полностью удалять)
    result = result.translate({
        ord("\xad"): None,    # символ мягкого переноса
        ord("\u200b"): None,  # символ нулевой ширины (zero-width space)
        ord("\u200c"): None,  # символ нулевой ширины (zero-width non-joiner)
        ord("\u200d"): None,  # символ Zero Width Joiner (ZWJ)
        ord("\u2060"): None,  # символ Word Joiner (WJ)
        ord("\ufeff"): None,  # символ Zero Width No-Break Space (BOM)
    })

    # Все типы пробельных символов для замены на обычный пробел
    all_spaces = SPACE_CHARS | frozenset([
        "\u00a0",   # non-breaking space (&nbsp)
        "\u202F",   # narrow no-break space (тонкий неразрывный пробел)
    ])

    # Заменяем ВСЕ типы пробелов на обычный пробел
    for space_char in all_spaces:
        result = result.replace(space_char, " ")

    # Удаляем начальные/конечные пробелы и нормализуем множественные пробелы
    # Финальная подстраховка: regex для ВСЕХ unicode whitespace символов (даже неизвестных)
    result = re.sub(r'\s+', ' ', result).strip()
    return result


def safe_html_special_symbols(s: str) -> str:
    """Преобразует HTML-фрагмент в чистый текст.

       Удаляет все HTML-теги и декодирует HTML-мнемоники в Unicode.
       Затем нормализует пробелы через normalize_string().

       Args:
            s: Строка, которую надо очистить (с возможной HTML-разметкой).
       Returns:
            str: Чистый текст без HTML-разметки, спецсимволов и нормализованный.

        Example:
            >> safe_html_special_symbols('<p>Привет&nbsp;<b>мир</b>!</p>')
            'Привет мир!'
            >> safe_html_special_symbols('Текст с\\u00a0неразрывным и \\u202Fтонким пробелом')
            'Текст с неразрывным и тонким пробелом'
    """
    if not s:
        return ""

    try:
        soup = BeautifulSoup(s, "html.parser")
    except Exception as e:
        logger.warning(f"BeautifulSoup parse error, using raw string: {e}")
        return str(s)

    # Скрипты и стили в чистый текст не нужны — выкидываем их целиком.
    for tag in soup(["script", "style", "noscript", "code", "kbd", "pre"]):
        tag.decompose()

    result = soup.get_text()
    result = unescape(result)

    # Нормализуем: удаляем невидимые символы, все типы пробелов, дубли и края
    return normalize_string(result)


def make_slug(slug_it: str, max_length: int | None = None, slug_default: str = "content") -> str:
    """Готовит чистый slug из HTML/Unicode текста (включая русский текст).

    Преобразует текст в URL-friendly slug:
    - Удаляет HTML-теги
    - Транслитерирует русский текст
    - Удаляет спецсимволы
    - Обрезает до max_length
    - Гарантирует уникальность (fallback на случайное значение)

    Args:
       slug_it: Строка для преобразования в slug.
       max_length: Максимальная длина slug (по умолчанию из settings).
       slug_default: Значение по умолчанию, если slug пустой после обработки.

    Returns:
       str: Чистый slug, готовый для использования в URL.

    Example:
       >> make_slug('<b>The Beatles</b>')
       'the-beatles'
       >> make_slug('Какой-то текст')
       'kakoj-to-tekst'
    """
    if not slug_it:
        return f"{slug_default}-{random.randint(1, 4095):03x}"

    max_length = max_length or SLUG_MAX_LENGTH

    # Вычисляем минимальную длину fallback'а: "slug_default-xyz"
    min_fallback_length = len(slug_default) + 1 + 3  # "-" и 3 hex-символа

    # Очищаем текст от HTML и спецсимволов
    clean_text = safe_html_special_symbols(slug_it).lower()

    # Транслитерируем и создаем slug (pytils подходит для русского)
    slug = pytils.translit.slugify(clean_text)

    # Нормализуем множественные дефисы,  удаляем дефисы в начале/конце
    slug = re.sub(pattern=r"-+", repl="-", string=slug).strip("-")

    # Обрезаем излишнее (но только если это не нарушит fallback)
    # Если max_length недостаточен для slug_default, не обрезаем
    if max_length >= min_fallback_length:
        slug = slug[:max_length]

    # Если все еще пусто — генерируем fallback (БЕЗ обрезания!)
    return slug or f"{slug_default}-{random.randint(1, 4095):03x}"



def validate_for_duplicates(
    model_class,
    instance_pk: int | None,
    main_field_value: str,
    metadata_dict: dict | None,
    main_field_name: str | None = None,
    metadata_field_name: str | None = None,
) -> dict:
    """
    Универсальный валидатор для проверки дубликатов в моделях БД.

    Находит дубликаты и возвращает их список.
    Логика обработки (исключение, логирование, API ответ) — дело вызывающего кода.

    Args:
        model_class: Класс модели для поиска (TbLabel, TbArtist и т.д.). Обязателен!
        instance_pk: PK текущей записи или None для новых записей
        main_field_value: Значение основного поля для проверки (s_label, s_artist и т.д.). Не может быть пусто!
        metadata_dict: Словарь метаданных, содержащий синонимы. Может быть None или {}
        main_field_name: Имя основного поля модели (s_label, s_artist, s_style_name). Обязателен!
        metadata_field_name: Имя поля метаданных (j_label_metadata, j_artist_metadata). Обязателен!

    Returns:
        list: Список найденных дубликатов (может быть пустой)
        Каждый элемент: {'pk': int, 's_label': str, 'matched_value': str, 'match_type': str, ...}

    Примеры использования:
        # В админке
        duplicates = validate_for_duplicates(
            model_class=TbLabel,
            instance_pk=self.instance.pk,
            main_field_value=self.cleaned_data['s_label'],
            metadata_dict=self.instance.j_label_metadata,
            main_field_name='s_label',
            metadata_field_name='j_label_metadata',
        )
        if duplicates:
            raise ValidationError("Найдены дубликаты...")

        # В парсере
        duplicates = validate_for_duplicates(...)
        if duplicates:
            logger.warning(f"Дубликаты найдены: {duplicates}")
            continue
    """
    # ===== ВАЛИДАЦИЯ ПАРАМЕТРОВ =====

    # Проверяем, что model_class и имена полей переданы
    if model_class is None:
        raise TypeError("model_class is required and cannot be None")
    if main_field_name is None:
        raise TypeError(
            "main_field_name is required and cannot be None.\nExample: 's_label', 's_artist', 's_style_name'"
        )
    if metadata_field_name is None:
        raise TypeError(
            "metadata_field_name is required and cannot be None.\nExample: 'j_label_metadata', 'j_artist_metadata'"
        )

    # Проверяем, что поля существуют в модели
    for field_name in [main_field_name, metadata_field_name]:
        if not hasattr(model_class, field_name):
            raise AttributeError(
                f"Model '{model_class.__name__}' has no field '{field_name}'"
            )

    # Проверяем main_field_value (не может быть пусто даже после нормализации)
    if not main_field_value or not str(main_field_value).strip():
        raise ValidationError("main_field_value cannot be empty or whitespace")

    # Нормализуем основное поле (удаляем пробелы в начале/конце и дублирующие)
    normalized_main_value = normalize_string(main_field_value)

    # Проверяем, что после нормализации остался какой-то текст
    if not normalized_main_value:
        raise ValidationError("main_field_value becomes empty after normalization")

    # Проверяем metadata_dict (если передан, должен быть dict или None)
    if metadata_dict is not None and not isinstance(metadata_dict, dict):
        raise TypeError(
            f"metadata_dict must be dict or None, got {type(metadata_dict).__name__}"
        )

    # ===== ОСНОВНАЯ ЛОГИКА =====

    duplicates_found = {VALIDATE_KEY__MODEL: model_class.__name__}

    # ПОДГОТОВКА: Получаем базовый queryset (все записи кроме текущей, если редактируем)
    # Это ленивый запрос - запрос выполнится, только когда мы применим фильтры
    records_to_check = model_class.objects.all()
    if instance_pk is not None:
        # При редактировании исключаем текущую запись из поиска, чтобы не найти "самого себя"
        records_to_check = records_to_check.exclude(pk=instance_pk)

    # ПРОВЕРКА 1: EXACT MATCH (точное совпадение основного поля)
    # Ищем: есть ли другая запись с точно таким же main_field_value?
    filter_kwargs = {f"{main_field_name}__exact": normalized_main_value}
    exact_matches = records_to_check.filter(**filter_kwargs)
    if exact_matches.exists():
        duplicates_found.update({
            VALIDATE_KEY__MATCH_TYPE: ValidateMatchType.IS_DUPLICATE,
            VALIDATE_KEY__VALUE: exact_matches,
        })
        return duplicates_found

    # ПРОВЕРКА 2: SYNONYM MATCH (совпадение с синонимами в метаданных других записей)
    # Ищем: есть ли текущее значение main_field в синонимах других записей?
    # Например, если у записи A синонимы=['Sony Music', 'SME Records'],
    # а мы добавляем запись B с основным полем 'Sony Music', это совпадение!

    # Используем RawSQL для работы с JSON функциями SQLite
    # json_each(j_label_metadata, '$.SYNONYM') развертывает массив синонимов в отдельные строки
    # Это необходимо т.к. Django ORM для SQLite не поддерживает __contains для JSON полей

    # Строим RawSQL запрос для поиска в JSON массиве синонимов
    # json_each распарсивает массив и ищет совпадение со значением
    synonym_matches = records_to_check.annotate(
        has_synonym=RawSQL(
            f"""
            EXISTS (
                SELECT 1 FROM json_each({metadata_field_name}, '$.{KEY_SYNONYM}')
                WHERE json_each.value = %s
            )
            """,
            (normalized_main_value,)
        )
    ).filter(has_synonym=True)

    # Если найдены совпадения в синонимах - возвращаем все найденные записи
    if synonym_matches.exists():
        duplicates_found.update({
            VALIDATE_KEY__MATCH_TYPE: ValidateMatchType.FIND_IN_SYNONYM,
            VALIDATE_KEY__VALUE: synonym_matches,
        })
        return duplicates_found

    # ПРОВЕРКА 3: EXACT_SYNONYM_MATCH (точное совпадение синонимов текущей записи с синонимами других)
    # Ищем: есть ли синонимы из текущей записи в синонимах других записей?
    # Пользователь мог отредактировать список синонимов в форме, и мы не хотим дубликатов среди синонимов.
    # Например, если текущая запись имеет синонимы=['Polydor Records', 'Vertigo France'],
    # а запись A имеет синонимы=['Vertigo France', 'Swirl'], это совпадение!
    # Пользователь подтверждает - удалим конфликтующие синонимы из других записей.

    if KEY_SYNONYM in metadata_dict and isinstance(metadata_dict[KEY_SYNONYM], list):
        # Собираем все синонимы текущей записи с нормализацией
        current_synonyms = [
            normalize_string(syn) for syn in metadata_dict[KEY_SYNONYM]
        ]

        # Если есть синонимы для проверки
        if current_synonyms:
            # Строим RawSQL условие для поиска любого из наших синонимов в JSON массиве других записей
            # Используем один аннотированный queryset со всеми условиями OR для поиска всех конфликтов сразу
            synonym_query_parts = []
            query_params = []
            for normalized_synonym in current_synonyms:
                synonym_query_parts.append(
                    f"EXISTS (SELECT 1 FROM json_each({metadata_field_name}, '$.{KEY_SYNONYM}') WHERE json_each.value = %s)"
                )
                query_params.append(normalized_synonym)

            # Объединяем все условия через OR - это вернет записи, у которых есть хотя бы один из наших синонимов
            synonym_in_others = records_to_check.annotate(
                has_any_synonym=RawSQL(
                    " OR ".join(synonym_query_parts),
                    query_params
                )
            ).filter(has_any_synonym=True).distinct()

            # Если найдены записи с совпадающими синонимами - возвращаем их все в одном queryset
            if synonym_in_others.exists():
                duplicates_found.update({
                    VALIDATE_KEY__MATCH_TYPE: ValidateMatchType.EXACT_SYNONYM_MATCH,
                    VALIDATE_KEY__VALUE: synonym_in_others,
                })
                return duplicates_found

    # Когда все проверки прошли -- возвращаем пустой словарь
    return duplicates_found


def remove_conflicting_synonyms_from_duplicates(
    duplicates_queryset: QuerySet,
    metadata_field_name: str,
    synonyms_to_remove: list[str],
) -> None:
    """
    Удаляет из метаданных (поле с именем metadata_field_name) записей (QuerySet) синонимы, которые совпадают
    со списком (synonyms_to_remove).

    Универсальный хелпер для очистки синонимов при подтверждении пользователем обхода валидации.

    Args:
        duplicates_queryset: QuerySet записей, где нужно удалить синонимы
        metadata_field_name: Имя поля метаданных ('j_label_metadata', 'j_artist_metadata' и т.д.)
        synonyms_to_remove: Список синонимов для удаления (будут нормализованы перед сравнением)

    Пример использования:
        # Удаляем основное поле текущей записи из синонимов других (FIND_IN_SYNONYM)
        remove_conflicting_synonyms_from_duplicates(
            duplicates_queryset,
            'j_label_metadata',
            [main_field_value],
        )

        # Удаляем все синонимы текущей записи из синонимов других (EXACT_SYNONYM_MATCH)
        remove_conflicting_synonyms_from_duplicates(
            duplicates_queryset,
            'j_label_metadata',
            metadata_dict.get(KEY_SYNONYM) or [],
        )
    """
    # Нормализуем синонимы для удаления один раз
    normalized_to_remove = [normalize_string(syn) for syn in synonyms_to_remove]

    for duplicate_record in duplicates_queryset:
        # Получаем текущие метаданные записи
        dup_metadata = getattr(duplicate_record, metadata_field_name) or {}

        # Если в метаданных есть синонимы, удаляем те, которые совпадают с нашим списком
        if KEY_SYNONYM in dup_metadata and isinstance(dup_metadata[KEY_SYNONYM], list):
            # Удаляем синонимы, которые совпадают с переданным списком
            dup_metadata[KEY_SYNONYM] = [
                syn for syn in dup_metadata[KEY_SYNONYM]
                if normalize_string(syn) not in normalized_to_remove
            ]
            # Сохраняем обновленные метаданные
            setattr(duplicate_record, metadata_field_name, dup_metadata)
            # Сохраняем запись (обновляем только поле с метаданными)
            duplicate_record.save(update_fields=[metadata_field_name])


def validate_entity_for_admin_form(form_instance, cleaned_data,
                                   main_field_name='s_label',
                                   metadata_field_name='j_label_metadata',
                                   request=None):
    """
    Универсальный валидатор для админских форм.

    Проверяет сущность на совпадения (дубликаты) с уже существующими записями.
    Выбрасывает ValidationError с кликабельными ссылками на найденные дубликаты.

    Используется во всех админских forms: LabelAdminForm, ArtistAdminForm, MusicStyleAdminForm и т.д.

    Args:
        form_instance: Экземпляр формы (self из clean методе)
        cleaned_data: Очищенные данные формы
        main_field_name: Имя основного поля ('s_label', 's_artist', 's_style_name')
        metadata_field_name: Имя поля метаданных ('j_label_metadata', 'j_artist_metadata')
        request: HTTP request объект (опционально, используется для проверки GET параметра ignore_validate)

    Raises:
        ValidationError: Если найдены совпадения (дубликаты) и GET параметр не установлен

    Пример использования в LabelAdminForm:
        def clean(self):
            cleaned_data = super().clean()
            validate_entity_for_admin_form(
                self,
                cleaned_data,
                main_field_name='s_label',
                metadata_field_name='j_label_metadata',
                request=self.request if hasattr(self, 'request') else None,
            )
            return cleaned_data
    """

    # Получаем класс модели из метаинформации формы
    model_class = form_instance.Meta.model

    # Получаем значения из формы
    main_field_value = cleaned_data.get(main_field_name)
    metadata_dict = cleaned_data.get(metadata_field_name) or {}

    # Если основное поле не заполнено, пропускаем валидацию
    if not main_field_value:
        return

    # Нормализуем основное значение для сравнения (как в validate_for_duplicates)
    normalized_main_value = normalize_string(main_field_value)

    # Вызываем основной валидатор дубликатов
    result = validate_for_duplicates(
        model_class=model_class,
        instance_pk=form_instance.instance.pk,
        main_field_value=main_field_value,
        metadata_dict=metadata_dict,
        main_field_name=main_field_name,
        metadata_field_name=metadata_field_name,
    )

    # Обрабатываем результаты проверки в зависимости от типа найденного совпадения
    if VALIDATE_KEY__MATCH_TYPE in result:
        match_type = result[VALIDATE_KEY__MATCH_TYPE]
        duplicates_queryset = result[VALIDATE_KEY__VALUE]

        # В dup_links формируем ссылки на найденные дубликаты для быстрого перехода в админке
        dup_links = []

        # Используем match-case для удобной обработки разных типов совпадений
        # С Enum вместо магических чисел код становится самодокументируемым
        # В будущем легко добавить новые типы: ValidateMatchType.PARTIAL_MATCH = 2 и т.д.
        match match_type:
            case ValidateMatchType.IS_DUPLICATE:
                # ОБРАБОТКА ТОЧНЫХ ДУБЛИКАТОВ
                for dup in duplicates_queryset:
                    # Относительная ссылка зависит от режима админки:
                    # При создании: /admin/app/model/add/ → ../456/change/
                    # При редактировании: /admin/app/model/123/change/ → ../..456/change/
                    rel_url = f"../{dup.pk}/change/" if form_instance.instance.pk is None else f"../../{dup.pk}/change/"
                    # Получаем значение основного поля из дубликата для вывода в ссылке
                    dup_value = getattr(dup, main_field_name, '?')
                    dup_links.append(f"<big><a href='{rel_url}'>#{dup.pk} '{dup_value}'</a></big>")

                # Объединяем все найденные дубликаты в один список
                dup_list = ", ".join(dup_links)

                # Для случая IS_DUPLICATE всегда выбрасываем ошибку, т.к. это критическая ситуация
                # и поле часто имеет unique=True на уровне модели.
                raise ValidationError(
                    mark_safe(
                        f"ОШИБКА: Найдено ПОЛНОЕ совпадение! "
                        f"Измените название или отредактируйте {dup_list}."
                    )
                )

            case ValidateMatchType.FIND_IN_SYNONYM:
                # ОБРАБОТКА СОВПАДЕНИЙ В СИНОНИМАХ (основное поле совпадает с синонимами других)
                # Проверяем: это запрос с подтверждением (ignore_validate=1) или первоначальная проверка?
                if request and request.GET.get('ignore_validate') == '1':
                    # РЕЖИМ: ОБХОД ВАЛИДАЦИИ (пользователь нажал красную кнопку и подтвердил "Я проверил и уверен!")
                    # Тихо удаляем найденные совпадения из синонимов других записей
                    remove_conflicting_synonyms_from_duplicates(
                        duplicates_queryset,
                        metadata_field_name,
                        [normalized_main_value],  # Удаляем основное поле текущей записи
                    )
                    # Выходим без ошибки в админку, т.к. пользователь "проверил и уверен!"
                    # Конфликтующие синонимы удалены, запись сохранится нормально
                    return

                else:
                    # РЕЖИМ: ПЕРВОНАЧАЛЬНАЯ ПРОВЕРКА
                    # Показываем пользователю красную кнопку подтверждения с информацией о совпадениях
                    for dup in duplicates_queryset:
                        rel_url = f"../{dup.pk}/change/" if form_instance.instance.pk is None else f"../../{dup.pk}/change/"
                        dup_value = getattr(dup, main_field_name, '?')
                        dup_links.append(f"<big><a href='{rel_url}'>#{dup.pk} '{dup_value}'</a></big>")
                    dup_list = ", ".join(dup_links)

                    # Кнопка подтверждения создания несмотря на синонимы
                    # При клике вызывает функцию markSubmitButtonsToIgnoreValidation()
                    # которая добавляет класс force-ignore-validation ко всем submit-кнопкам.
                    # Вотчер видит этот класс и добавляет onclick обработчик к кнопкам
                    # для добавления GET параметра ignore_validate=1 перед отправкой формы.
                    # Весь JS код находится в form-field-watcher.js для чистоты и переиспользования.
                    confirmation_button = '''
                    <div class="confirmation-button-container">
                      <button type="button" onclick="markSubmitButtonsToIgnoreValidation();">
                        <big>Я проверил и уверен!</big><br/>
                        Сохранить, несмотря на синонимы.<br/>
                        <i>Точные совпадения в синонимах других записей будут удалены.</i>
                      </button>
                      <em>Теперь нажмите стандартные кнопки сохранения снизу, чтобы сохранить.</em>
                    </div>
                    '''

                    raise ValidationError(
                        mark_safe(
                            f"ВНИМАНИЕ: Найдено совпадение в синонимах! "
                            f"Проверьте {dup_list} "
                            f"или используйте синонимы из найденной записи."
                            f"{confirmation_button}"
                        )
                    )

            case ValidateMatchType.EXACT_SYNONYM_MATCH:
                # ОБРАБОТКА СОВПАДЕНИЙ СИНОНИМОВ (синонимы текущей записи совпадают с синонимами других)
                # Проверяем: это запрос с подтверждением (ignore_validate=1) или первоначальная проверка?
                if request and request.GET.get('ignore_validate') == '1':
                    # РЕЖИМ: ОБХОД ВАЛИДАЦИИ (пользователь нажал красную кнопку и подтвердил "Я проверил и уверен!")
                    # Тихо удаляем из других записей те синонимы, которые совпадают с синонимами текущей.
                    remove_conflicting_synonyms_from_duplicates(
                        duplicates_queryset,
                        metadata_field_name,
                        metadata_dict.get(KEY_SYNONYM) or [],  # Удаляем все синонимы текущей записи
                    )
                    # Выходим без ошибки в админку, т.к. пользователь "проверил и уверен!"
                    # Конфликтующие синонимы удалены, запись сохранится нормально
                    return

                else:
                    # РЕЖИМ: ПЕРВОНАЧАЛЬНАЯ ПРОВЕРКА
                    # Обрабатываем на Python (без доп запросов к БД) - duplicates_queryset уже в памяти
                    # Для каждого синонима текущей записи ищем, в каких записях он есть

                    # Собираем текущие синонимы с нормализацией
                    current_synonyms_list = metadata_dict.get(KEY_SYNONYM) or []

                    # Строим словарь: {нормализованный синоним: {оригинальный синоним, запись1, запись2, ...}}
                    synonym_to_records = {}
                    for current_syn in current_synonyms_list:
                        normalized_syn = normalize_string(current_syn)
                        if normalized_syn not in synonym_to_records:
                            synonym_to_records[normalized_syn] = {
                                'original': current_syn,
                                'records': []
                            }

                        # Ищем этот синоним в метаданных других записей
                        for dup in duplicates_queryset:
                            dup_metadata = getattr(dup, metadata_field_name) or {}
                            dup_synonyms = dup_metadata.get(KEY_SYNONYM) or []

                            # Проверяем: есть ли текущий синоним в синонимах этой записи
                            for dup_syn in dup_synonyms:
                                if normalize_string(dup_syn) == normalized_syn:
                                    # Добавляем запись если ее еще нет в списке
                                    rel_url = f"../{dup.pk}/change/" if form_instance.instance.pk is None else f"../../{dup.pk}/change/"
                                    dup_value = getattr(dup, main_field_name, '?')
                                    dup_link = f"<a href='{rel_url}'>#{dup.pk} '{dup_value}'</a>"

                                    # Проверяем что эту запись еще не добавили для этого синонима
                                    if dup_link not in synonym_to_records[normalized_syn]['records']:
                                        synonym_to_records[normalized_syn]['records'].append(dup_link)
                                    break

                    # Строим текст с детализацией по каждому синониму
                    synonym_details = []
                    for normalized_syn, info in synonym_to_records.items():
                        original_syn = info['original']
                        records = info['records']
                        if records:  # Только если этот синоним найден в других записях
                            records_html = ", ".join(records)
                            synonym_details.append(f"<b>'{original_syn}'</b> найден в: {records_html}")

                    # Объединяем все детали в один список
                    synonym_details_text = "<br/>".join(synonym_details) if synonym_details else "Синонимы не найдены"

                    # Кнопка подтверждения создания несмотря на совпадение синонимов
                    confirmation_button = '''
                    <div class="confirmation-button-container">
                      <button type="button" onclick="markSubmitButtonsToIgnoreValidation();">
                        <big>Я проверил и уверен!</big><br/>
                        Сохранить, несмотря на совпадение синонимов.<br/>
                        <i>Совпадающие синонимы в других записях будут удалены.</i>
                      </button>
                      <em>Теперь нажмите стандартные кнопки сохранения снизу, чтобы сохранить.</em>
                    </div>
                    '''

                    raise ValidationError(
                        mark_safe(
                            f"ВНИМАНИЕ: Найдено совпадение синонимов!<br/>"
                            f"Синонимы совпадают:<br/>{synonym_details_text}<br/>"
                            f"Проверьте и уточните синонимы если нужно."
                            f"{confirmation_button}"
                        )
                    )

            case _:
                # Неизвестный или не обработанный тип совпадения
                # В будущем сюда можно добавить логирование неожиданных типов
                pass


def validate_and_raise_for_duplicates(
    instance,
    main_field_name: str,
    metadata_field_name: str,
) -> None:
    """
    Валидирует экземпляр модели на дубликаты и выбрасывает ValidationError если найдены.

    Используется в переопределённых методах save() моделей для проверки дубликатов
    перед сохранением. Получает все необходимые данные из экземпляра модели.

    УНИВЕРСАЛЬНЫЙ ХЕЛПЕР — работает для любых моделей (TbLabel, TbArtist, TbMusicStyle и т.д.)

    Args:
        instance: Экземпляр модели (self из save методе). Обязателен!
        main_field_name: Имя основного поля модели ('s_label', 's_artist', 's_style_name'). Обязателен!
        metadata_field_name: Имя поля метаданных ('j_label_metadata', 'j_artist_metadata'). Обязателен!

    Raises:
        AttributeError: Если указанные поля не существуют в модели
        ValidationError: Если найдены совпадения (дубликаты)

    Пример использования в TbLabel.save():
        def save(self, *args, **kwargs):
            # Валидируем ДО работы с данными!
            validate_and_raise_for_duplicates(self, 's_label', 'j_label_metadata')
            # ... остальная логика save()
            super().save(*args, **kwargs)

    Пример использования в TbArtist.save():
        def save(self, *args, **kwargs):
            validate_and_raise_for_duplicates(self, 's_artist', 'j_artist_metadata')
            # ... остальная логика save()
            super().save(*args, **kwargs)
    """
    # Получаем класс модели из экземпляра
    model_class = instance.__class__

    # Проверяем, что указанные поля существуют в модели
    for field_name in [main_field_name, metadata_field_name]:
        if not hasattr(instance, field_name):
            raise AttributeError(
                f"{model_class.__name__} instance has no attribute '{field_name}'. "
                f"Check that main_field_name and metadata_field_name are correct."
            )

    main_field_value = getattr(instance, main_field_name)

    # Вызываем основной валидатор дубликатов
    duplicates_result = validate_for_duplicates(
        model_class=model_class,
        instance_pk=instance.pk,  # None для новых записей
        main_field_value=main_field_value,                     # ЗНАЧЕНИЕ основного поля модели
        metadata_dict=getattr(instance, metadata_field_name),  # ЗНАЧЕНИЕ поля метаданных модели
        main_field_name=main_field_name,            # ИМЯ основного поля модели
        metadata_field_name=metadata_field_name,    # ИМЯ поля метаданных модели
    )

    # Обрабатываем результаты валидации через match-case
    match duplicates_result.get(VALIDATE_KEY__MATCH_TYPE):
        case ValidateMatchType.IS_DUPLICATE:
            # Точный дубликат найден - это критическая ошибка!
            # На уровне save() мы НИКОГДА не должны позволить точные дубликаты.
            model_name = model_class.__name__
            dup_pks = [dup.pk for dup in duplicates_result[VALIDATE_KEY__VALUE]]
            raise ValidationError(
                f"{model_name}.save(): КРИТИЧЕСКАЯ ОШИБКА! Дубликат '{main_field_value}' уже существует. "
                f"PK дубликатов: {dup_pks}. Сохранение отменено!"
            )

        case ValidateMatchType.FIND_IN_SYNONYM:
            # Совпадение в синонимах найдено - консервативный подход: всегда блокируем
            # Это вызвано вне админки (парсер, API, батник, bulk операции и т.д.)
            # где нет пользовательского интерфейса для принятия решения.
            #
            # TODO: В будущем когда будет парсер/брокер очереди принятия решений:
            # - Сохранить состояние экземпляра в очередь (сохранить в брокер)
            # - Уведомить пользователя/модератора о конфликте
            # - Ожидать решения пользователя (удалить из синонимов или объединить записи)
            # - После решения пользователя: автоматически удалить синонимы и пересохранить
            #
            # На данный момент: просто блокируем и требуем ручного разрешения конфликта.
            model_name = model_class.__name__
            dup_pks = [dup.pk for dup in duplicates_result[VALIDATE_KEY__VALUE]]
            raise ValidationError(
                f"{model_name}.save(): Найдено совпадение в синонимах! "
                f"Разрешите на уровне админки или подтвердите решение. "
                f"PK конфликтующих записей: {dup_pks}"
            )

        case ValidateMatchType.EXACT_SYNONYM_MATCH:
            # Совпадение синонимов найдено - синонимы в текущей записи совпадают с синонимами других записей
            # Теритически, это может произойти вне админки (парсер, API, батник, bulk операции и т.д.)
            # но синонимы определяются и редактируются только в админке (через интерфейс), парсеры их генерировать
            # не должны (и не будут). Блокируем (может быть в будущем сохранить состояние в брокере, но вряд ли).
            model_name = model_class.__name__
            dup_pks = [dup.pk for dup in duplicates_result[VALIDATE_KEY__VALUE]]
            raise ValidationError(
                f"{model_name}.save(): Найдено совпадение синонимов! "
                f"Синонимы текущей записи совпадают с синонимами других записей. "
                f"Разрешите конфликт в админке. "
                f"PK конфликтующих записей: {dup_pks}"
            )

        case _:
            # Неизвестный тип совпадения или дубликатов нет
            # Это нормальная ситуация - логируем только если что-то странное
            if VALIDATE_KEY__MATCH_TYPE in duplicates_result:
                model_name = model_class.__name__
                logger.warning(
                    f"{model_name}.save(): Неизвестный тип совпадения: "
                    f"{duplicates_result.get(VALIDATE_KEY__MATCH_TYPE)}"
                )


def update_synonyms_in_metadata(
    instance,
    main_field_name: str,
    metadata_field_name: str,
) -> None:
    """
    Обновляет список синонимов в метаданных экземпляра модели.

    Универсальный хелпер для управления синонимами во всех моделях (TbLabel, TbArtist, TbMusicStyle и т.д.)

    Логика:
    - При создании новой записи: добавляет текущее значение поля в SYNONYM
    - При редактировании: если значение поля изменилось, добавляет ОБА (старое и новое) в SYNONYM
    - Очищает дубликаты в списке синонимов, сохраняя порядок
    - Использует KEY_SYNONYM из settings как ключ в metadata словаре

    Args:
        instance: Экземпляр модели (self из save методе). Обязателен!
        main_field_name: Имя основного поля ('s_label', 's_artist', 's_style_name'). Обязателен!
        metadata_field_name: Имя поля метаданных ('j_label_metadata', 'j_artist_metadata'). Обязателен!

    Пример использования в TbLabel.save():
        def save(self, *args, **kwargs):
            validate_and_raise_for_duplicates(self, 's_label', 'j_label_metadata')
            update_synonyms_in_metadata(self, 's_label', 'j_label_metadata')
            # ... остальная логика save()
            super().save(*args, **kwargs)

    Пример использования в TbArtist.save():
        def save(self, *args, **kwargs):
            validate_and_raise_for_duplicates(self, 's_artist', 'j_artist_metadata')
            update_synonyms_in_metadata(self, 's_artist', 'j_artist_metadata')
            # ... остальная логика save()
            super().save(*args, **kwargs)
    """
    model_class = instance.__class__

    # Проверяем, что указанные поля существуют в модели
    for field_name in [main_field_name, metadata_field_name]:
        if not hasattr(instance, field_name):
            raise AttributeError(
                f"{model_class.__name__} instance has no attribute '{field_name}'. "
                f"Check that main_field_name and metadata_field_name are correct."
            )

    # ===== ОПРЕДЕЛЯЕМ, ЭТО СОЗДАНИЕ ИЛИ РЕДАКТИРОВАНИЕ =====
    # Получаем текущее значение основного поля
    current_field_value = getattr(instance, main_field_name)

    # Определяем новая ли это запись или обновление
    is_new = instance.pk is None

    # Получаем старое значение поля (для редактирования)
    old_field_value = None
    if not is_new:
        try:
            old_instance = model_class.objects.get(pk=instance.pk)
            old_field_value = getattr(old_instance, main_field_name)
        except model_class.DoesNotExist:
            # На случай если что-то пошло не так, считаем это новым
            is_new = True

    # ===== ИНИЦИАЛИЗИРУЕМ МЕТАДАННЫЕ =====
    # Инициализируем metadata если оно пусто
    metadata_dict = getattr(instance, metadata_field_name)
    if not metadata_dict:
        metadata_dict = {}
        setattr(instance, metadata_field_name, metadata_dict)

    # Убеждаемся, что ключ 'SYNONYM' существует и это список
    if KEY_SYNONYM not in metadata_dict or not isinstance(metadata_dict[KEY_SYNONYM], list):
        metadata_dict[KEY_SYNONYM] = []

    # ===== ДОБАВЛЯЕМ СИНОНИМЫ =====
    # Добавляем синонимы при создании ИЛИ если значение поля изменилось
    if is_new or old_field_value != current_field_value:
        # Если поле было обновлено и значение изменилось - добавляем старое значение
        if old_field_value and old_field_value not in metadata_dict[KEY_SYNONYM]:
            metadata_dict[KEY_SYNONYM].append(old_field_value)

        # Добавляем текущее значение если его еще нет в синонимах
        if current_field_value not in metadata_dict[KEY_SYNONYM]:
            metadata_dict[KEY_SYNONYM].append(current_field_value)

    # ===== ОЧИЩАЕМ ДУБЛИКАТЫ =====
    # Удаляем дубликаты в списке синонимов, сохраняя порядок
    # (может случиться если пользователь вручную редактировал метаданные)
    if KEY_SYNONYM in metadata_dict and isinstance(metadata_dict[KEY_SYNONYM], list):
        metadata_dict[KEY_SYNONYM] = list(dict.fromkeys(metadata_dict[KEY_SYNONYM]))

    # ===== СООБЩАЕМ DJANGO ЧТО ПОЛЕ ИЗМЕНИЛОСЬ =====
    # Для JSONField нужно явно сообщить что мы изменили содержимое
    # иначе Django может не сохранить изменения
    setattr(instance, metadata_field_name, metadata_dict)

