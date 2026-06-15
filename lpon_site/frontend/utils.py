# frontend/utils.py
# Служебные функции и хелперы проекта

from bs4 import BeautifulSoup
from html import unescape
from lpon_site.settings import SLUG_MAX_LENGTH
from etpgrf.config import HANGING_PUNCTUATION_SPACE_CHARS as SPACE_CHARS
import re
import pytils
import random
import logging

logger = logging.getLogger(__name__)


def safe_html_special_symbols(s: str) -> str:
    """Преобразует HTML-фрагмент в чистый текст.

       Удаляет все HTML-теги и декодирует HTML-мнемоники в Unicode, убирает невидимые символы и нормализует пробелы.

       Обработка пробелов:
       - Заменяет ВСЕ типы пробелов из SPACE_CHARS на обычный пробел
       - Добавляет явно: \\u00a0 (non-breaking space) и \\u202F (narrow no-break space)
       - Удаляет нулевой ширины символы (ZWJ, zero-width space и т.д.)
       - Нормализует множественные пробелы в один

       Args:
            s: Строка, которую надо очистить (с возможной HTML-разметкой).
       Returns:
            str: Чистый текст без HTML-разметки и спецсимволов.

        Example:
            >>> safe_html_special_symbols('<p>Привет&nbsp;<b>мир</b>!</p>')
            'Привет мир!'
            >>> safe_html_special_symbols('Текст с\\u00a0неразрывным и \\u202Fтонким пробелом')
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

    # Убираем символы, которые нужно удалить (не заменять, а удалять)
    result = result.translate({
        ord("\xad"): None,    # символ мягкого переноса
        ord("\u200b"): None,  # символ нулевой ширины (zero-width space)
        ord("\u200c"): None,  # символ нулевой ширины (zero-width non-joiner)
        ord("\u200d"): None,  # символ Zero Width Joiner (ZWJ)
        ord("\u2060"): None,  # символ Word Joiner (WJ)
        ord("\ufeff"): None,  # символ Zero Width No-Break Space (BOM)
    })

    # Заменяем все типы пробелов из SPACE_CHARS из библиотеки etpgrf на обычный пробел
    # Важно сделать это после обработки "мягкого переноса" потому что он включен в SPACE_CHARS (frozenset)
    all_spaces = SPACE_CHARS | frozenset([
        "\u00a0",   # non-breaking space (&nbsp)
        "\u202F",   # narrow no-break space (нет мнемоники) — тонкий неразрывный пробел
    ])
    for space_char in all_spaces:
        result = result.replace(space_char, " ")

    # Нормализуем пробелы (удаляем множественные пробелы и приводим к стандарту)
    return " ".join(result.split())


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

    # Очищаем текст от HTML и спецсимволов
    clean_text = safe_html_special_symbols(slug_it).lower()

    # Транслитерируем и создаем slug (pytils подходит для русского)
    slug = pytils.translit.slugify(clean_text)

    # Нормализуем множественные дефисы,  удаляем дефисы в начале/конце
    slug = re.sub(pattern=r"-+", repl="-", string=slug).strip("-")

    # Обрезаем излишнее
    slug = slug[:max_length]

    # Если все еще пусто — генерируем fallback
    return slug or f"{slug_default}-{random.randint(1, 4095):03x}"
