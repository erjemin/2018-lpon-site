"""
Константы, перечисления и ключи метаданных проекта LPON.

Данный модуль является единым источником правды для:
  • Ключей JSON-метаданных (TbItem.j_item_metadata, TbOffer.j_offer_metadata и др.)
  • Контролируемых словарей и перечислений (типы носителей, типы статей, продавцов, валют)
  • Функций генерации дефолтных JSON-структур для моделей
  • Валидационных настроек и системных констант
"""

from enum import IntEnum
from django.db import models


# ============================================================================
# СИСТЕМНЫЕ НАСТРОЙКИ И ОГРАНИЧЕНИЯ
# ============================================================================

# Максимальная длина slug: Весь URL оптимально иметь до 70 символов (методичка Google).
# SLUG_MAX_LENGTH задает ограничение для слагов, создаваемых автоматически.
SLUG_MAX_LENGTH = 60

# Минимальная длина слова для поиска совпадений схожести в синонимах
MIN_SYNONYM_WORD_LENGTH = 4


# ============================================================================
# КЛЮЧИ МЕТАДАННЫХ ДЛЯ ОБЩИХ ТАБЛИЦ (TbLabel, TbSeller, TbArtist, TbMusicStyle)
# ============================================================================

KEY_SYNONYM_EN = 'SYN_EN'  # Синонимы на английском языке (для поиска и парсеров)
KEY_SYNONYM_RU = 'SYN_RU'  # Синонимы на русском языке (для отображения на фронтенде)


# ============================================================================
# КЛЮЧИ И ЗНАЧЕНИЯ ДЛЯ МЕТАДАННЫХ ИЗОБРАЖЕНИЙ (TbImageMetadata)
# ============================================================================

KEY_IMAGE_TYPE = 'IMG_IS'           # Ключ для хранения типа картинки
VALUE_IMAGE_ABSTRACT = 'abstract'   # Абстрактная картинка (логотипы, промо, типовые обложки)
VALUE_IMAGE_REAL = 'real'           # Реальная фотография физического лота

KEY_IMAGE_FROM = 'IMG_FROM'         # Источник происхождения изображения
VALUE_IMAGE_FROM_USER = '_adm'      # Загружено пользователем через панель управления
VALUE_IMAGE_FROM_PARSE = 'parse'    # Получено автоматически через парсер (Discogs, Bandcamp и т.д.)

KEY_IMAGE_URL = 'IMG_URL'           # URL оригинального источника изображения
KEY_IMAGE_NOTE = 'IMG_NOTE'         # Текстовая заметка или подпись к изображению


# ============================================================================
# КЛЮЧИ МЕТАДАННЫХ СТАТЕЙ (TbArticle)
# ============================================================================

KEY_ARTICLE_HUB = 'HUB'             # Флаг того, что статья является хабом/сборником


# ============================================================================
# КЛЮЧИ МЕТАДАННЫХ ДЛЯ ТОВАРОВ И МОДЕЛЕЙ НОСИТЕЛЕЙ (TbItem.j_item_metadata)
# ============================================================================

KEY_ITEM_MEDIA_TYPE = 'media_type'        # Тип сущности: музыкальный альбом, модель носителя и т.д.
KEY_ITEM_MEDIA_FORMAT = 'media_format'    # Формат физического носителя (кассета, MD, винил, CD)
KEY_ITEM_TAPE_TYPE = 'tape_type'          # Тип магнитной ленты (для кассет: Type I, II, III, IV)
KEY_ITEM_LENGTH = 'length'                # Хронометраж носителя (46, 60, 74, 90 мин)
KEY_ITEM_SHELL_COLOR = 'shell_color'      # Цвет корпуса кассеты или минидиска
KEY_ITEM_RELEASE_YEAR = 'release_year'    # Год или диапазон годов производства модели/релиза
KEY_ITEM_MARKET = 'market'                # Регион дистрибуции (JP, US, EU, GLOBAL)
KEY_ITEM_GALLERY_MODEL = 'gallery_model'  # Список ID эталонных изображений модели в django-filer
KEY_ITEM_CATALOG_NUM = 'catalog_num'      # Оригинальный каталожный номер производителя
KEY_ITEM_BARCODE = 'barcode'              # Штрихкод (EAN/UPC)


# ============================================================================
# КЛЮЧИ МЕТАДАННЫХ ДЛЯ КОММЕРЧЕСКИХ ПРЕДЛОЖЕНИЙ (TbOffer.j_offer_metadata)
# ============================================================================

KEY_OFFER_NOTE = 'OFR_NT'                 # Текстовая заметка по лоту (дефекты, нюансы)
KEY_OFFER_ALL_MEDIA = 'OFR_MF'            # Состав комплекта носителей (например, {"lp": 2, "cd": 1})
KEY_OFFER_IS_RECORDED = 'is_recorded'     # Флаг наличия уникальной аудиозаписи на носителе
KEY_OFFER_RECORDING_INFO = 'recording_info' # Описание записанного материала (эфир, альбом, бутлег)
KEY_OFFER_TABS = 'write_protect_tabs'     # Состояние язычков защиты от записи (INTACT, BROKEN)
KEY_OFFER_INLAY = 'inlay_condition'       # Состояние бумажного вкладыша J-Card (CLEAN, PENCIL, WRITTEN)
KEY_OFFER_SERIES_TAG = 'series_tag'       # Слаг/метка серии или коллекции
KEY_OFFER_PACKAGING = 'packaging'         # Сохранность упаковки (SEALED, OPENED)


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ГЕНЕРАЦИИ ДЕФОЛТНЫХ ЗНАЧЕНИЙ JSON (CALLABLE DEFAULTS)
# ============================================================================

def get_image_metadata_default() -> dict:
    """
    Возвращает значение по умолчанию для TbImageMetadata.j_img_metadata.
    Используется как callable default в Django моделях и миграциях.
    """
    return {
        KEY_IMAGE_TYPE: VALUE_IMAGE_ABSTRACT,
        KEY_IMAGE_FROM: VALUE_IMAGE_FROM_USER,
        KEY_IMAGE_URL: None,
        KEY_IMAGE_NOTE: '???',
    }


def get_offer_metadata_default() -> dict:
    """
    Возвращает значение по умолчанию для TbOffer.j_offer_metadata.
    Используется как callable default в Django моделях и миграциях.
    """
    return {
        KEY_OFFER_NOTE: '',
        KEY_OFFER_ALL_MEDIA: [],
    }


def get_item_metadata_default() -> dict:
    """
    Возвращает значение по умолчанию для TbItem.j_item_metadata.
    """
    return {
        KEY_ITEM_MEDIA_TYPE: 'blank_media',
        KEY_ITEM_MEDIA_FORMAT: 'other',
    }


# ============================================================================
# КОНТРОЛИРУЕМЫЕ ПЕРЕЧИСЛЕНИЯ (ENUMS / CHOICES ДЛЯ МОДЕЛЕЙ И JSON)
# ============================================================================

class ArticleType(models.TextChoices):
    """
    Типы статей и контентных разделов (TbArticle.l_article_type).

    ВАЖНО ДЛЯ РОУТИНГА И URL:
    Значение каждого элемента (например, 'info', 'blog', 'artist', 'item' и т.д.)
    используется напрямую как первый сегмент канонического URL-пути статьи:
        /<l_article_type>/<slug>/   (например: /info/privacy-policy/, /blog/new-release-2026-september/)

    Исключения:
        - HUB ('HUB'): статьи-хабы публикуются напрямую в корне сайта (/<slug>/).
    """
    ARTIST = 'artist', 'Artist: артист, группа или бренд'
    STYLE = 'style', 'Style: музыкальный стиль'
    ITEM = 'item', 'Item: Альбом, релиз или товар (кассета, hifi, аксессуар)'
    LABEL = 'label', 'Label: Лейбл, издатель или компания'
    OFFER = 'offer', 'Offer: конкретное предложение от продавца'
    SELLER = 'seller', 'Seller: продавец или магазин'
    BLOG = 'blog', 'Blog: Новость или блог'
    ACTION = 'action', 'Action: Спецпредложение, акция, распродажа и т.п.'
    ADV = 'adv', 'Adv: Реклама или баннер'
    HUB = 'HUB', 'HUB: СТАТЬЯ-ХАБ (использует DSL для отображения контента)'
    INFO = 'info', 'Info: Текстовый контент (для FAQ, условий конфиденциальности, правил/соглашений и т.д.)'
    OTHER = '--', '?¿?: Другое'


class SellerType(models.TextChoices):
    """Тип продавца или магазина (TbSeller.l_seller_type)."""
    SELLER = 'seller', 'Продавец'
    LABEL = 'label', 'Лейбл (издатель)'
    DIY = 'diy', 'Самиздат группы'
    CROWD = 'crowd', 'Краудфандинг'
    OTHER = '???', 'Другое'


class Currency(models.TextChoices):
    """Валюта источника/продавца (TbSeller.l_seller_currency)."""
    RUB = 'rub', 'RUB: российский рубль'
    USD = 'usd', 'USD: американский доллар'
    EUR = 'eur', 'EUR: евро'
    AMD = 'amd', 'AMD: армянских драм'
    TRY = 'try', 'TRY: турецкая лира'
    JPY = 'jpy', 'JPY: японская иена'
    GBP = 'gbp', 'GBP: британский фунт'
    CNY = 'cny', 'CNY: китайский юань'
    BYN = 'byn', 'BYN: белорусский рубль'
    TON = 'ton', 'TON: криптовалюта TON'
    OTHER = '??', 'Other'


class Condition(models.TextChoices):
    """
    Международный грейдинг состояния носителя, обложки, вкладышей, плакатов и т.п. (Goldmine Standard).
    Используется в TbOffer.l_offer_condition_media и TbOffer.l_offer_condition_sleeve.
    """
    S = 's', 'Still Sealed (новое, запечатано)'
    M = 'm', 'Mint (новое, распакованное)'
    NM = 'nm', 'Near Mint (почти новое)'
    VG = 'vg', 'Very Good (очень хорошее)'
    G = 'g', 'Good (хорошее)'
    F = 'f', 'Fair (удовлетворительное)'
    P = 'p', 'Poor (плохое)'
    OTHER = '??', 'Other'


class Format(models.TextChoices):
    """Физический формат носителя оффера (TbOffer.l_offer_to_format)."""
    LP = 'lp', 'Vinyl Long-Play (12")'
    EP = 'ep', 'Vinyl Extended-Play (12", 10", 7")'
    V45 = '45', 'Vinyl 7" (45 rpm)'
    CD = 'cd', 'Compact Disc'
    LD = 'ld', 'LaserDisc'
    REC_MD = 'md', 'MiniDisc Record'
    USE_MD = 'ms', 'Used MiniDisc (для записи)'
    REC_CS = 'cs', 'Cassette Record'
    USE_CS = 'uc', 'Used Cassette (для записи)'
    REC_RR = 'tp', 'Tape Reel Record'
    USE_RR = 'ur', 'Used Tape Reel (для записи)'
    OTHER = '??', 'Other'


class SourceType(models.TextChoices):
    """Тип источника данных о товарах (TbSource.l_source_type)."""
    EXCEL = 'excel', 'Excel-файл от продавца или издателя'
    CSV = 'csv', 'CSV-файл от продавца или издателя'
    URL = 'url', 'URL страницы с данными (например, HTML-страница с каталогом товаров)'
    OTHER = '??', 'Другое (включая ручной ввод)'


class MediaType(models.TextChoices):
    """Тип сущности товара в каталоге."""
    M_ALBUM = 'music_album', 'Музыкальный альбом / релиз (кассета, CD, винил, MD и т.д.)'
    M_MEDIA = 'blank_media', 'Носитель под запись (чистый или б/у модель)'
    M_RARE = 'rare_recording', 'Раритетная аудиозапись или бутлег'
    M_EQUIPMENT = 'equipment', 'Аудиотехника и аксессуары'


class Market(models.TextChoices):
    """Регион дистрибуции релиза или модели носителя."""
    JAPAN = 'jp', 'Япония (Japan / NTSC-J)'
    USA = 'us', 'США / Северная Америка (USA / NTSC-U)'
    EUROPE = 'eu', 'Европа (Europe / PAL)'
    UK = 'uk', 'Великобритания (United Kingdom)'
    USSR = 'su', 'СССР / Мелодия'
    RU = 'ru', 'Россия'
    GLOBAL = 'global', 'Международный / Global'


class TapeType(models.TextChoices):
    """Тип магнитной ленты для аудиокассет."""
    TYPE_1_NORMAL = 'type_1', 'Type I: Normal Position (Fe / Fe2O3)'
    TYPE_2_HIGH = 'type_2', 'Type II: High Position (CrO2 / Chrome / Cobalt)'
    TYPE_3_FECR = 'type_3', 'Type III: Ferro-Chrome (FeCr)'
    TYPE_4_METAL = 'type_4', 'Type IV: Metal Position (Metal Tape)'


class MediaLength(models.IntegerChoices):
    """Стандартные хронометражи кассет и минидисков в минутах."""
    L10 = 10, '10 минут'
    L20 = 20, '20 минут'
    L30 = 30, '30 минут'
    L40 = 40, '40 минут'
    L46 = 46, '46 минут'
    L50 = 50, '50 минут'
    L54 = 54, '54 минуты'
    L60 = 60, '60 минут'
    L74 = 74, '74 минуты (стандарт MiniDisc)'
    L80 = 80, '80 минут'
    L90 = 90, '90 минут'
    L100 = 100, '100 минут'
    L110 = 110, '110 минут'
    L120 = 120, '120 минут'
    L150 = 150, '150 минут'


class ShellColor(models.TextChoices):
    """Цвет корпуса компакт-кассеты или минидиска."""
    AMBER = 'amber', 'Янтарный (Amber / Прозрачный оранжевый)'
    SMOKE = 'smoke', 'Дымчатый (Smoke / Полупрозрачный серый)'
    CLEAR = 'clear', 'Прозрачный (Clear)'
    BLACK = 'black', 'Черный (Solid Black)'
    WHITE = 'white', 'Белый (Solid White)'
    GOLD = 'gold', 'Золотой / Металлик (Gold Metallic)'
    BLUE = 'blue', 'Синий / Голубой (Blue / Cyan)'
    RED = 'red', 'Красный / Рубиновый (Red / Ruby)'
    GREEN = 'green', 'Зеленый (Green)'


class WriteProtectTabs(models.TextChoices):
    """Состояние язычков защиты от записи на компакт-кассетах."""
    INTACT = 'intact', 'Целы (Intact / Запись возможна)'
    BROKEN = 'broken', 'Выломаны (Broken / Защита активна)'


class InlayCondition(models.TextChoices):
    """Состояние бумажного вкладыша (J-Card)."""
    CLEAN = 'clean', 'Чистый (Без надписей / как новый)'
    PENCIL = 'pencil', 'Надписи простым карандашом (стираемые)'
    WRITTEN = 'written', 'Исписан ручкой / штампы / наклейки'
    MISSING = 'missing', 'Вкладыш отсутствует'


class Packaging(models.TextChoices):
    """Тип сохранности упаковки физического экземпляра."""
    SEALED = 'sealed', 'Заводская запечатка (Still Sealed)'
    OPENED = 'opened', 'Вскрыт / б/у (Opened)'


# ============================================================================
# КОНСТАНТЫ ДЛЯ ПОИСКА ДУБЛИКАТОВ И ВАЛИДАЦИИ
# ============================================================================

VALIDATE_KEY__MATCH_TYPE = 'MATCH_TYPE'
VALIDATE_KEY__MODEL = 'MODEL'
VALIDATE_KEY__VALUE = 'MATCH_VALUE'


class ValidateMatchType(IntEnum):
    """Типы совпадений при поиске дубликатов."""
    IS_DUPLICATE = 1                      # Точное совпадение основного поля (s_label, s_artist и т.д.)
    FIND_IN_SYNONYM = 2                   # Точное совпадение в синонимах
    EXACT_SYNONYM_MATCH = 3               # Точное совпадение синонимов с синонимами остальных записей
    PARTIAL_MATCH = 4                     # Схожесть: частичное совпадение
    PARTIAL_MATCH__RISK_SHORT_WORDS = 5   # Схожесть: совпадение по коротким словам (риск ложных срабатываний)
