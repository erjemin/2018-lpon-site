# frontend/utils.py
# Служебные функции и хелперы проекта

from __future__ import annotations

import re
import pytils
import random
import logging
from typing import Any, Dict, List, Optional, Union
from bs4 import BeautifulSoup
from html import unescape
from etpgrf.config import HANGING_PUNCTUATION_SPACE_CHARS as SPACE_CHARS
from django.utils.html import mark_safe

from django.http import HttpRequest
from django.db.models import Model
from lpon_site.settings import (
    SLUG_MAX_LENGTH, KEY_SYNONYM,
)



logger = logging.getLogger(__name__)

def normalize_string(s: str) -> str:
    """
    Нормализует строку: удаляет невидимые символы, начальные, конечные и дублирующие пробелы.
    Также приводит к нижнему регистру для case-insensitive сравнения при поиске дублей.

    Работает со ВСЕМИ типами пробельных символов (не-breaking space, thin space и т.д.).

    Args:
        s: Строка для нормализации

    Returns:
        str: Нормализованная строка в нижнем регистре (или пустая если была пуста)

    Пример:
        >> normalize_string("  Sony   Music  ")
        'sony music'
        >> normalize_string("SONY MUSIC")
        'sony music'
        >> normalize_string("Sony\u00a0\u202FMusic")  # с неразрывными пробелами
        'sony music'
    """
    if not s:
        return ""

    result = str(s)

    # Преобразуем в нижний регистр для case-insensitive сравнения
    # (регистр не должен быть значимым при поиске дублей артистов/лейблов/стилей)
    result = result.lower()

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


def super_normalize_string(s: str) -> str:
    """
    Супер-нормализация строки для проверки частичного совпадения слов (PARTIAL_MATCH).

    Выполняет глубокую нормализацию для сравнения словарных совпадений:
    - Очищает HTML через safe_html_special_symbols() (которая вызывает normalize_string())
    - Удаляет все символы кроме букв, цифр и пробелов
    - Сохраняет буквы и цифры ВСЕХ языков (Unicode-safe)
    - Приводит к нижнему регистру (через safe_html_special_symbols → normalize_string)
    - Нормализует пробелы (множественные → одиночные)

    Результат используется для поиска словарных совпадений:
    "The Beatles" и "Beatles, The" оба станут: "the beatles"
    Затем разбиваются на слова: ["the", "beatles"]

    Args:
        s: Строка для нормализации

    Returns:
        str: Строка со словами, разделенными пробелами (в нижнем регистре)

    Пример:
        >> super_normalize_string("The Beatles (Rock)")
        'the beatles rock'
        >> super_normalize_string("Beatles, The - Rock Band!")
        'beatles the rock band'
    """
    if not s:
        return ""

    # Сначала очищаем HTML и спецсимволы через существующую функцию
    # (safe_html_special_symbols вызывает normalize_string(), который уже приводит к нижнему регистру)
    cleaned = safe_html_special_symbols(s)

    # Удаляем все символы кроме букв, цифр и пробелов (Unicode-safe)
    # \w в Python regex с флагом UNICODE включает: буквы всех языков, цифры и подчеркивание
    # Используем [^\w\s] для удаления всего кроме слов и пробелов, затем исключаем подчеркивание
    cleaned = re.sub(r'[^\w\s]|_', '', cleaned, flags=re.UNICODE)

    # Нормализуем пробелы (множественные → одиночные)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


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


def make_slug(
        slug_it: str,
        max_length: int = SLUG_MAX_LENGTH,
        slug_default: str = "content") -> str:
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


def update_synonyms_in_metadata(
    instance: Model,
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

def create_or_get_related_article(
    instance: Model,
    article_type: str,
    main_field_name: str,
    metadata_field_name: str,
    related_fk_field_name: str,
) -> Model:
    """
    Создает или получает связанную статью для сущности модели.
    
    Универсальный хелпер для создания статей при сохранении лейблов, артистов и т.д.
    
    Алгоритм:
    1. Получает значение FK поля напрямую через getattr() (никаких запросов в БД)
    2. Если статья найдена → возвращает её
    3. Если FK поле пусто → создает новую статью с автоматическими SEO параметрами

    Параметры:
    -----------
    instance : django.db.models.Model
        Экземпляр модели (TbLabel, TbArtist, TbMusicStyle и т.д.)
        Должен иметь поле k_{type}_to_article для привязки статьи
    
    article_type : TbArticle.ArticleType
        Тип статьи (например, TbArticle.ArticleType.LABEL)
    
    main_field_name : str
        Имя основного поля сущности (например, 's_label' для TbLabel)
    
    metadata_field_name : str
        Имя поля метаданных со словарем синонимов (например, 'j_label_metadata')
    
    related_fk_field_name : str
        Имя FK поля в модели instance (например, 'k_label_to_article')
        Передается явно из save() модели

    Returns:
        TbArticle: Созданная или найденная статья
    
    Пример использования в TbLabel.save():
        article = create_or_get_related_article(
            self,
            TbArticle.ArticleType.LABEL,
            's_label',
            'j_label_metadata',
            'k_label_to_article'
        )
        self.k_label_to_article = article
    """
    from .models import TbArticle

    # Получаем verbose_name модели для универсальности
    verbose_name = instance._meta.verbose_name  # "Лейбл", "Артист" и т.д.

    # Генерируем slug используя verbose_name (более гибко чем хардкод)
    # "Лейбл" → "label", "Артист" → "artist"
    article_slug_default = make_slug(slug_it=verbose_name)
    
    # Получаем значение основного поля (например, "Sony Records")
    main_field_value = getattr(instance, main_field_name, '')
    
    # ===== ПОПЫТКА НАЙТИ СУЩЕСТВУЮЩУЮ СТАТЬЮ =====
    # Получаем статью через FK поле напрямую (никаких запросов в БД)
    try:
        article = getattr(instance, related_fk_field_name)
        if article:
            # FK поле содержит статью - возвращаем её
            return article
    except:
        # FK поле не существует или пусто, создаем новую
        pass

    # ===== СТАТЬЯ НЕ ПРИВЯЗАНА. СОЗДАËМ НОВУЮ СТАТЬЮ =====

    # Собираем синонимы из метаданных для SEO ключевых слов и исключаем текущее значение поля
    # из списка (оно будет добавлено первым для приоритета)
    other_synonyms = [s for s in instance.__dict__.get(metadata_field_name, {}).get(KEY_SYNONYM, []) if str(s) != main_field_value]

    # Собираем все синонимы с текущим значением первым
    all_synonyms = [main_field_value] + other_synonyms if other_synonyms else [main_field_value]
    synonyms_str = ", ".join(str(s) for s in all_synonyms)

    # Создаем объект статьи
    article = TbArticle(
        s_article_title=f"[{verbose_name}] {main_field_value} (auto-make)",     # Техническое название для админки
        s_article_title_html=main_field_value,
        seo_title=main_field_value,
        seo_keywords=f"{synonyms_str}, {verbose_name}, {article_slug_default}",
        seo_description=f"{main_field_value} ({verbose_name}): информация.",
        l_article_type=article_type,
        b_article_published=True,
        slug=make_slug(slug_it=main_field_value, slug_default=article_slug_default),
    )

    # Сохраняем статью
    article.save()

    # TODO: Отправить уведомление в Redis о созданной статье
    # Это нужно для парсера и автоматического добавления лейблов/артистов/стилей
    # Уведомление должно содержать: article.pk, article.s_article_title_html, model_type, article_type
    # Админ должен получить очередь задач "Созданные статьи требуют проверки/редактирования"
    # Пример: redis.lpush('parser:created_articles', json.dumps({
    #     'pk': article.pk,
    #     'title': article.s_article_title_html,
    #     'article_type': str(article.l_article_type),
    #     'model': instance.__class__.__name__,
    #     'created_at': datetime.now().isoformat()
    # }))

    return article
