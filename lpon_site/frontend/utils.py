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
from lpon_site.settings import (
    SLUG_MAX_LENGTH,
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

    # ПРОВЕРКА 1: EXACT MATCH (точное совпадение основного поля)
    # Ищем: есть ли другая запись с точно таким же main_field_value?
    filter_kwargs = {f"{main_field_name}__exact": normalized_main_value}
    exact_matches = model_class.objects.filter(**filter_kwargs)
    if instance_pk is not None:
        # При редактировании, чтобы не найти "самого себя" как дубликат, исключаем текущую запись из поиска
        exact_matches = exact_matches.exclude(pk=instance_pk)
    if exact_matches.exists():
        duplicates_found.update({
            VALIDATE_KEY__MATCH_TYPE: ValidateMatchType.IS_DUPLICATE,
            VALIDATE_KEY__VALUE: exact_matches,
        })
        return duplicates_found
    # for other_record in exact_matches:
    #     other_main_value = str(getattr(other_record, main_field_name, ""))
    #     duplicates_found[VALIDATE_KEY__VALUE].append({
    #         MATCH__KEY_PK: other_record.pk,
    #         's_label': other_main_value,
    #         'matched_value': normalized_main_value,
    #     })

    # Когда все проверки прошли -- возвращаем пустой словарь
    return duplicates_found


def validate_entity_for_admin_form(form_instance, cleaned_data,
                                   main_field_name='s_label',
                                   metadata_field_name='j_label_metadata'):
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

    Raises:
        ValidationError: Если найдены совпадения (дубликаты)

    Пример использования в LabelAdminForm:
        def clean(self):
            cleaned_data = super().clean()
            validate_entity_for_admin_form(
                self,
                cleaned_data,
                main_field_name='s_label',
                metadata_field_name='j_label_metadata'
            )
            return cleaned_data
    """
    from django.urls import reverse
    from django.utils.html import mark_safe

    # Получаем класс модели из метаинформации формы
    model_class = form_instance.Meta.model

    # Получаем значения из формы
    main_field_value = cleaned_data.get(main_field_name)
    metadata_dict = cleaned_data.get(metadata_field_name) or {}

    # Если основное поле не заполнено, пропускаем валидацию
    if not main_field_value:
        return

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

        # Используем match-case для удобной обработки разных типов совпадений
        # С Enum вместо магических чисел код становится самодокументируемым
        # В будущем легко добавить новые типы: ValidateMatchType.PARTIAL_MATCH = 2 и т.д.
        match match_type:
            case ValidateMatchType.IS_DUPLICATE:
                # ОБРАБОТКА ТОЧНЫХ ДУБЛИКАТОВ
                # Строим ссылки на найденные дубликаты для быстрого перехода в админке
                dup_links = []
                for dup in duplicates_queryset:
                    # Получаем admin URL автоматически через Django meta
                    model_name = model_class._meta.model_name
                    app_label = model_class._meta.app_label
                    admin_url = reverse(f'admin:{app_label}_{model_name}_change', args=[dup.pk])
                    # Делаем ссылку относительной (убираем начальный слэш для универсальности)
                    rel_url = admin_url.lstrip('/')

                    # Получаем значение основного поля из дубликата
                    dup_value = getattr(dup, main_field_name, '?')
                    dup_links.append(f"<big><a href='{rel_url}'>#{dup.pk} '{dup_value}'</a></big>")

                # Объединяем все найденные дубликаты в один список
                dup_list = ", ".join(dup_links)

                # Выбрасываем ValidationError с HTML ссылками на дубликаты
                raise ValidationError(
                    mark_safe(
                        f"ОШИБКА: Найдено совпадение! "
                        f"Отредактируйте {dup_list} "
                        f"или используйте синонимы из найденной записи."
                    )
                )

            case _:
                # Неизвестный или не обработанный тип совпадения
                # В будущем сюда можно добавить логирование неожиданных типов
                pass

