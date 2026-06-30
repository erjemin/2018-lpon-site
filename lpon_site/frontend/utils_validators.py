# frontend/utils_validators.py
# Функции валидации для моделей (проверка дубликатов, синонимов и т.д.)

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Union
from django.core.exceptions import ValidationError
from django.db.models import QuerySet, Model
from django.db.models.expressions import RawSQL
from django.utils.html import mark_safe
from django.http import HttpRequest
from django.forms import ModelForm
from django.contrib import messages
from lpon_site.settings import (
    KEY_SYNONYM,
    VALIDATE_KEY__MATCH_TYPE, VALIDATE_KEY__MODEL, VALIDATE_KEY__VALUE,
    ValidateMatchType, MIN_SYNONYM_WORD_LENGTH
)


# Импортируем функции нормализации из основного модуля utils
from .utils import normalize_string, super_normalize_string

logger = logging.getLogger(__name__)


def validate_for_duplicates(
    model_class: type[Model],
    instance_pk: int | None,
    main_field_value: str,
    metadata_dict: dict | None,
    main_field_name: str | None = None,
    metadata_field_name: str | None = None,
) -> Dict[str, Any]:
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

    # ПОДГОТОВКА 1: Инициализируем переменную для отслеживания минимальной длины синонимов
    # Используется для адаптивной фильтрации при PARTIAL_MATCH на очень коротких названиях
    # (например, "B'Z", "XL", которые после супер-нормализации становятся еще короче).
    # Начинаем с MIN_SYNONYM_WORD_LENGTH, будет переопределяться по необходимости.
    effective_min_word_len = MIN_SYNONYM_WORD_LENGTH

    # ПОДГОТОВКА 2: Получаем базовый queryset (все записи кроме текущей, если редактируем)
    # Это ленивый запрос - запрос выполнится, только когда мы применим фильтры
    records_to_check = model_class.objects.all()
    if instance_pk is not None:
        # При редактировании исключаем текущую запись из поиска, чтобы не найти "самого себя"
        records_to_check = records_to_check.exclude(pk=instance_pk)

    # ПРОВЕРКА 1: EXACT MATCH (точное совпадение основного поля)
    # Ищем: есть ли другая запись с точно таким же main_field_value?
    # Используем RawSQL с LOWER() для case-insensitive сравнения нормализованных значений
    exact_matches = records_to_check.annotate(
        has_exact_match=RawSQL(
            f"LOWER({main_field_name}) = %s",
            (normalized_main_value,)
        )
    ).filter(has_exact_match=True)

    if exact_matches.exists():
        duplicates_found.update({  # type: ignore
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
    # LOWER() используется т.к. в БД могут быть строки в любом регистре, но нормализованное значение в нижнем
    synonym_matches = records_to_check.annotate(
        has_synonym=RawSQL(
            f"""
            EXISTS (
                SELECT 1 FROM json_each({metadata_field_name}, '$.{KEY_SYNONYM}')
                WHERE LOWER(json_each.value) = %s
            )
            """,
            (normalized_main_value,)
        )
     ).filter(has_synonym=True)

    # Если найдены совпадения в синонимах - возвращаем все найденные записи
    if synonym_matches.exists():
        duplicates_found.update({  # type: ignore
            VALIDATE_KEY__MATCH_TYPE: ValidateMatchType.FIND_IN_SYNONYM,
            VALIDATE_KEY__VALUE: synonym_matches,
        })
        return duplicates_found

    # Подготавливаем единый список всех значений для анализа:
    # основное поле + все синонимы из метаданных
    # Этот список переиспользуется на этапах 3 и 4, избегая дублирования логики
    raw_values_to_analyze = [main_field_value]
    if KEY_SYNONYM in metadata_dict and isinstance(metadata_dict[KEY_SYNONYM], list):
        raw_values_to_analyze.extend(metadata_dict[KEY_SYNONYM])

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

        # Удаляем дубликаты синонимов, сохраняя порядок
        # (может быть пользователь вручную добавил одно и то же несколько раз)
        current_synonyms = list(dict.fromkeys(current_synonyms))

        # Определяем минимальную длину синонимов из текущей записи
        # (для адаптивной фильтрации при PARTIAL_MATCH на очень коротких названиях)
        # Учитываем как синонимы, так и основное значение поля (normalized_main_value)
        # которое может быть коротким и уже совпадало на этапе 2
        all_values_to_check = current_synonyms + [normalized_main_value]
        min_syn_len = min(len(val) for val in all_values_to_check if val)
        effective_min_word_len = min(effective_min_word_len, min_syn_len)

        # Если есть синонимы для проверки
        if current_synonyms:
            # Строим RawSQL условие для поиска любого из наших синонимов в JSON массиве других записей
            # Используем один аннотированный queryset со всеми условиями OR для поиска всех конфликтов сразу
            # LOWER() используется т.к. в БД могут быть строки в любом регистре, но нормализованные значения в нижнем
            synonym_query_parts = []
            query_params = []
            for normalized_synonym in current_synonyms:
                synonym_query_parts.append(
                    f"EXISTS (SELECT 1 FROM json_each({metadata_field_name}, '$.{KEY_SYNONYM}') WHERE LOWER(json_each.value) = %s)"
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
                duplicates_found.update({  # type: ignore
                    VALIDATE_KEY__MATCH_TYPE: ValidateMatchType.EXACT_SYNONYM_MATCH,
                    VALIDATE_KEY__VALUE: synonym_in_others,
                })
                return duplicates_found

    # ПРОВЕРКА 4: PARTIAL_MATCH (частичное совпадение слов текущей записи с другими)
    # Ищем: есть ли значимые слова (> MIN_SYNONYM_WORD_LENGTH) из текущей записи и синонимов
    # в основных полях и синонимах других записей?
    # Пример: "The Beatles" содержит слово "beatles" (5 букв > 3),
    # "Beatles, The" тоже содержит "beatles", это схожесть (предупреждение, не блокировка)
    #
    # Собираем все слова из main_field_value и синонимов текущей записи
    all_current_words = set()

    # Переиспользуем raw_values_to_analyze (основное поле + синонимы из метаданных),
    # которое уже подготовили на этапе 3, чтобы избежать дублирования логики.
    # Обрабатываем каждое значение: супер-нормализуем и собираем слова
    for value in raw_values_to_analyze:
        # Используем супер-нормализатор для удаления пунктуации и спецсимволов
        normalized_value = super_normalize_string(value)
        value_words = re.split(r'\s+', normalized_value)
        for word in value_words:
            # Собираем ВСЕ слова (даже очень короткие) для отслеживания
            if word:  # Только непустые
                all_current_words.add(word)
                # Отслеживаем минимальную длину встреченных слов (независимо от MIN_SYNONYM_WORD_LENGTH)
                effective_min_word_len = min(effective_min_word_len, len(word))

    # Если собрали значимые слова - ищем их в других записях
    if all_current_words:
        # Строим RawSQL условие для поиска любого из наших слов в main_field_name других записей
        # или в синонимах других записей (как в main_field_name, так и в JSON)
        word_search_conditions = []
        word_search_params = []

        # Условия поиска в основном поле (case-insensitive)
        for word in all_current_words:
            # Фильтруем слова по эффективной минимальной длине (может быть меньше MIN_SYNONYM_WORD_LENGTH
            # если встречались короткие синонимы, например, "B'Z" → "B Z")
            if len(word) >= effective_min_word_len:
                # Ищем слово как подстроку в основном поле (окружено пунктуацией/пробелами или в начале/конце)
                # Используем LIKE с wildcard
                word_search_conditions.append(
                    f"LOWER({main_field_name}) LIKE %s"
                )
                word_search_params.append(f"%{word}%")

        # Условия поиска в синонимах (в JSON массиве)
        for word in all_current_words:
            # Фильтруем слова по эффективной минимальной длине
            if len(word) >= effective_min_word_len:
                word_search_conditions.append(
                    f"""EXISTS (
                        SELECT 1 FROM json_each({metadata_field_name}, '$.{KEY_SYNONYM}')
                        WHERE LOWER(json_each.value) LIKE %s
                    )"""
                )
                word_search_params.append(f"%{word}%")

        # Объединяем условия через OR - ищем хотя бы одно совпадение по словам
        partial_matches = records_to_check.annotate(
            has_partial_match=RawSQL(
                " OR ".join(word_search_conditions),
                word_search_params
            )
        ).filter(has_partial_match=True).distinct()

        # Если найдены записи с частичным совпадением - возвращаем их
        if partial_matches.exists():
            # Определяем тип совпадения: если были найдены очень короткие слова (< MIN_SYNONYM_WORD_LENGTH),
            # помечаем это как PARTIAL_MATCH__RISK_SHORT_WORDS для специального обращения в админке
            match_type = ValidateMatchType.PARTIAL_MATCH
            if effective_min_word_len < MIN_SYNONYM_WORD_LENGTH:
                match_type = ValidateMatchType.PARTIAL_MATCH__RISK_SHORT_WORDS

            duplicates_found.update({  # type: ignore
                VALIDATE_KEY__MATCH_TYPE: match_type,
                VALIDATE_KEY__VALUE: partial_matches,
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


def build_search_report(
    cleaned_data: dict,
    main_field_name: str,
    metadata_dict: dict,
    duplicates_queryset: QuerySet,
    metadata_field_name: str,
) -> str:
    """
    Собирает поисковые слова из основного поля и синонимов текущей записи,
    затем формирует красивый отчет о совпадениях этих слов в дубликатах.

    Универсальная функция, используется для кейсов:
    - IS_DUPLICATE: для поиска совпадений слов в других записях
    - FIND_IN_SYNONYM: основное поле совпадает с синонимами других записей
    - PARTIAL_MATCH: слова совпадают (частичное совпадение)
    - PARTIAL_MATCH__RISK_SHORT_WORDS: частичное совпадение с короткими словами

    Args:
        cleaned_data: Очищенные данные формы
        main_field_name: Имя основного поля ('s_label', 's_artist', 's_style_name')
        metadata_dict: Словарь с метаданными текущей записи
        duplicates_queryset: QuerySet записей, в которых нашли совпадения
        metadata_field_name: Имя поля метаданных ('j_label_metadata', 'j_artist_metadata')

    Returns:
        str: HTML строка с отчетом о совпадениях со ссылками и выделением слов
    """
    # Инициализируем набор поисковых слов
    search_words = set()

    # Собираем слова из основного поля
    # Применяем супер-нормализацию (удаление пунктуации, спецсимволов)
    main_value_normalized = super_normalize_string(cleaned_data.get(main_field_name, ''))
    # Разбиваем на слова по пробельным символам
    search_words.update(re.split(r'\s+', main_value_normalized))

    # Собираем слова из синонимов метаданных
    metadata_synonyms = metadata_dict.get(KEY_SYNONYM) or []
    for synonym in metadata_synonyms:
        # Применяем супер-нормализацию к каждому синониму
        syn_normalized = super_normalize_string(synonym)
        # Добавляем все слова этого синонима в набор
        search_words.update(re.split(r'\s+', syn_normalized))

    # Удаляем пустые строки из набора слов
    # (они могут появиться при разбиении на пробелы)
    search_words.discard('')

    # ===== ФОРМИРОВАНИЕ ОТЧЕТА О СОВПАДЕНИЯХ =====
    # Собираем HTML отчет со списком найденных совпадений
    report_lines = []

    # Для каждого поискового слова (в алфавитном порядке)
    for search_word in sorted(search_words):
        matches_for_word = []

        # Проходим по всем найденным дубликатам
        for dup in duplicates_queryset:
            # Получаем основное поле этой записи
            main_field_value = getattr(dup, main_field_name, '')

            # Получаем метаданные и синонимы
            dup_metadata = getattr(dup, metadata_field_name) or {}
            dup_synonyms = dup_metadata.get(KEY_SYNONYM) or []

            # Ищем слово в основном поле и синонимах (case-insensitive)
            found_locations = []
            found_synonyms = []  # Собираем все найденные синонимы отдельно

            # Проверяем основное поле
            if main_field_value:
                # Ищем подстроку (LIKE поиск как в SQL) - case-insensitive
                # lambda функция выделяет найденное слово в ВЕРХНЕМ регистре для лучшей акцентуации
                # m.group(0) содержит найденный текст, .upper() переводит его в верхний регистр
                # Используем простой regex без \b границ для поиска подстрок (как LIKE в SQL)
                highlighted_main = re.sub(
                    re.escape(search_word),
                    lambda m: f'<u>{m.group(0).upper()}</u>',  # Выделяем в верхнем регистре
                    main_field_value,
                    flags=re.IGNORECASE
                )
                if highlighted_main != main_field_value:  # Совпадение найдено
                    found_locations.append(f"основное поле: &quot;{highlighted_main}&quot;")

            # Проверяем синонимы
            for synonym in dup_synonyms:
                if synonym:
                    # Ищем подстроку в синониме (LIKE поиск как в SQL) - case-insensitive
                    # lambda функция выделяет найденное слово в ВЕРХНЕМ регистре для лучшей акцентуации
                    # Используем простой regex без \b границ для поиска подстрок (как LIKE в SQL)
                    highlighted_syn = re.sub(
                        re.escape(search_word),
                        lambda m: f'<u>{m.group(0).upper()}</u>',  # Выделяем в верхнем регистре
                        synonym,
                        flags=re.IGNORECASE
                    )
                    if highlighted_syn != synonym:  # Совпадение найдено
                        # Собираем синонимы в отдельный список вместо добавления по одному
                        found_synonyms.append(f"&quot;{highlighted_syn}&quot;")

            # Если найдены синонимы с совпадениями - добавляем их одной строкой
            if found_synonyms:
                synonyms_html = ", ".join(found_synonyms)
                found_locations.append(f"синонимы: {synonyms_html}")

            # Если слово найдено в этой записи - добавляем в отчет
            if found_locations:
                rel_url = f"../{dup.pk}/change/"  # Относительная ссылка на запись
                dup_display_name = getattr(dup, main_field_name, '?')
                locations_html = ", ".join(found_locations)
                matches_for_word.append(
                    f"<a href='{rel_url}'>#{dup.pk} &quot;{dup_display_name}&quot;</a> → {locations_html}"
                )

        # Если слово найдено хотя бы в одной записи - добавляем строку в отчет
        if matches_for_word:
            # Формируем вложенный список для каждого найденного дубликата
            matches_items = "".join(
                f"<li>{match}</li>"
                for match in matches_for_word
            )
            report_lines.append(
                f"<li><b>{search_word}:</b> встречается в<br/>"
                f"  <ul>{matches_items}</ul>"
                f"</li>"
            )

    # Объединяем все строки в один HTML отчет с использованием списка
    if report_lines:
        return f"<ul>{''.join(report_lines)}</ul>"
    else:
        return "Совпадения не найдены"


def validate_entity_for_admin_form(
    form_instance: ModelForm,
    cleaned_data: dict,
    main_field_name: str,
    metadata_field_name: str,
    request: HttpRequest | None = None,
) -> None:
    """
    Универсальный валидатор для админских форм.

    Проверяет сущность на совпадения (дубликаты) с уже существующими записями.
    Выбрасывает ValidationError с кликабельными ссылками на найденные дубликаты.

    Используется во всех админских forms: LabelAdminForm, ArtistAdminForm, MusicStyleAdminForm и т.д.

    Args:
        form_instance: Экземпляр формы (self из clean методе). Обязателен!
        cleaned_data: Очищенные данные формы. Обязателен!
        main_field_name: Имя основного поля модели. ОБЯЗАТЕЛЕН!
            Примеры: 's_label' (для TbLabel), 's_artist' (для TbArtist), 's_style_name' (для TbMusicStyle)
            Если поле не существует в модели, будет выброшено AttributeError.
        metadata_field_name: Имя поля метаданных модели. ОБЯЗАТЕЛЕН!
            Примеры: 'j_label_metadata', 'j_artist_metadata', 'j_style_synonyms'
            Если поле не существует в модели, будет выброшено AttributeError.
        request: HTTP request объект (опционально, используется для проверки GET параметра ignore_validate)

    Raises:
        AttributeError: Если main_field_name или metadata_field_name не существуют в модели
        ValidationError: Если найдены совпадения (дубликаты) и GET параметр не установлен

    Пример использования в LabelAdminForm:
        def clean(self):
            cleaned_data = super().clean()
            validate_entity_for_admin_form(
                self,
                cleaned_data,
                main_field_name='s_label',  # ОБЯЗАТЕЛЕН!
                metadata_field_name='j_label_metadata',  # ОБЯЗАТЕЛЕН!
                request=self.request if hasattr(self, 'request') else None,
            )
            return cleaned_data
    """

    # Получаем класс модели из метаинформации формы
    model_class = form_instance.Meta.model  # type: ignore

    # === ВАЛИДАЦИЯ ПАРАМЕТРОВ ===

    # Проверяем, что поля существуют в модели
    for field_name in [main_field_name, metadata_field_name]:
        if not hasattr(model_class, field_name):
            raise AttributeError(
                f"Model '{model_class.__name__}' has no field '{field_name}'. "
                f"Please provide valid field names from the model."
            )

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
        main_field_value=str(main_field_value),  # type: ignore  # Преобразуем в строку (после проверки выше)
        metadata_dict=metadata_dict,
        main_field_name=main_field_name,
        metadata_field_name=metadata_field_name,
    )

    if VALIDATE_KEY__MATCH_TYPE not in result:
        return # Нет совпадений, продолжаем обработку формы

    # Обрабатываем результаты проверки в зависимости от типа найденного совпадения
    match_type = result[VALIDATE_KEY__MATCH_TYPE]
    duplicates_queryset = result[VALIDATE_KEY__VALUE]

    # Используем match-case для удобной обработки разных типов совпадений
    # С Enum вместо магических чисел код становится самодокументируемым
    # В будущем легко добавить новые типы: ValidateMatchType.PARTIAL_MATCH = 2 и т.д.
    match match_type:
        case ValidateMatchType.IS_DUPLICATE:
            # ОБРАБОТКА ТОЧНЫХ ДУБЛИКАТОВ
            # Формируем красивый отчет с выделением совпадений
            report_html = build_search_report(
                cleaned_data,
                main_field_name,
                metadata_dict,
                duplicates_queryset,
                metadata_field_name
            )

            # Для случая IS_DUPLICATE всегда выбрасываем ошибку, т.к. это критическая ситуация
            # и поле часто имеет unique=True на уровне модели.
            raise ValidationError(
                mark_safe(
                    f"ОШИБКА: Найдено ПОЛНОЕ совпадение!<br/>"
                    f"{report_html}<br/>"
                    f"Измените название или отредактируйте найденную запись."
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
                # Формируем красивый отчет с выделением совпадений
                report_html = build_search_report(
                    cleaned_data,
                    main_field_name,
                    metadata_dict,
                    duplicates_queryset,
                    metadata_field_name
                )

                # Кнопка подтверждения создания несмотря на синонимы
                # При клике вызывает функцию markSubmitButtonsToIgnoreValidation()
                # которая добавляет класс force-ignore-validation ко всем submit-кнопкам.
                # Вотчер видит этот класс и добавляет onclick обработчик к кнопкам
                # для добавления GET параметра ignore_validate=1 перед отправкой формы.
                # Весь JS код находится в form-field-watcher.js для чистоты и переиспользования.
                raise ValidationError(
                    mark_safe(
                        f"ВНИМАНИЕ: Найдено совпадение в синонимах! "
                        f"{report_html}<br/>"
                        f"Проверьте и уточните синонимы если нужно."
                        f"<div class=\"confirmation-button-container\">"
                        f"  <button type=\"button\" onclick=\"markSubmitButtonsToIgnoreValidation();\">"
                        f"    <big>Я проверил и уверен!</big><br/>"
                        f"    Сохранить, несмотря на синонимы.<br/>"
                        f"    <i>Точные совпадения в синонимах других записей будут удалены.</i>"
                        f"  </button>"
                        f"  <em>Теперь нажмите стандартные кнопки сохранения снизу, чтобы сохранить.</em>"
                        f"</div>"
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
                raise ValidationError(
                    mark_safe(
                        f"ВНИМАНИЕ: Найдено совпадение синонимов!<br/>"
                        f"Синонимы совпадают:<br/>{synonym_details_text}<br/>"
                        f"Проверьте и уточните синонимы если нужно."
                        f"<div class=\"confirmation-button-container\">"
                        f"  <button type=\"button\" onclick=\"markSubmitButtonsToIgnoreValidation();\">"
                        f"    <big>Я проверил и уверен!</big><br/>"
                        f"    Сохранить, несмотря на совпадение синонимов.<br/>"
                        f"    <i>Совпадающие синонимы в других записях будут удалены.</i>"
                        f"  </button>"
                        f"  <em>Теперь нажмите стандартные кнопки сохранения снизу, чтобы сохранить.</em>"
                        f"</div>"
                    )
                )

        case ValidateMatchType.PARTIAL_MATCH:
            # ОБРАБОТКА ЧАСТИЧНЫХ СОВПАДЕНИЙ (слова совпадают)
            # Это просто схожесть, не критично. Показываем предупреждение, но не блокируем сохранение.
            # При подтверждении просто сохраняем без каких-либо изменений в других записях.

            if request and request.GET.get('ignore_validate') == '1':
                # РЕЖИМ: ОБХОД ВАЛИДАЦИИ (пользователь подтвердил что ознакомлен)
                # Тихо сохраняем запись, ничего не меняя в других записях
                return

            else:
                # РЕЖИМ: ПЕРВОНАЧАЛЬНАЯ ПРОВЕРКА
                # Показываем пользователю информативное предупреждение о схожести
                # Используем вспомогательную функцию для сбора слов и формирования отчета
                report_html = build_search_report(
                    cleaned_data,
                    main_field_name,
                    metadata_dict,
                    duplicates_queryset,
                    metadata_field_name
                )

                # Кнопка для игнорирования предупреждения (без критичности)
                raise ValidationError(
                    mark_safe(
                        f"ИНФОРМАЦИЯ: Найдены похожие записи со схожими словами!<br/>"
                        f"{report_html}<br/>"
                        f"Это просто информация, не ошибка. Но неточности на сайте могут рассмешить"
                        f" (или огорчить) пользователей."
                        f"<div class=\"confirmation-button-container\">"
                        f"  <button type=\"button\" onclick=\"markSubmitButtonsToIgnoreValidation();\">"
                        f"    <big>OK, Я ПРОВЕРИЛ. ПРОБЛЕМ НЕ БУДЕТ</big><br/>"
                        f"    Сохранить запись<br/>"
                        f"    <i>Я уверен в своих действиях.</i>"
                        f"  </button>"
                        f"  <em>Теперь нажмите стандартные кнопки сохранения снизу, чтобы сохранить.</em>"
                        f"</div>"
                    )
                )

        case ValidateMatchType.PARTIAL_MATCH__RISK_SHORT_WORDS:
            # ОБРАБОТКА ЧАСТИЧНЫХ СОВПАДЕНИЙ С ВЫСОКИМ РИСКОМ (очень короткие слова/синонимы)
            # Найдены совпадения, но среди слов есть очень короткие (< MIN_SYNONYM_WORD_LENGTH)
            # Это может быть как вероятное совпадение (B'Z, XL) так и ложное срабатывание (А, И)
            # Показываем ещё более серьезное предупреждение о необходимости проверки

            if request and request.GET.get('ignore_validate') == '1':
                # РЕЖИМ: ОБХОД ВАЛИДАЦИИ (пользователь подтвердил что ознакомлен с рисками)
                # Тихо сохраняем запись, ничего не меняя в других записях
                return

            else:
                # РЕЖИМ: ПЕРВОНАЧАЛЬНАЯ ПРОВЕРКА
                # Собираем поисковые слова для отчета (используются для выделения в отчете)
                # Используем вспомогательную функцию для сбора слов и формирования отчета
                report_html = build_search_report(
                    cleaned_data,
                    main_field_name,
                    metadata_dict,
                    duplicates_queryset,
                    metadata_field_name
                )

                # Кнопка для подтверждения с указанием на риск
                raise ValidationError(
                    mark_safe(
                        f"ВНИМАНИЕ: ВЫСОКИЙ РИСК ОШИБКИ! Найдены похожие записи с ОЧЕНЬ КОРОТКИМИ словами!<br/>"
                        f"{report_html}<br/>"
                        f"Совпадения могут быть двухбуквенными и даже однобуквенными словами (например:"
                        f" \"B'Z\" → \"B Z\" или \"R&B\" → \"R B\" ). ОЧЕНЬ ВЕЛИК РИСК ложных срабатываний!"
                        f"<div class=\"confirmation-button-container\">"
                        f"  <button type=\"button\" onclick=\"markSubmitButtonsToIgnoreValidation();\">"
                        f"    <big>ВНИМАНИЕ: ВЫСОКИЙ РИСК!</big><br/>"
                        f"    Я всё проверил и уверен в своих действиях.<br/>"
                        f"    <i>Очень короткие слова (символов менее {MIN_SYNONYM_WORD_LENGTH}), подтверждаю!</i>"
                        f"  </button>"
                        f"  <em>Теперь нажмите стандартные кнопки сохранения снизу, чтобы сохранить.</em>"
                        f"</div>"
                    )
                )

        case _:
            # Неизвестный или не обработанный тип совпадения
            # В будущем сюда можно добавить логирование неожиданных типов
            pass

    return


def validate_and_raise_for_duplicates(
    instance: Model,
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
            # Совпадение синонимов найдено - синонимы текущей записи совпадают с синонимами других записей
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

        case ValidateMatchType.PARTIAL_MATCH:
            # Частичное совпадение по словам найдено - это просто предупреждение (warning)
            # Не блокируем, просто логируем для информации
            # Парсеры/батники могут работать с такими данными без ограничений
            model_name = model_class.__name__
            dup_pks = [dup.pk for dup in duplicates_result[VALIDATE_KEY__VALUE]]
            logger.info(
                f"{model_name}.save(): Найдено частичное совпадение по словам. "
                f"PK записей с похожими названиями: {dup_pks}"
            )

        case ValidateMatchType.PARTIAL_MATCH__RISK_SHORT_WORDS:
            # Частичное совпадение, но с очень короткими словами (< MIN_SYNONYM_WORD_LENGTH)
            # Повышенный риск ложных срабатываний, но все равно это предупреждение (warning)
            # Не блокируем, просто логируем с более высоким приоритетом
            # Администраторы могут обратить внимание на такие случаи
            model_name = model_class.__name__
            dup_pks = [dup.pk for dup in duplicates_result[VALIDATE_KEY__VALUE]]
            logger.warning(
                f"{model_name}.save(): Найдено частичное совпадение по словам с ВЫСОКИМ РИСКОМ ошибки! "
                f"Обнаружены очень короткие слова/синонимы (< {MIN_SYNONYM_WORD_LENGTH} символов). "
                f"Проверьте вручную! PK записей с похожими названиями: {dup_pks}"
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


def generate_admin_save_message(
        request: HttpRequest,
        obj: Model,
        is_new: bool,
        related_article: Model | None,
        obj_field_name: str,
        article_title_field: str,
) -> None:
    """
    Генерирует и отправляет информативное сообщение об сохранении объекта в админке.

    Функция анализирует тип операции (создание/редактирование) и статус связанной статьи,
    отправляя соответствующее сообщение (success или warning) с ссылкой на статью.

    Использует Django messages framework для отправки сообщений:
    - GREEN SUCCESS: при успешном создании/обновлении
    - YELLOW WARNING: при создании без связанной статьи (ошибка!)

    Ссылка на статью открывается в новой вкладке для удобства админа.

    Параметры:
    -----------
    request : HttpRequest
        Объект HTTP-запроса для отправки сообщений через Django messages framework.
        Обязателен!

    obj : django.db.models.Model
        Сохраненный объект модели (уже сохранен в БД). Обязателен!
        Из этого объекта автоматически извлекается verbose_name модели через obj._meta.verbose_name
        Также используется для получения старого значения при редактировании.

    is_new : bool
        True если создается новая запись, False если редактируется существующая. Обязателен!
        При создании (is_new=True): отправляет success или warning в зависимости от наличия статьи.
        При обновлении (is_new=False): отправляет success с информацией о текущем состоянии.

    related_article : django.db.models.Model или None
        Связанная статья для нового объекта или при редактировании.
        При создании (is_new=True):
            - Если present: отправляет GREEN SUCCESS и ссылку на статью
            - Если None: отправляет YELLOW WARNING (это ошибка!)
        При редактировании (is_new=False):
            - Если present: отправляет SUCCESS со ссылкой на статью
            - Если None: просто SUCCESS без ссылки
        Обычно это поле вида k_model_to_article из модели.

    obj_field_name : str
        Имя основного поля объекта для получения текущего значения. ОБЯЗАТЕЛЕН!
        Примеры: 's_label' (для TbLabel), 's_artist' (для TbArtist), 's_style_name' (для TbMusicStyle)
        Если поле не существует в модели, будет выброшено AttributeError.

    article_title_field : str
        Имя поля статьи для получения названия статьи. ОБЯЗАТЕЛЕН!
        Обычно это 's_article_title' для всех моделей статей.
        Если поле не существует в связанной статье, будет выброшено AttributeError.

    Raises:
        AttributeError: Если obj_field_name не существует в модели obj
        AttributeError: Если article_title_field не существует в related_article (если он не None)

    Отправляемые сообщения:
    -----------------------
    Новая запись с статьей (is_new=True, related_article существует):
        - GREEN SUCCESS: "Лейбл «NAME» создан успешно. Связанная статья «TITLE» создана автоматически."
        - С ссылкой: "Проверить/Отредактировать статью →"

    Новая запись БЕЗ статьи (is_new=True, related_article=None):
        - YELLOW WARNING: "Лейбл «NAME» создан успешно. [ОЙ-ОЙ-ОЙ] СТАТЬЯ НЕ БЫЛА СОЗДАНА. ЭТО НЕ ДОЛЖНО БЫЛО СЛУЧИТЬСЯ!"
        - Сигнализирует об ошибке в процессе создания связанной статьи

    Обновление (is_new=False):
        - GREEN SUCCESS: "Лейбл «NAME» обновлен. Связанная статья: «ARTICLE_TITLE»."
        - С ссылкой: "Проверить/Отредактировать статью →" (если статья существует)

    Пример использования в admin.py (максимально чистый и поджарый код):
    -----------------------------------------------------------------------
    class LabelAdmin(admin.ModelAdmin):
        def save_model(self, request, obj, form, change):
            # Основной механизм сохранения Django (создает статью если нужно)
            super().save_model(request, obj, form, change)

            # Отправляем информативное сообщение админу с явным указанием полей
            generate_admin_save_message(
                request=request,
                obj=obj,
                is_new=not change,  # Django: change=False для новых, True для существующих
                related_article=obj.k_label_to_article,
                obj_field_name='s_label',  # ОБЯЗАТЕЛЕН! Имя поля для основного названия
                article_title_field='s_article_title',  # ОБЯЗАТЕЛЕН! Имя поля для названия статьи
            )
    """
    # === ВАЛИДАЦИЯ ПАРАМЕТРОВ ===

    # Проверяем, что obj_field_name существует в объекте модели
    if not hasattr(obj, obj_field_name):
        raise AttributeError(
            f"Model '{obj.__class__.__name__}' has no field '{obj_field_name}'. "
            f"Please provide a valid field name from the model."
        )

    # Если есть связанная статья, проверяем что article_title_field в ней существует
    if related_article and not hasattr(related_article, article_title_field):
        raise AttributeError(
            f"Related article model '{related_article.__class__.__name__}' has no field '{article_title_field}'. "
            f"Please provide a valid field name for the article title."
        )

    # Получаем текущее значение основного поля
    current_field_value = getattr(obj, obj_field_name)

    # Инициализируем для использования в сообщениях (если related_article есть, перезапишем)
    article_title = ''
    article_link = ''
    article_info = ''

    # Формируем ссылку на редактирование статьи и собираем информацию о ней
    if related_article:
        article_title = getattr(related_article, article_title_field)
        article_link = (f' <a href=\'../../../tbarticle/{related_article.pk}/change/\''
                        f' target=\'_blank\'>Проверить/Отредактировать статью →</a>')

        # Собираем информацию о статье для более подробного сообщения
        article_info = (f' [{getattr(related_article, 'l_article_type', '???')}]'
                        f' ({getattr(related_article, 's_article_title_html', '<i>???</i>')})')

    # Генерируем сообщение в зависимости от типа операции
    if is_new:
        # СОЗДАНИЕ НОВОЙ ЗАПИСИ - показываем зеленый успех
        msg = f'[OK] {obj._meta.verbose_name} «{current_field_value}» создан успешно.'
        if related_article:
            msg += (f' Связанная статья «{article_title}» создана автоматически. >>'
                    f' {article_info} {article_link}')
            messages.success(request, mark_safe(msg))
        else:
            msg += ' [ОЙ-ОЙ-ОЙ] СТАТЬЯ НЕ БЫЛА СОЗДАНА. ЭТО НЕ ДОЛЖНО БЫЛО СЛУЧИТЬСЯ!'
            messages.warning(request, mark_safe(msg))

    else:
        # РЕДАКТИРОВАНИЕ СУЩЕСТВУЮЩЕЙ ЗАПИСИ
        # Название изменилось или нет - показываем информацию о текущем состоянии и связанной статье
        msg = f'[OK] {obj._meta.verbose_name} «{current_field_value}» обновлен.'
        if related_article:
            msg += f' Связанная статья: «{article_title}» >> {article_info} {article_link}'
        messages.success(request, mark_safe(msg))

