# LPON Store — Django E-Commerce Database Schema (SQLite optimized)
# ER-ДИАГРАММА СХЕМЫ БД (v2.0 - переделана правильно!)
# 
# Легенда:
#   PK = Primary Key        FK = Foreign Key        M2M = Many-to-Many
#   1:1 = OneToOne связь    1:M = One-to-Many      M:M = Many-to-Many
#
# ВАЖНО: Диаграмма разделена по логическим секциям, см. ниже!
#
# ════════════════════════════════════════════════════════════════════════════════
# ЦЕНТР СХЕМЫ: СТАТЬИ (TbArticle) — ИНДЕКСНАЯ ТАБЛИЦА ДЛЯ ВСЕХ СПРАВОЧНИКОВ
# ════════════════════════════════════════════════════════════════════════════════
#
# TbArticle — главная таблица для всех текстовых описаний, SEO, контента:
#   - Соединитель для Artist, Item, Label, Seller, Style (все 1:1 в статьи)
#   - Прямая ссылка на filer.Image для обложки
#   - M2M к TbMusicStyle (теги стилей)
#
# ════════════════════════════════════════════════════════════════════════════════
# СПРАВОЧНИКИ (все связаны с TbArticle через OneToOne)
# ════════════════════════════════════════════════════════════════════════════════
#
# TbArtist (1:1→TbArticle) + M2M←→TbItem через k_item_to_artist (коллаборации)
# TbItem   (1:1→TbArticle) + M2M←→TbMusicStyle через k_item_to_style (жанры)
# TbLabel  (1:1→TbArticle)
# TbSeller (1:1→TbArticle) + 1:M→TbSource (источники данных от продавца)
# TbMusicStyle (1:1→TbArticle) + M2M←→TbArticle через k_article_to_styles (теги статей)
#
# ════════════════════════════════════════════════════════════════════════════════
# КОММЕРЧЕСКИЕ ТАБЛИЦЫ: Управление предложениями и их историей
# ════════════════════════════════════════════════════════════════════════════════
#
# TbSource (1:M←TbSeller)
#   └─→ TbOffer (1:M)
#       ├─ 1:1→TbItem (FK что именно продавать)
#       ├─ 1:1→TbLabel (FK от какого издателя)
#       ├─ 1:1→TbArticle (опцион, для уникальной статьи предложения)
#       ├─ M2M←→TbImageMetadata (картинки оффера)
#       │   └─ TbImageMetadata (промежуточная таблица M2M offer←→Image)
#       │       └─ 1:1→filer.Image (FK на файл из django_filer)
#       │       └─ m_offer: FK→TbOffer (часть M2M)
#       │       └─ i_img_sort: порядок сортировки
#       │       └─ j_img_metadata: JSON метаданные (тип, источник и т.д.)
#       │
#       └─ 1:M→TbOfferHistory (история цены/кол-ва)
#           └─ t_history_created: Timestamp (редактируется для импорта исторических данных)
#
# ════════════════════════════════════════════════════════════════════════════════
# СПРАВОЧНИК ПОЛЕЙ ВСЕХ МОДЕЛЕЙ
# ════════════════════════════════════════════════════════════════════════════════
#
# TbArticle (текстовый контент и SEO):
#   id, s_article_title (уникальный), l_article_type, b_article_published
#   s_article_title_html, k_article_to_image (→filer.Image), i_article_sort, j_article_metadata (JSON)
#   k_article_to_styles (M2M→TbMusicStyle), i_article_views, i_article_favorites
#   slug (уникальный, для URL), seo_title, seo_description, s_article_teaser_html
#   s_article_content_html, t_article_started, t_article_ended, t_article_created, t_article_updated
#
# TbArtist (1:1→TbArticle, M2M←TbItem.k_item_to_artist):
#   id, s_artist, k_artist_to_article (1:1→TbArticle)
#   t_artist_created, t_artist_updated
#
# TbItem (1:1→TbArticle, M2M: →TbArtist, →TbMusicStyle):
#   id, s_item, k_item_to_artist (M2M), k_item_to_style (M2M)
#   k_item_to_article (1:1→TbArticle), s_item_date (текстовая дата)
#   t_item_date (базовая дата), i_discogs_master_id
#   t_item_created, t_item_updated
#
# TbLabel (1:1→TbArticle, ←TbOffer.k_offer_to_label):
#   id, s_label, k_label_to_article (1:1→TbArticle)
#   t_label_created, t_label_updated
#
# TbSeller (1:1→TbArticle, 1:M→TbSource):
#   id, s_seller (уникальный), l_seller_currency, l_seller_type
#   k_seller_to_article (1:1→TbArticle), j_seller_metadata (JSON)
#   t_seller_created, t_seller_updated
#
# TbMusicStyle (1:1→TbArticle, M2M: ←TbArticle, ←TbItem):
#   id, s_style_name, k_style_to_article (1:1→TbArticle)
#   j_style_metadata (JSON синонимы Discogs), t_style_created, t_style_updated
#
# TbSource (1:M←TbSeller, 1:M→TbOffer):
#   id, k_source_to_seller (1:M←), l_source_type, s_source_name
#   source_file (FilerFileField), s_source_url, t_source_data
#   j_source_metadata (JSON структура источника), t_source_created, t_source_updated
#
# TbOffer (1:M←TbSource, FK: TbItem, TbLabel, TbArticle, M2M: ←TbImageMetadata):
#   id, s_offer (название оффера)
#   k_offer_to_item (1:1→TbItem), k_offer_to_label (1:1→TbLabel)
#   k_offer_to_source (1:M←TbSource), k_offer_to_article (1:1→TbArticle, опцион)
#   m_image (M2M←TbImageMetadata)
#   l_offer_to_format (формат: LP, CD, Vinyl и т.д.)
#   b_offer_is_preorder, d_offer_date_release, l_offer_condition_media, l_offer_condition_sleeve
#   f_offer_price, i_offer_quantity, i_offer_discount_to_daily_sale
#   i_offer_discogs_id, s_offer_code (hashids, уникальный, генерируется автоматически)
#   j_offer_metadata (JSON), i_offer_views, i_offer_favorites
#   t_offer_created, t_offer_updated
#
# TbOfferHistory (1:M←TbOffer, только история цены/кол-ва):
#   id, k_history_to_offer (1:M←TbOffer)
#   f_history_price (старая цена), i_history_quantity (старое кол-во)
#   j_history_metadata (JSON координаты в источнике)
#   t_history_created (Timestamp, РЕДАКТИРУЕТСЯ ДЛЯ ИМПОРТА исторических данных!)
#
# TbImageMetadata (промежуточная M2M offer←→Image):
#   id, k_image_to_image (FK→filer.Image), m_offer (FK→TbOffer)
#   i_img_sort (порядок сортировки)
#   j_img_metadata (JSON: тип, источник, ссылка, заметка)
#   t_img_metadata_created, t_img_metadata_updated
#
# ════════════════════════════════════════════════════════════════════════════════
# МЕТОДЫ И АВТОМАТИКА МОДЕЛЕЙ
# ════════════════════════════════════════════════════════════════════════════════
#
# TbArticle:
#   • save(): генерирует slug автоматически (если не установлен)
#   • increment_views(): безопасный инкремент просмотров
#   • increment_favorites(): безопасный инкремент добавлений в избранное
#   • Если привязана картинка без метаданных → создает TbImageMetadata
#
# TbArtist, TbItem, TbLabel, TbSeller, TbMusicStyle:
#   • save(): создает/обновляет связанную TbArticle автоматически
#   • create_or_get_related_article(): хелпер для создания статьи
#
# TbOffer:
#   • save(): генерирует s_offer_code (hashids) при создании нового оффера
#   • save(): отслеживает изменения цены/кол-ва → создает TbOfferHistory
#   • Двухэтапное сохранение: super().save() → кодирование → update(s_offer_code=...)
#   • Не обновляет код при изменении (только при создании)
#
# TbOfferHistory:
#   • Создается автоматически в save() TbOffer
#   • Сравнивает последнюю запись истории с текущей ценой/кол-вом
#   • Новая запись создается ТОЛЬКО если произошли изменения
#   • t_history_created редактируется для импорта исторических данных
#
# TbImageMetadata:
#   • Промежуточная таблица M2M (не имеет собственной автоматики)
#   • Заполняется вручную через админку или парсерами
#
# ════════════════════════════════════════════════════════════════════════════════

# 
# Справочники (5):
#   TbArticle - индексная таблица для всех текстовых описаний
#   TbArtist, TbItem, TbLabel, TbSeller - справочники (все 1:1→article)
#   TbMusicStyle - музыкальные стили (1:1→article, M2M←article, M2M←item)
#
# Коммерческие (5):
#   TbSource - источники данных (1:M←seller)
#   TbOffer - предложения товаров (1:M←source, FK→item/label/article, M2M←imagemetadata)
#   TbOfferHistory - история изменений цены/кол-ва (1:M←offer)
#   TbImageMetadata - метаданные изображений (M2M offer←→Image)
#
#
# ОПТИМИЗАЦИЯ ДЛЯ SQLite:
#   - db_index=True на все FK поля (SQLite не создает их автоматически)
#   - Составные индексы на часто используемые комбинации
#   - PRAGMA auto_vacuum=2 для невручного сокращения файла БД
#   - PRAGMA journal_mode=WAL для лучшей concurrency
#   - M2M использует числовые FK (INT) вместо строк
#   - Slug'и как UNIQUE indexed fields (не primary_key) для экономии места

import base64
import datetime
import logging
from hashids import Hashids
from django.db import models
from django.db.models import F
from django.utils import timezone
from filer.fields.image import FilerImageField
from filer.fields.file import FilerFileField
from frontend.utils import make_slug, update_synonyms_in_metadata, create_or_get_related_article
from frontend.utils_validators import validate_and_raise_for_duplicates
from lpon_site.settings import (
    KEY_IMAGE_TYPE,                 # Ключ, о том, какой тип изображения (реальное или абстрактное)
    VALUE_IMAGE_ABSTRACT,             # Реальная картинка (актуально, для фото товаров в TbOffer)
    KEY_IMAGE_FROM,               # Ключ, о том, как получено изображение
    VALUE_IMAGE_FROM_USER,          # Картинка загружена пользователем через админку
    KEY_IMAGE_URL,                  # Ключ, о том, откуда получена картинка (URL источника)
    KEY_IMAGE_NOTE,                 # Ключ, для заметок о картинке (например, "обложка", "задник", "вкладка" и т.д.)
    KEY_OFFER_NOTE,                 # Ключ, для заметок о коммерческом предложении (например, "замят угол конверта" и т.д.)
    KEY_OFFER_ALL_MEDIA,             # Ключ, для хранения информации о том, какие носители входят в оффер (например, CD+2LP)
    OFFER_HASHIDS_SALT,             # Соль для криптографического кодирования ID оферов
    OFFER_HASHIDS_MIN_LENGTH,       # Минимальная длина кода
)

logger = logging.getLogger(__name__)


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ DEFAULTS В МОДЕЛЯХ
# ============================================================================

def get_image_metadata_default():
    """
    Возвращает значение по умолчанию для j_img_metadata.
    Используется как callable default в Django моделях (Django не может сериализовать lambda).
    """
    return {
        KEY_IMAGE_TYPE: VALUE_IMAGE_ABSTRACT,
        KEY_IMAGE_FROM: VALUE_IMAGE_FROM_USER,
        KEY_IMAGE_URL: None,
        KEY_IMAGE_NOTE: '???',
    }


def get_offer_metadata_default():
    """
    Возвращает значение по умолчанию для j_offer_metadata.
    Используется как callable default в Django моделях (Django не может сериализовать lambda).
    """
    return {
        KEY_OFFER_NOTE: '',
        KEY_OFFER_ALL_MEDIA: [],
    }


# ============================================================================
# МЕТАДАННЫЕ ИЗОБРАЖЕНИЙ
# ============================================================================
class TbImageMetadata(models.Model):
    """
    Метаданные изображений для офферов (промежуточная таблица M2M).
    
    Поля:
      • image (FK→filer.Image): файл изображения из django_filer [indexed]
      • m_offer (FK→TbOffer): оффер, к которому привязана картинка [nullable, indexed]
      • i_img_sort (int): порядок сортировки (0=обложка, 1=задник и т.д.) [indexed]
      • j_img_metadata (JSON): метаданные (тип, источник, ссылка, заметка)
      • t_img_metadata_created, t_img_metadata_updated (Timestamps)
    
    Использование:
      • offer.m_image.all() — все картинки оффера
      • offer.m_image.all().order_by('i_img_sort') — отсортированные картинки
      • image.metadata (через related_name) — доступ к метаданным
    
    МЕТОДЫ:
    • Нет переопределённых методов save(). Используется стандартное поведение Django.
    """

    image = FilerImageField(
        # Связь в M2M с filer.Image (часть промежуточной таблицы)
        # CASCADE: если удалится картинка → удалить метаданные (метаданные без картинки бессмысленны)
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        related_name='m_offer',  # Встречный доступ: filer_image.m_offer.all()
        verbose_name='Файл изображения',
        help_text='Файл изображения из django_filer.',
    )

    i_img_sort = models.IntegerField(
        # Порядок (сортировка) вывода изображений
        default=0,
        db_index=True,
        verbose_name='Сортировка',
        help_text='Порядок отображения изображений. Чем меньше число, тем выше в списке. '
                  'Можно использовать для указания обложки (0), задника (1) и т.д.',
    )

    j_img_metadata = models.JSONField(
        # Гибкие дополнительные данные об изображении с предзаполненной структурой
        # Пример: {"IMG_IS": "abstract", "IMG_FROM": "ivan", "IMG_URL": None, "IMG_NOTE": "обложка"}
        default=get_image_metadata_default,
        blank=True,
        null=False,  # Изменено с True на False т.к. теперь всегда есть структура default
        verbose_name='Метаданные',
        help_text='JSON с дополнительными данными: тип (реальное/абстрактное), источник (парсер/админка), '
                  'URL источника и заметки. Предзаполнено структурой для удобства.',
    )

    # Связь с TbOffer (часть M2M через эту промежуточную таблицу)
    m_offer = models.ForeignKey(
        'TbOffer',
        on_delete=models.SET_NULL,  # SET_NULL: если удалится оффер → метаданные остаются (картинка же еще есть!)
        null=True,
        blank=True,
        related_name='m_image',  # Встречный доступ: offer.m_image.all()
        verbose_name='Оффер',
        help_text='Оффер, к которому привязана эта картинка (может быть пусто, если оффер удален)',
    )

    class Meta:
        verbose_name = 'Метаданные изображения'
        verbose_name_plural = 'Метаданные изображений'
        ordering = ('i_img_sort',)


# ============================================================================
# СТАТЬИ (любая текстовая информация о релизе, исполнителе, продавце и т.д...)
#         а так же новости, блог, тексты о спец-предложениях и т.д.)
# ============================================================================
class TbArticle(models.Model):
    """
    Центральная таблица текстового контента, SEO и описаний.
    
    Поля:
      • id (PK), s_article_title (str, уникальный): технический заголовок
      • l_article_type (choice): тип статьи (artist, item, offer, seller, style, blog и т.д.)
      • b_article_published (bool): опубликовано ли [indexed]
      • s_article_title_html (str): HTML-заголовок для отображения
      • k_article_to_image (FK→filer.Image): обложка статьи [nullable, indexed]
      • k_article_to_styles (M2M→TbMusicStyle): теги стилей статьи
      • slug (str, уникальный): URL-идентификатор [indexed]
      • seo_title, seo_description (str): SEO метаданные
      • s_article_teaser_html, s_article_content_html (text): тизер и полный текст статьи
      • i_article_views, i_article_favorites (int): счётчики [indexed]
      • t_article_started, t_article_ended, t_article_created, t_article_updated (datetime)
    
    Методы:
      • save(): генерирует slug автоматически из s_article_title (если не установлен)
      • increment_views(): безопасный инкремент просмотров (F-выражение)
      • increment_favorites(): безопасный инкремент добавлений в избранное
    
    Использование:
      • Соединитель для Artist, Item, Label, Seller, Style (все 1:1→article)
      • Хранит текстовый контент, SEO, изображения справочников
    """
    class ArticleType(models.TextChoices):
        ARTIST = 'artist', 'Artis: артист, группа или бренд'
        STYLE = 'style', 'Slyle: музыкальный стиль'
        ITEM = 'item', 'Item: Альбом, релиз или товар (кассета, hifi, аксессуар)'
        LABEL = 'label', 'Label: Лейбл, издатель или компания'
        OFFER = 'offer', 'Offer: конкретное предложение от продавца'
        SELLER = 'seller', 'Seller: продавец или магазин'
        BLOG = 'blog', 'blog: Новость или блог'
        ACTION = 'action', 'action: Спецпредложение, акция, распродажа и т.д.'
        ADV = 'adv', 'adv: Реклама или баннер'
        HUB = 'HUB', 'hub: СТАТЬЯ-ХАБ (использует DSL для отображения контента)'
        INFO = 'info', 'info: Текстовый контент (для условий конфиденциальности, правил, соглашений и т.д.)'
        OTHER = '?¿?', '?¿?: Другое'

    s_article_title = models.CharField(
        max_length=255,
        blank=False,
        default='',
        unique=True,
        verbose_name='Технический заголовок',
        help_text='Технический заголовок статьи для внутреннего использования, например: "Album: Abbey Road"'
                  ' или "Bio: The Beatles".'
    )
    l_article_type = models.CharField(
        max_length=7,
        blank=True,
        choices=ArticleType.choices,
        default=ArticleType.OTHER,
        db_index=True,
        verbose_name='Тип статьи',
    )
    b_article_published = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Опубликовано',
    )
    t_article_started = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Дата начала публикации',
    )
    t_article_ended = models.DateTimeField(
        blank=True,
        null=True,
        default=None,
        db_index=True,
        verbose_name='Дата окончания публикации',
        help_text='Если указано, статья будет отображаться только между датой начала и датой окончания публикации.'
                  ' Если не указано, статья будет отображаться всегда (или до тех пор, пока не будет удалена '
                  ' или снята с публикации через `b_article_published`)',
    )
    i_article_sort = models.IntegerField(
        default=0,
        db_index=True,
        verbose_name='Приоритет',
        help_text='Сортировка/Приоритет для HUB. Статьи-хабы (и, возможно, обычные статьи) будут сортироваться'
                  ' в первую очередь по этому полю. Чем меньше число, тем выше приоритет. Используется для'
                  ' формирования меню, навигации, разделов и т.д.'
    )
    s_article_title_html = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Заголовок',
        help_text='Заголовок статьи, например: "Описание релиза Abbey Road" или "Биография группы The Beatles".'
                  ' Может содержать HTML-разметку для типографирования (html-мнемоники и -теги). Если не указано,'
                  ' будет отображаться без заголовка.'
    )
    k_article_to_image = FilerImageField(
        # Прямая ссылка на файл изображения из django_filer.
        # Метаданные об этом изображении (сортировка, источник, тип и т.д.) хранятся в TbImageMetadata.k_image_to_image
        on_delete=models.SET_NULL,
        related_name='image_to_article',
        blank=True,
        null=True,
        db_index=True,
        verbose_name='Изображение для статьи',
        help_text='Обложка или иллюстрация статьи из файлового хранилища (django_filer).'
                  ' Для получения метаданных: TbImageMetadata.objects.filter(k_image_to_image=article.k_article_to_image).<br/>'
                  '<b>ВАЖНО</b>: Так как статья привязывается к исполнителям, лейблам, продавцам, музыкальным стилям,'
                  ' её изображение можно использовать как логотип, пиктограмму или баннер этих сущностей. '
                  'Рекомендуется использовать прозрачный фон (движок поддерживает SVG, WebP и PNG).'
    )
    s_article_teaser_html = models.TextField(
        blank=True,
        null=True,
        default='',
        verbose_name='Тизер статьи',
        help_text='Короткий анонс статьи, который будет отображаться в списках. Может содержать HTML-вёрсту (теги,'
                  ' мнемоники, спецсимволы) для типографирования.',
    )
    s_article_content_html = models.TextField(
        blank=True,
        null=True,
        default='',
        verbose_name='Статья',
        help_text='Полный текст статьи. Может содержать HTML-вёрсту (теги, мнемоники, спецсимволы) для'
                  ' типографирования.',
    )
    i_article_views = models.IntegerField(
        # Счетчик просмотров (включая просмотры артиста, итема/релиза/товара, лейбла и продавца)
        default=0,
        db_index=True,  # для сортировки "самые просматриваемые"
        verbose_name='Число просмотров',
    )
    i_article_favorites = models.IntegerField(
        # Счетчик добавлений в избранное (включая избранный артист, item/релиз/товар/лейбл/продавец)
        default=0,
        db_index=True,  # для сортировки "самые добавляемые в избранное"
        verbose_name='Число в избранном',
    )
    slug = models.SlugField(
        max_length=255,
        blank=False,
        default='',
        unique=True,
        db_index=True,
        verbose_name='Слаг статьи',
    )
    j_article_metadata = models.JSONField(
        blank=True,
        null=True,
        default=dict,
        verbose_name='Метаданные статьи',
        help_text='JSON с дополнительными данными статьи. Может быть понадобится. Например, можно хранить информацию'
                  ' об источнике данных, авторе статьи, ссылках на внешние ресурсы, историю переименований slug и т.д.',
    )
    seo_title = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='SEO Title',
        help_text='SEO Title для статьи. Если не указано, будет использоваться заголовок статьи'
                  ' (s_article_title_html) без HTML-тегов.',
    )
    seo_description = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='SEO Description',
        help_text='SEO Description для статьи. Если не указано, будет использоваться обрезанный тизер статьи'
                  ' (s_article_teaser_html) без HTML-тегов.',
    )
    seo_keywords = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='SEO Keywords',
        help_text='SEO Keywords для статьи, через запятую. Например: "The Beatles, Abbey Road, Vinyl, 1969"',
    )
    t_article_created = models.DateTimeField(auto_now_add=True, editable=False, verbose_name="Дата создания",)
    t_article_updated = models.DateTimeField(auto_now=True, editable=False, verbose_name="Дата обновления",
    )

    def __str__(self):
        return f"article {self.id:0>4}: {self.s_article_title}"

    def increment_views(self):
        """Безопасный инкремент просмотров (статьи, артиста, лейбла, продавца, товара/релиза/альбома...)"""
        TbArticle.objects.filter(id=self.id).update(
            i_article_views=F('i_article_views') + 1
        )

    def increment_favorites(self):
        """Безопасный инкремент добавлений в избранное (статьи, артиста, лейбла, продавца, товара/релиза/альбома...)"""
        TbArticle.objects.filter(id=self.id).update(
            i_article_favorites=F('i_article_favorites') + 1
        )

    def save(self, *args, **kwargs):
        """
        Автоматически генерируем slug на основе заголовка статьи.
        Если привязана картинка и метаданных нет — создаем TbImageMetadata с тегами IMG_IS и IMG_FROM.
        Вызывается при каждом сохранении записи (создание или обновление).
        """
        # Если slug не установлен (новая запись) — генерируем его из названия
        if not self.slug:
            # Генерируем базовый slug на основе заголовка статьи
            base_slug = make_slug(self.s_article_title)

            # Проверяем на уникальность и добавляем счетчик если нужно
            # Это гарантирует, что slug будет уникален даже для похожих названий
            slug = base_slug
            counter = 1
            while TbArticle.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        # Сохраняем статью в БД (нужно чтобы потом привязать метаданные картинки)
        super().save(*args, **kwargs)

        # Если картинка привязана и метаданных для неё нет — создаем их
        if self.k_article_to_image:
            # Получаем существующие метаданные (если есть)
            metadata = TbImageMetadata.objects.filter(image=self.k_article_to_image).first()

            adding_metadata = {}
            if not metadata or not KEY_IMAGE_TYPE in (metadata.j_img_metadata or {}):
                adding_metadata[KEY_IMAGE_TYPE] = VALUE_IMAGE_ABSTRACT
            if not metadata or not KEY_IMAGE_FROM in (metadata.j_img_metadata or {}):
                # Получаем username из контекста админки (установлен в ArticleAdmin.save_model())
                # Fallback на 'unknown' если username недоступен (например, при программном создании)
                username = getattr(self, '_admin_username', 'unknown')
                adding_metadata[KEY_IMAGE_FROM] = username
            if not metadata or not KEY_IMAGE_URL in (metadata.j_img_metadata or {}):
                adding_metadata[KEY_IMAGE_URL] = None
            if not metadata or not KEY_IMAGE_NOTE in (metadata.j_img_metadata or {}):
                adding_metadata[KEY_IMAGE_NOTE] = None
            if not metadata:
                metadata = TbImageMetadata.objects.create(
                    image=self.k_article_to_image,
                    i_img_sort=0,
                    j_img_metadata=adding_metadata
                )
            else:
                # Обновляем только недостающие ключи в j_img_metadata
                if adding_metadata:
                    metadata.j_img_metadata.update(adding_metadata)
                metadata.save(update_fields=['j_img_metadata'])
            
            # Заполняем поля filer.Image если они пусты
            # Это улучшает SEO и accessibility (для скринридеров, поисковиков)
            image_needs_update = False
            
            # default_alt_text (alt) — компактное описание для скринридеров и SEO
            if not self.k_article_to_image.default_alt_text:
                # Приоритет: KEY_IMAGE_NOTE → seo_title (оптимизирован для SEO) → fallback
                alt_text = (
                    metadata.j_img_metadata.get(KEY_IMAGE_NOTE) 
                    or self.seo_title 
                    or self.s_article_title[:60]
                )
                self.k_article_to_image.default_alt_text = alt_text
                image_needs_update = True
            
            # default_caption (title) — подробное описание с контекстом
            if not self.k_article_to_image.default_caption:
                # Используем seo_description (оптимизирован для SEO) с добавлением типа и источника
                caption = self.seo_description or self.s_article_title[:80]
                # Добавляем метаинформацию для полноты
                caption = (
                    f"{caption}. "
                    f"Type: {metadata.j_img_metadata[KEY_IMAGE_TYPE]}. "
                    f"Source: {metadata.j_img_metadata[KEY_IMAGE_FROM]}"
                )
                self.k_article_to_image.default_caption = caption
                image_needs_update = True
            
            # Сохраняем картинку, если были изменения
            if image_needs_update:
                self.k_article_to_image.save()
            
            # Примечание: m_offer остаётся NULL т.к. это статья, а не оффер

    class Meta:
        verbose_name = 'Статья'
        verbose_name_plural = 'Статьи'
        ordering = ('-t_article_updated', '-t_article_created', 's_article_title')
        indexes = [
            # Составной индекс: найти опубликованные статьи по типу, отсортированные по свежести (для витрины)
            models.Index(fields=['l_article_type', 'b_article_published', '-t_article_created'],
                        name='idx_articles_by_type_published'),
        ]


# ============================================================================
# МУЗЫКАЛЬНЫЕ СТИЛИ
# ============================================================================
class TbMusicStyle(models.Model):
    """
    Музыкальные стили и жанры.
    
    Поля:
      • id (SmallPK): оптимизировано (до ~32k стилей)
      • s_style_name (str, уникальный): название стиля (Rock, Jazz и т.д.)
      • k_style_to_article (1:1→TbArticle): связанная статья (SEO, слаг, картинка)
      • j_style_metadata (JSON): синонимы из Discogs для матчинга при импорте
      • t_style_created, t_style_updated (datetime)
    
    Связи:
      • M2M←TbArticle.k_article_to_styles: теги стилей к статьям
      • M2M←TbItem.k_item_to_style: жанры альбомов
    
    МЕТОДЫ:
    • save(): управляет синонимами и создаёт связанную статью автоматически
      - При создании/изменении: добавляет название стиля в SYN_EN метаданные
      - Если статья не привязана: создаёт новую через create_or_get_related_article()
    """
    # Используем SmallAutoField для оптимизации (макс ~32k)
    # Стилей обычно 100-1000, поэтому 2 байта достаточно
    id = models.SmallAutoField(primary_key=True)
    s_style_name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name='Стиль (канонический)',
        help_text='Основное название стиля. Например: "Rock", "Jazz", "Classical"',
    )
    k_style_to_article = models.OneToOneField(
        TbArticle,
        on_delete=models.SET_NULL,
        related_name='article_to_style',
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        default=None,
        null=True,
        blank=True,  # <-- Интерфейсное удобство. Связь будет сделана автоматически, и статья создана автоматически.
        verbose_name='Связанная статья',
        help_text='Связанная статья о музыкальном стиле (Типографированные заголовок, тизер и текст статьи. Так же'
                  ' через статью может быть получена картинка, seo атрибуты, слаг (обязательно) и т.п.)<br />'
                  '<b>ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ</b> т.к. через статью получаем слаг для URL музыкального стиля.'
    )
    j_style_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Метаданные',
        help_text='В основном список синонимов/вариантов названия из Discogs, MusicBrainz и т.д. для матчинга.'
                  ' Пример: <tt>{"SYN_EN": ["rock", "Rock Music", "Rock & Roll", "Hard Rock"]}</tt>.',
    )
    t_style_created = models.DateTimeField(auto_now_add=True, editable=False, verbose_name="Дата создания")
    t_style_updated = models.DateTimeField(auto_now=True, editable=False, verbose_name="Дата обновления")

    def __str__(self):
        return self.s_style_name

    def save(self, *args, **kwargs):
        """
        Переопределяем save для управления синонимами музыкального стиля и создания связанной статьи.

        При сохранении музыкального стиля (создание и обновление):
        1. Управляем синонимами:
           - Для новых музыкальных стилей: добавляем текущий s_style_name в SYN_EN
           - При изменении s_style_name: добавляем как старый, так и новый s_style_name в SYN_EN
           - При редактировании: используем j_style_metadata из формы (приоритет админу)
        2. Если статья не привязана - создаём новую статью музыкального стиля автоматически
        3. Генерируем технический заголовок и slug для статьи
        """
        # ===== ВАЛИДАЦИЯ НА ДУБЛИКАТЫ =====
        # Проверяем ДО работы с синонимами и метаданными!
        # Страховка: защита от прямого вызова save() минуя админку или (в будущем) парсер
        validate_and_raise_for_duplicates(self, 's_style_name', 'j_style_metadata')

        # ===== УПРАВЛЕНИЕ СИНОНИМАМИ =====
        # Обновляем список синонимов в метаданных (универсальный хелпер для всех моделей)
        update_synonyms_in_metadata(self, 's_style_name', 'j_style_metadata')

        # ===== СОЗДАНИЕ ИЛИ ПОЛУЧЕНИЕ СВЯЗАННОЙ СТАТЬИ =====
        # Используем универсальный хелпер для создания/поиска статьи
        # Хелпер сам проверит через обратный FK. Не дублирует статьи, даже если админ переименовал
        article = create_or_get_related_article(
            self,
            TbArticle.ArticleType.STYLE,
            's_style_name',
            'j_style_metadata',
            'k_style_to_article'  # ← Явно передаем имя FK поля (избегаем "магии")
        )
        self.k_style_to_article = article

        # Вызываем оригинальный save родительского класса
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Музыкальный стиль'
        verbose_name_plural = 'Музыкальные стили'
        ordering = ('s_style_name',)


# ============================================================================
# ИСПОЛНИТЕЛИ
# ============================================================================
class TbArtist(models.Model):
    """
    Исполнители и музыкальные группы.
    
    Поля:
      • id (SmallPK): оптимизировано
      • s_artist (str, уникальный): название исполнителя
      • k_artist_to_article (1:1→TbArticle): связанная статья (SEO, слаг, картинка)
      • t_artist_created, t_artist_updated (datetime)
    
    Связи:
      • M2M←TbItem.k_item_to_artist: коллаборации (артист может быть на нескольких альбомах)
    
    МЕТОДЫ:
    • save(): управляет синонимами и создаёт связанную статью автоматически
      - При создании/изменении: добавляет названия артиста в SYN_EN метаданные
      - Если статья не привязана: создаёт новую через create_or_get_related_article()
    """
    # Используем SmallAutoField для оптимизации (макс ~32k)
    # Артистов в базе может быть несколько тысяч, достаточно
    id = models.SmallAutoField(primary_key=True)
    s_artist = models.CharField(
        max_length=128,
        unique=True,
        verbose_name='Исполнитель',
        help_text='Техническое название исполнителя для внутреннего использования, например: "The Beatles" или'
                  '"David Bowie".'
    )
    k_artist_to_article = models.OneToOneField(
        TbArticle,
        on_delete=models.SET_NULL,
        related_name='article_to_artist',
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        default=None,
        null=True,
        blank=True,     # <-- Интерфейсное удобство. Связь будет сделана автоматически, и статья создана автоматически.
        verbose_name='Связанная статья',
        help_text='Связанная статья об исполнителе (Типографированные заголовок, тизер и текст статьи. Так же'
                  ' через статью может быть получена <b>картинка<b>, seo атрибуты, слаг (обязательно) и т.п.)<br />'
                  '<b>ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ</b> т.к. через статью получаем слаг для URL артиста.'
    )
    j_artist_metadata = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name='Метаданные JSON',
        help_text='В основном список синонимов/вариантов названия из Discogs, MusicBrainz и т.д. для матчинга.'
                  ' Пример: <tt>{"SYN_EN": ["The Beatles", "Beatles", "Beatles, The"]}</tt>.',
    )
    t_artist_created = models.DateTimeField(auto_now_add=True, editable=False, verbose_name="Дата создания",)
    t_artist_updated = models.DateTimeField(auto_now=True, editable=False, verbose_name="Дата обновления",
    )

    def __str__(self):
        return f"artist {self.id:0>4}: {self.s_artist}"

    def save(self, *args, **kwargs):
        """
        Переопределяем save для управления синонимами исполнителей и создания связанной статьи.

        При сохранении исполнителя (создание и обновление):
        1. Управляем синонимами:
           - Для новых исполнителей: добавляем текущий s_artist в SYN_EN
           - При изменении s_artist: добавляем как старый, так и новый s_artist в SYN_EN
           - При редактировании: используем j_artist_metadata из формы (приоритет админу)
        2. Если статья не привязана - создаём новую статью исполнителя автоматически
        3. Генерируем технический заголовок и slug для статьи
        """
        # ===== ВАЛИДАЦИЯ НА ДУБЛИКАТЫ =====
        # Проверяем ДО работы с синонимами и метаданными!
        # Страховка: защита от прямого вызова save() минуя админку или (в будущем) парсер
        validate_and_raise_for_duplicates(self, 's_artist', 'j_artist_metadata')

        # ===== УПРАВЛЕНИЕ СИНОНИМАМИ =====
        # Обновляем список синонимов в метаданных (универсальный хелпер для всех моделей)
        update_synonyms_in_metadata(self, 's_artist', 'j_artist_metadata')

        # ===== СОЗДАНИЕ ИЛИ ПОЛУЧЕНИЕ СВЯЗАННОЙ СТАТЬИ =====
        # Используем универсальный хелпер для создания/поиска статьи
        # Хелпер сам проверит через обратный FK, не дублирует статьи даже если админ переименовал
        article = create_or_get_related_article(
            self,
            TbArticle.ArticleType.ARTIST,
            's_artist',
            'j_artist_metadata',
            'k_artist_to_article'  # ← Явно передаем имя FK поля (избегаем "магии")
        )
        self.k_artist_to_article = article

        # Вызываем оригинальный save родительского класса
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Исполнитель'
        verbose_name_plural = 'Исполнители'
        ordering = ('s_artist',)
        # index_together = ('t_artist_created', 't_artist_updated', 'k_artist_to_article')


class TbItem(models.Model):
    """
    Товары в каталоге: релизы (альбомы, синглы), носители, аксессуары.
    
    Поля:
      • id (PK), s_item (str, уникальный): название товара
      • k_item_to_artist (M2M→TbArtist): исполнители (коллаборации)
      • k_item_to_style (M2M→TbMusicStyle): жанры альбома
      • k_item_to_article (1:1→TbArticle): связанная статья (SEO, слаг, картинка)
      • s_item_date (str): дата релиза (текстовая, неполная) [indexed]
      • t_item_date (date): нормализованная дата релиза [indexed]
      • i_discogs_master_id (int): ID мастер-релиза на Discogs
      • t_item_created, t_item_updated (datetime)
    
    Использование:
      • Один товар может быть в нескольких TbOffer от разных продавцов
      • M2M с TbArtist для поддержки коллабораций
      • M2M с TbMusicStyle для жанров
    
    МЕТОДЫ:
    • save(): управляет синонимами и создаёт связанную статью автоматически
      - При создании/изменении: добавляет названия товара в SYN_EN метаданные
      - Если статья не привязана: создаёт новую через create_or_get_related_article()
    """
    s_item = models.CharField(
        max_length=128,
        unique=True,
        verbose_name='Товар',
        help_text='Техническое название товара (альбома, релиза, аксессуара) для внутреннего использования,'
                  'например: "Abbey Road (LP)" или "TDK CDing I (кассета для записи)".'
    )
    k_item_to_artist = models.ManyToManyField(
        # Исполнители (ManyToMany для поддержки коллабораций)
        # Например: "David Bowie & Queen", "Elton John & Tim Rice"
        TbArtist,
        blank=True,     # Исполнителя может и не быть (например для сборников)
        related_name='artist_to_item',  # artist.products.all() — найти все релизы артиста
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Исполнители',
        help_text="Один или несколько для коллабораций",
    )
    k_item_to_style = models.ManyToManyField(
        # Музыкальные стили (ManyToMany для альбомов с множеством жанров)
        # Например: "Abbey Road" → [Rock, Progressive Rock, ...]
        # Позволяет: найти все альбомы стиля / найти стили альбома / найти артистов в стиле
        TbMusicStyle,
        blank=True,     # Стиль может быть не указан (например для аксессуаров)
        related_name='style_to_item',  # style.style_to_item.all() — найти все релизы в стиле
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Музыкальные стили',
        help_text='Один или несколько стилей, характеризующих альбом/товар. Например: Rock, Progressive Rock.',
    )
    k_item_to_article = models.OneToOneField(
        TbArticle,
        on_delete=models.SET_NULL,
        related_name='article_to_item',
        db_index=True,
        default=None,
        null=True,
        blank=True,
        verbose_name='Связанная статья',
        help_text='Связанная статья об альбоме/релизе/товаре (Типографированные заголовок, тизер и текст статьи.'
                  ' Так же через статью может быть получена <b>картинка</b>, seo атрибуты, слаг (обязательно) и т.п.)<br />'
                  '<b>ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ</b> т.к. через статью получаем слаг для URL альбома/релиза/товара.'
    )
    s_item_date = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        db_index=True,
        default='XXXX-XX-XX',
        verbose_name='Дата релиза (str)',
        help_text='Например: 1969-05-25, или 1969-05-XX (если день неизвестен), или 1969-XX-XX (если известен только'
                  ' год, или XXXX-XX-XX (если дата релиза неизвестна). Менее приоритетное поле для отображения даты'
                  ' релиза, чем t_release_date, так как может содержать неполную дату и/или текстовую информацию.'
                  ' Срабатывает только если t_release_date не указано.'
    )
    t_item_date = models.DateField(
        blank=True,
        null=True,
        db_index=True,
        verbose_name='Дата релиза',
        help_text='Полная дата если известна, например: 1969-09-26. Если точно известен.',
    )
    i_discogs_master_id = models.IntegerField(
        blank=True,
        null=True,
        default=None,
        verbose_name='ID на мастер-релиз Discogs',
        help_text='Уникальный идентификатор мастер-релиза на Discogs, если он там есть. Например: <tt>306323</tt>',
    )
    j_item_metadata = models.JSONField(
        default=dict, blank=True, null=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные и метаданные релиза (страна, жанр, количество треков и т.д.) или товавра'
                  ' в виде JSON-словаря. Сюда же включены варианты написания релиза в источниках',
    )
    t_item_created = models.DateTimeField(auto_now_add=True, editable=False, verbose_name="Дата создания",)
    t_item_updated = models.DateTimeField(auto_now=True, editable=False, verbose_name="Дата обновления",)

    def __str__(self):
        return f"Item {self.id:0>4}: {self.s_item}"

    def save(self, *args, **kwargs):
        """
        Переопределяем save для управления синонимами релиза (альбома) или просто товара и создания связанной статьи.

        При сохранении релиза/альбома (создание и обновление):
        1. Управляем синонимами альбома/релиза/товара:
           - Для новых альбомов/релиза/товара: добавляем в SYN_EN
           - При изменении s_item: добавляем как старый, так и новый s_item в SYN_EN
           - При редактировании: используем j_item_metadata из формы (приоритет админу)
        2. Если статья не привязана - создаём новую автоматически
        3. Генерируем технический заголовок и slug для статьи
        """
        # ===== ВАЛИДАЦИЯ НА ДУБЛИКАТЫ =====
        # Проверяем ДО работы с синонимами и метаданными!
        # Страховка: защита от прямого вызова save() минуя админку или (в будущем) парсер
        validate_and_raise_for_duplicates(self, 's_item', 'j_item_metadata')

        # ===== УПРАВЛЕНИЕ СИНОНИМАМИ =====
        # Обновляем список синонимов в метаданных (универсальный хелпер для всех моделей)
        update_synonyms_in_metadata(self, 's_item', 'j_item_metadata')

        # ===== СОЗДАНИЕ ИЛИ ПОЛУЧЕНИЕ СВЯЗАННОЙ СТАТЬИ =====
        # Используем универсальный хелпер для создания/поиска статьи
        # Хелпер сам проверит через обратный FK, не дублирует статьи даже если админ переименовал
        article = create_or_get_related_article(
            self,
            TbArticle.ArticleType.ITEM,
            's_item',
            'j_item_metadata',
            'k_item_to_article'  # ← Явно передаем имя FK поля (избегаем "магии")
        )
        self.k_item_to_article = article

        # Вызываем оригинальный save родительского класса
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Товар в каталоге (релиз, носитель, аксессуар)'
        verbose_name_plural = 'Товары в каталоге'
        ordering = ('s_item',)


# ============================================================================
# ЛЕЙБЛЫ (производители релизов)
# ============================================================================
class TbLabel(models.Model):
    """
    Лейблы и издатели релизов.
    
    Поля:
      • id (SmallPK): оптимизировано
      • s_label (str, уникальный): название лейбла (Sony, Мелодия, TDK, Pioneer и т.д.)
      • k_label_to_article (1:1→TbArticle): связанная статья (SEO, слаг, картинка)
      • t_label_created, t_label_updated (datetime)
    
    Связи:
      • 1:M←TbOffer.k_offer_to_label: предложения от этого лейбла
    
    МЕТОДЫ:
    • save(): управляет синонимами и создаёт связанную статью автоматически
      - При создании/изменении: добавляет названия лейбла в SYN_EN метаданные
      - Если статья не привязана: создаёт новую через create_or_get_related_article()
    """
    # Используем SmallAutoField для оптимизации (макс ~32k)
    # Лейблов обычно несколько сотен-тысяч, достаточно
    id = models.SmallAutoField(primary_key=True)
    s_label = models.CharField(
        max_length=128,
        blank=False,
        unique=True,
        verbose_name='Лейбл',
        help_text='Название лейбла. Например: "Sony Records" или "Мелодия"... Представление на самом сайте, с версткой,'
                  ' будет определиться через статью, связанную с лейблом (TbArticle).'
    )
    k_label_to_article = models.OneToOneField(
        TbArticle,
        on_delete=models.SET_NULL,
        related_name='article_to_label',
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        default=None,
        null=True,
        blank=True,     # <-- Интерфейсное удобство. Связь будет сделана автоматически, и статья создана автоматически.
        verbose_name='Связанная статья',
        help_text='Связанная статья об лейбле (Типографированные заголовок, тизер и текст статьи.'
                  ' Так же через статью может быть получена <b>картинка</b>, seo атрибуты, слаг (обязательно) и т.п.)<br />'
                  '<b>ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ</b> т.к. через статью получаем слаг для URL лейбла.'
    )
    j_label_metadata = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name='Метаданные',
        help_text='JSON: страна лейбла, официальный сайт и т.д. Включая список синонимов/вариантов названия для матчинга.'
                  ' Пример: <tt>{"SYN_EN": ["Island", "Island Records", "Vertigo France"]}</tt>.'
        ,
    )
    t_label_created = models.DateTimeField(auto_now_add=True, editable=False, verbose_name="Дата создания",)
    t_label_updated = models.DateTimeField(auto_now=True, editable=False, verbose_name="Дата обновления",)

    def __str__(self):
        return f"label: {self.id:0>5}: {self.s_label}"

    def save(self, *args, **kwargs):
        """
        Переопределяем save для управления синонимами лейблов и создания связанной статьи.

        При сохранении лейбла (создание и обновление):
        1. Управляем синонимами лейбла:
           - Для новых лейблов: добавляем текущий s_label в SYN_EN
           - При изменении s_label: добавляем как старый, так и новый s_label в SYN_EN
           - При редактировании: используем j_label_metadata из формы (приоритет админу)
        2. Если статья не привязана - создаём новую автоматически
        3. Генерируем технический заголовок и slug для статьи
        """
        # ===== ВАЛИДАЦИЯ НА ДУБЛИКАТЫ =====
        # Проверяем ДО работы с синонимами и метаданными!
        # Страховка: защита от прямого вызова save() минуя админку или (в будущем) парсер
        validate_and_raise_for_duplicates(self, 's_label', 'j_label_metadata')

        # ===== УПРАВЛЕНИЕ СИНОНИМАМИ =====
        # Обновляем список синонимов в метаданных (универсальный хелпер для всех моделей)
        update_synonyms_in_metadata(self, 's_label', 'j_label_metadata')

        # ===== СОЗДАНИЕ ИЛИ ПОЛУЧЕНИЕ СВЯЗАННОЙ СТАТЬИ =====
        # Используем универсальный хелпер для создания/поиска статьи
        # Хелпер сам проверит через обратный FK, не дублирует статьи даже если админ переименовал
        article = create_or_get_related_article(
            self,
            TbArticle.ArticleType.LABEL,
            's_label',
            'j_label_metadata',
            'k_label_to_article'  # ← Явно передаем имя FK поля (избегаем "магии")
        )
        self.k_label_to_article = article

        # Вызываем оригинальный save родительского класса
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Лейбл'
        verbose_name_plural = 'Лейблы'
        ordering = ('s_label',)


# ============================================================================
# ПРОДАВЦЫ / МАГАЗИНЫ
#     - Валюта привязана к продавцу. Если у продавца несколько валют,
#       создаем несколько продавцов с разными валютами.
# ============================================================================
class TbSeller(models.Model):
    """
    Продавцы и магазины.
    
    Поля:
      • id (SmallPK): оптимизировано
      • s_seller (str, уникальный): название продавца [indexed]
      • l_seller_type (choice): тип (seller, label, diy, crowdfunding, other)
      • l_seller_currency (choice): валюта (RUB, USD, EUR, JPY и т.д.)
      • k_seller_to_article (1:1→TbArticle): связанная статья (SEO, слаг, картинка, контакты)
      • j_seller_metadata (JSON): доп. данные (ссылки, контакты, соцсети)
      • t_seller_created, t_seller_updated (datetime)
    
    Связи:
      • 1:M→TbSource.k_source_to_seller: источники данных от этого продавца
      • 1:M→TbOffer (через TbSource): предложения товаров
    
    МЕТОДЫ:
    • save(): создаёт связанную статью автоматически (синонимы не используются)
      - Если статья не привязана: создаёт новую через create_or_get_related_article()
    """
    class SellerType(models.TextChoices):
        SELLER = 'seller', 'Продавец'
        LABEL = 'label', 'Лейбл (издатель)'
        DIY = 'diy', 'Самиздат группы'
        CROWD = 'crowd', 'Краудфандинг'
        OTHER = '???', 'Другое'

    class Currency(models.TextChoices):
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

    # Используем SmallAutoField для оптимизации (макс ~32k)
    # Продавцов обычно до 1000-10000, поэтому достаточно
    id = models.SmallAutoField(primary_key=True)
    s_seller = models.CharField(
        max_length=128,
        blank=False,
        unique=True,
        verbose_name='Название продавца',
        help_text='Техническое название продавца или магазина. Например: <tt>Клюква Рекодс</tt>. Может совпадать'
                  ' с названием продавца, если лейбл сам реализует свои издания через сайт.',
    )
    l_seller_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.RUB,
        verbose_name='Валюта источника',
        help_text='В какой валюте указаны цены в этом источнике. Все офферы из этого источника будут в этой валюте.',
    )
    k_seller_to_article = models.OneToOneField(
        TbArticle,
        on_delete=models.SET_NULL,
        related_name='article_to_seller',
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        default=None,
        null=True,
        blank=True,     # <-- Интерфейсное удобство. Связь будет сделана автоматически, и статья создана автоматически.
        verbose_name='Связанная статья',
        help_text='Связанная статья о продавце (HTML-готовые заголовок, тизер и текст статьи).'
                  ' Так же через статью может быть получена <b>картинка</b>, seo атрибуты, слаг (обязательно) и т.п.)<br />'
                  '<b>ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ</b> т.к. через статью получаем слаг для URL продавца.'
    )
    l_seller_type = models.CharField(
        max_length=6,
        default=SellerType.SELLER,
        choices=SellerType.choices,
        verbose_name='Тип продавца',
    )
    j_seller_metadata = models.JSONField(
        default=dict, blank=True, null=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные о продавце в виде JSON-словаря. Телефон, email, адрес, ссылка на сайт и т.д.',
    )
    t_seller_created = models.DateTimeField(auto_now_add=True, editable=False, verbose_name="Дата создания",)
    t_seller_updated = models.DateTimeField(auto_now=True, editable=False, verbose_name="Дата обновления",)

    def __str__(self):
        return f"seller: {self.id:0>2}: {self.s_seller}"

    def save(self, *args, **kwargs):
        """
        Переопределяем save для привязки связанной статьи о продавце.

        0. ВАЖНО: Продавцам не нужны синонимы (хотя технически возможно), потому синонимы не проверяем и не обновляем
        1. Если статья не привязана - создаём новую статью исполнителя автоматически
        2. Генерируем технический заголовок и slug для статьи
        """
        # ===== СОЗДАНИЕ ИЛИ ПОЛУЧЕНИЕ СВЯЗАННОЙ СТАТЬИ =====
        # Используем универсальный хелпер для создания/поиска статьи
        # Хелпер сам проверит через обратный FK, не дублирует статьи даже если админ переименовал
        article = create_or_get_related_article(
            self,
            TbArticle.ArticleType.SELLER,
            's_seller',
            'j_seller_metadata',
            'k_seller_to_article'  # ← Явно передаем имя FK поля (избегаем "магии")
        )
        self.k_seller_to_article = article

        # Вызываем оригинальный save родительского класса
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Продавец'
        verbose_name_plural = 'Продавцы'
        ordering = ('s_seller',)


# ============================================================================
# ПРЕДЛОЖЕНИЯ / ОФФЕРЫ
# ============================================================================
class TbOffer(models.Model):
    """
    Конкретное предложение от продавца.
    Один и тот же релиз может быть несколько раз в системе от разных продавцов.
    
    УНИКАЛЬНЫЙ КОД (s_offer_code):
    Генерируется автоматически при создании нового оффера с помощью hashids-кодирования:
    - При первом сохранении: рассчитывается из id через Skip32 + Base62/Base64 обфускацию
    - При обновлении: код НЕ изменяется (используется для отслеживания в корзине и заказах)
    - Уникален в пределах системы (UNIQUE constraint)
    - Используется в QR-кодах и ссылках (вместо прямого id для конфиденциальности)
    
    ИСТОРИЯ ЦЕНЫ И КОЛИЧЕСТВА (TbOfferHistory):
    При каждом сохранении оффера система автоматически отслеживает изменения:
    - Если это новый оффер: создаёт первую запись истории с текущей ценой/количеством
    - Если цена или количество изменились: создаёт новую запись истории
    - История помогает отслеживать динамику наличия и ценообразования
    - Поле t_history_created можно редактировать для импорта исторических данных
    
    СВЯЗЬ С КАРТИНКАМИ:
    Картинки к офферу управляются через TbImageMetadata (промежуточная таблица M2M):
    - offer.m_image.all() — все картинки этого офера (упорядочены по i_img_sort)
    - Каждая запись TbImageMetadata содержит: k_image_to_image (FK на Image), i_img_sort, j_img_metadata
    - Метаданные: порядок сортировки, тип изображения, источник, заметки и т.д.
    
    МЕТОДЫ:
    • save(): двухэтапное сохранение:
      1. Вызывает super().save() чтобы получить id для кодирования
      2. Кодирует id в s_offer_code через hashids (только для новых офферов!)
      3. Вызывает update(s_offer_code=...) чтобы обновить БД с кодом
    • save(): отслеживает изменения цены/кол-ва → создает TbOfferHistory
    
    В админке M2M выглядит как список картинок с сортировкой и метаданными.
    """
    class Condition(models.TextChoices):
        S = 's', 'Still Sealed (новое, запечатано)'
        M = 'm', 'Mint (новое, распакованное)'
        NM = 'nm', 'Near Mint (почти новое)'
        VG = 'vg', 'Very Good (очень хорошее)'
        G = 'g', 'Good (хорошее)'
        F = 'f', 'Fair (удовлетворительное)'
        P = 'p', 'Poor (плохое)'
        OTHER = '??', 'Other'

    class Format(models.TextChoices):
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

    s_offer = models.CharField(
        max_length=128,
        blank=False,
        db_index=True,
        verbose_name='Название оффера',
        help_text='Техническое название оффера для внутреннего использования, например:'
                  ' "Abbey Road (LP) AnTrop NM/NM (МЗГ)" или "TDK CDing I 60 (б/у) VG/VG (Janan, 198x синяя-градиент)"'
    )
    l_offer_to_format = models.CharField(
        max_length=2,
        choices=Format.choices,
        default=Format.OTHER,
        db_index=True,
        verbose_name='Формат',
        help_text='Форматы основного носителей (пластинка, CD, кассета и т.п.). Если несколько носителей (и разных),'
                  ' то это указывать в "Дополнительных данных" в JSON-формате. Например:'
                  ' <tt>{"OFR_MF": {"lp": 2, "cd": 1},}</tt>',
    )
    # Связи
    k_offer_to_article = models.ForeignKey(
        TbArticle,
        on_delete=models.SET_NULL,
        related_name='article_to_offer',
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        default=None,
        null=True,
        blank=True,     # <-- Интерфейсное удобство. Статья НЕ БУДЕТ СОЗДАНА автоматически.
        verbose_name='Связанная статья',
        help_text='Связанная статья об оффере (HTML-готовые заголовок, тизер и текст статьи).'
                 ' Так же через статью может быть получена картинка, seo атрибуты, слаг (обязательно) и т.п.)<br />'
                 '<b>МОЖНО НЕ УКАЗЫВАТЬ</b> т.к. URL оффера (для корзины) формируется через id или хеш.'
    )
    k_offer_to_item = models.ForeignKey(
        TbItem,
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name='item_to_offer',  # ← product.item_to_offer.all()
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Релиз (товар)',
    )
    k_offer_to_label = models.ForeignKey(
        TbLabel,
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name='label_to_offer',  # ← label.label_to_offers.all()
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Лейбл/Производитель',
        help_text='Лейбл, на котором был выпущен релиз (если известен), или производитель для аудиио-кассет и MD'
                  ' под запись, технику или аксессуар.',
    )
    k_offer_to_source = models.ForeignKey(
        to='TbSource',
        null=True,
        default=None,
        on_delete=models.CASCADE,  # ← если удалён источник, удалены все офферы
        related_name='source_to_offer',
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Источник данных',
        help_text='Обязательно - каждый оффер должен иметь источник. Через источник получаем данные '
                  'продавца: offer.k_offer_to_source.k_source_to_seller',
    )
    # Изображения (M2M к filer.Image через TbImageMetadata промежуточную таблицу)
    m_offer_to_image = models.ManyToManyField(
        'filer.Image',
        through='TbImageMetadata',
        related_name='m_image_to_offer',
        blank=True,
        verbose_name='Изображения товара',
        help_text='Картинки этого предложения (обложка, задник, фото и т.д). '
                  'Управляются в админке TbImageMetadata с сортировкой (i_img_sort) и метаданными (j_img_metadata). '
                  'Доступ в коде: '
                  'offer.m_image.all() (все TbImageMetadata, отсортированные) или '
                  'offer.m_offer_to_image.all() (все картинки). '
                  'Каждая запись TbImageMetadata содержит: image, m_offer, i_img_sort, j_img_metadata.',
    )
    # Характеристики
    s_offer_catalog_num = models.TextField(
        blank=True,
        default='',
        verbose_name='Каталожный номер / Barcode',
        help_text='Например: "SD 16023" или "5099923452355"',
    )
    b_offer_is_preorder = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Предзаказ',
        help_text='Если товар доступен только для предзаказа',
    )
    d_offer_date_release = models.DateField(
        blank=True,
        null=True,
        default=None,
        db_index=True,
        verbose_name='Дата релиза',
        help_text='Дата релиза (например, дата выпуска переиздания) или выхода по предзаказу, если она известна',
    )
    i_offer_discogs_id = models.IntegerField(
        blank=True,
        default=0,
        verbose_name='ID на релиз Discogs',
        help_text='Уникальный идентификатор релиза на Discogs, если он там есть. Например: <tt>306323</tt>',
    )
    l_offer_condition_media = models.CharField(
        max_length=2,
        choices=Condition.choices,
        default=Condition.S,
        verbose_name="Состояние носителя",
        help_text='Состояние носителя (пластинки, CD и т.п.) по шкале от "Still Sealed" (запечатано) до "Poor" (плохое).',
    )
    l_offer_condition_sleeve = models.CharField(
        max_length=2,
        choices=Condition.choices,
        default=Condition.S,
        verbose_name="Состояние обложки",
        help_text='Состояние обложки по шкале от "Still Sealed" (запечатано) до "Poor" (плохое).',
    )
    # Цена и наличие
    f_offer_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        db_index=True,   # <-- Чтобы можно было сортировать по цене
        verbose_name='Цена',
        help_text='Цена в валюте источника. Валюта определяется в TbSource: offer.k_offer_to_source.l_currency',
    )
    i_offer_quantity = models.IntegerField(
        # Устанавливая количество в ноль, можно указать, что предложение в настоящее время не доступно.
        blank=True,
        default=0,
        verbose_name='Количество в наличии',
    )
    i_offer_discount_to_daily_sale = models.IntegerField(
        blank=True,
        default=0,
        db_index=True,   # <-- Чтобы можно было сортировать по скидке и быстро выбирать то, что участвует в распродажах
        verbose_name='Возможна cкидка (%)',
        help_text='Процент возможной скидки, если участвует в "ежедневной распродаже" или акции. Если указано'
                  ' <tt>0</tt> то данное предложение не может участвовать в распродажах, спецпредложениях и акциях',
    )
    j_offer_metadata = models.JSONField(
        # Метаданные оффера (сырые данные из источника, координаты в Excel и т.д.)
        default=get_offer_metadata_default,
        null=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные о предложении в виде JSON-словаря. Например:<pre style=\"'
                  'background-color:#80808080;border:1px solid #ccc; padding:1ex;max-width: calc(75% - 13em);\">{\n'
                  f'  \"{KEY_OFFER_NOTE}\": \"Уценка: замят угол конверта, повреждены наклейки.\",\n'
                  f'  \"{KEY_OFFER_ALL_MEDIA}\": '
                  '{\n    "lp": 2,\n    "cd": 1\n  }\n}</pre>'
                  f'Ключи:<ul>'
                  f'  <li>\"{KEY_OFFER_NOTE}\" — Примечание к офферу</li>'
                  f'  <li>\"{KEY_OFFER_ALL_MEDIA}\" — Какие носители входят в коммерческое предложение.<br/>'
                  ' Допустимые значения: \"lp\" — Vinyl Long-Play (12"), \"ep\" — Vinyl Extended-Play (12\", 10\",'
                  ' 7\"), \"45\" — Vinyl 7\" (45 rpm), \"cd\" — Compact Disc, \"ld\" — LaserDisc,'
                  ' \"md\" — MiniDisc Record, \"ms\" — Used MiniDisc (для записи),'
                  ' \"cs\" — Cassette Record, \"uc\" — Used Cassette (для записи),'
                  ' \"tp\" — Tape Reel Record, \"ur\" — Used Tape Reel (для записи),'
                  ' \"??\" — Other</li></ul>',
    )
    s_offer_code = models.CharField(
        max_length=12,
        unique=True,
        verbose_name='Код товара',
        help_text='Уникальный код товара для идентификации в корзине и при заказе (чтобы не светить id).'
                  ' Например: "4gfFCJ". Формируется автоматически через Hashids на основе ID оффера.'
                  ' <b>Не редактировать вручную!</b>',
    )
    i_offer_views = models.IntegerField(
        default=0,
        db_index=True,
        verbose_name='Просмотры',
    )
    i_offer_favorites = models.IntegerField(
        default=0,
        db_index=True,
        verbose_name='В избранном',
    )
    t_offer_created = models.DateTimeField(auto_now_add=True, editable=False, verbose_name="Дата создания",)
    t_offer_updated = models.DateTimeField(auto_now=True, editable=False, verbose_name="Дата обновления",)

    def __str__(self):
        seller = self.k_offer_to_source.k_source_to_seller.s_seller if (self.k_offer_to_source
                                                              and self.k_offer_to_source.k_source_to_seller) else "?"
        return (f"[{self.s_offer_code:0>6}]\u00A0«{self.s_offer}»"
                f" ⟶\u00A0item\u00A0«{self.k_offer_to_item_id}»"
                f" ⟶\u00A0seller\u00A0«{seller}»")

    def increment_views(self):
        """Безопасный инкремент просмотров оффера"""
        TbOffer.objects.filter(id=self.id).update(
            i_offer_views=F('i_offer_views') + 1
        )

    def increment_favorites(self):
        """Безопасный инкремент добавлений в избранное оффера"""
        TbOffer.objects.filter(id=self.id).update(
            i_offer_favorites=F('i_offer_favorites') + 1
        )

    def save(self, *args, **kwargs):
        """
        Переопределенный метод save для:
        1. Автоматического формирования s_offer_code (криптографический код)
        2. Записи истории изменений цены и количества в TbOfferHistory
        
        ЛОГИКА s_offer_code:
        - Для новых оферов: генерируем код после получения ID
        - Для старых оферов БЕЗ кода: кодируем существующий ID (миграция)
        - Для старых оферов С кодом: не трогаем
        
        ЛОГИКА истории (TbOfferHistory):
        - При первом сохранении: создаем первую запись с ценой и количеством
        - При обновлении: если цена или количество изменилось → создаем новую запись
        - Это позволяет отследить полную историю изменений
        """
        # 1. Проверяем нужно ли генерировать s_offer_code:
        # - ИЛИ это новый объект (self.pk == None)
        # - ИЛИ это старый объект без s_offer_code (миграция)
        if not self.pk or not self.s_offer_code:
            # Если это новый оффер, сначала сохраняем, чтобы получить ID
            if not self.pk:
                # Сохраняем БЕЗ s_offer_code чтобы Django создал запись и присвоил pk
                super().save(*args, **kwargs)
                # После save() Django автоматически заполнит self.pk

            # Кодируем pk в компактный, необратимый код
            # Пример: pk=42 → "QBErd8"
            self.s_offer_code = Hashids(salt=OFFER_HASHIDS_SALT, min_length=OFFER_HASHIDS_MIN_LENGTH).encode(self.pk)

            # Сохраняем только поле s_offer_code (не перезаписываем остальное)
            super().save(update_fields=['s_offer_code'])
        else:
            # Оффер существует И уже имеет s_offer_code: сохраняем как обычно
            # Не трогаем s_offer_code, он был сформирован при создании
            super().save(*args, **kwargs)

        # 2. Записывает историю изменений цены и количества в TbOfferHistory.
        # Пытаемся получить последнюю (самую свежую) запись в истории
        latest_history = TbOfferHistory.objects.filter(
            k_history_to_offer_id=self.pk
        ).order_by('-t_history_created').first()

        if latest_history is None \
                or self.f_offer_price != latest_history.f_history_price \
                or self.i_offer_quantity != latest_history.i_history_quantity:
            # Нет истории для этого офера, или изменилась цена/количество -> создаем новую запись в истории
            TbOfferHistory.objects.create(
                k_history_to_offer_id=self.pk,
                f_history_price=self.f_offer_price,
                i_history_quantity=self.i_offer_quantity,
                # TODO: когда появится парсер, нужно будет добавить и запись поля `j_history_metadata` с информацией
                #  откуда "прилетели" изменения (или координаты ячеек в EXCEL, или CSS-селектор и URL, или что-то ещё)
            )

    class Meta:
        verbose_name = 'Оффер (предложение)'
        verbose_name_plural = 'Офферы (предложения)'
        ordering = ('-t_offer_updated', '-t_offer_created', 's_offer')
        indexes = [
            # Составной индекс: найти все офферы товара, отсортировать по цене (для витрины)
            models.Index(fields=['k_offer_to_item', '-f_offer_price'], name='idx_offer_by_item_price'),
            ## Составной индекс: для фильтра распродаж - по источнику и скидке
            # models.Index(fields=['k_offer_to_source', '-i_offer_discount_to_daily_sale'], name='idx_offer_by_source_discount'),
            # Составной индекс: найти актуальные офферы по товару (есть в наличии)
            models.Index(fields=['k_offer_to_item', 'i_offer_quantity'], name='idx_offer_by_item_qty'),
        ]
        # ПРИМЕЧАНИЕ: UniqueConstraint на (item, source, format) удален, т.к. k_offer_to_format теперь M2M.
        # M2M не поддерживают участие в constraints. Уникальность на уровне БД не требуется.


# ============================================================================
class TbSource(models.Model):
    """
    Источники данных для импорта офферов (Excel, CSV, URL, ручной ввод).
    
    Поля:
      • id (SmallPK): оптимизировано
      • k_source_to_seller (FK→TbSeller): от какого продавца это данные [indexed]
      • l_source_type (choice): тип источника (excel, csv, url, other)
      • s_source_name (str): название источника для удобства
      • source_file (FilerFileField): загруженный файл (если Excel/CSV)
      • s_source_url (str): URL источника (если URL)
      • t_source_data (date): дата данных (когда их получили)
      • j_source_metadata (JSON): структура источника (вкладки, столбцы, CSS-селекторы и т.д.)
      • t_source_created, t_source_updated (datetime)
    
    Связи:
      • 1:M→TbOffer.k_offer_to_source: офферы из этого источника
    
    МЕТОДЫ:
    • Нет переопределённых методов save(). Используется стандартное поведение Django.
    """
    class SourceType(models.TextChoices):
        EXCEL = 'excel', 'Excel-файл от продавца или издателя'
        CSV = 'csv', 'CSV-файл от продавца или издателя'
        URL = 'url', 'URL страницы с данными (например, HTML-страница с каталогом товаров)'
        OTHER = '??', 'Другое (включая ручной ввод)'

    # Используем SmallAutoField для оптимизации (макс ~32k)
    # Источников обычно до 1000, достаточно
    id = models.SmallAutoField(primary_key=True)
    k_source_to_seller = models.ForeignKey(
        TbSeller,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name='seller_to_source',
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Продавец',
    )
    s_source_name = models.CharField(
        max_length=128,
        blank=True,
        default='',
        verbose_name='Название источника',
        help_text='Название источника данных (для удобства), например: <tt>Предзаказ на RSD-2025 от Полуэкта.</tt>',
    )
    l_source_type = models.CharField(
        max_length=5,
        default=SourceType.EXCEL,
        choices=SourceType.choices,
        verbose_name='Тип источника',
        help_text='Тип источника данных, например: <tt>Excel-файл от продавца или издателя</tt>, <tt>URL страницы'
                  ' с данными</tt> и т.д.',
    )
    t_source_data = models.DateField(
        blank=True, default=datetime.date.today,
        verbose_name='Дата данных',
        help_text='Дата, к которой относятся данные в источнике. Например, если это исторический Excel-файл.',
    )
    source_file = FilerFileField(
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        # TODO:
        # 1. Чтобы файлы автоматически привязывались к нужной виртуальной папке filer при загрузке через Django Admin.
        #    Для этого использовать сигналы (signals) в Admin или переопределение метода save модели (аналог
        #    `upload_to` в обычных FileField).
        # 2. Внутри `FilerFileField` есть хеш SHA-1 (instance.doc.sha1) и размер файла в байтах (instance.doc.size).
        #    Они доступны в момент загрузки (сразу после, еще до записи на диск и БД. Через его проверку
        #    нужно предотвратить повторную запись файла-источника.
        verbose_name='Файл-источник',
        help_text='Файл-источник, например, Excel-файл от продавца или издателя. Если данные в источнике'
                  ' представлены на странице в интернете, можно не указывать файл, а указать URL в поле ниже.',
    )
    s_source_url = models.TextField(
        max_length=255, blank=True, default='',
        verbose_name='URL источника',
        help_text='URL страницы с данными, например, HTML-страница с каталогом товаров. Если данные в источнике'
                  ' представлены в виде файла, можно не указывать URL, а загрузить файл в поле выше.',
    )
    j_source_metadata = models.JSONField(
        default=dict, blank=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные об источнике (внутреннем устройстве: вкладках и стоkбцах Excel-файла,'
                  ' структуре HTML-страницы и т.п.) в виде JSON-словаря',
    )
    t_source_created = models.DateTimeField(auto_now_add=True, editable=False, verbose_name="Дата создания",)
    t_source_updated = models.DateTimeField(auto_now=True, editable=False, verbose_name="Дата обновления",
    )

    def __str__(self):
        return f"source {self.id:0>3}: {self.s_source_name}"

    class Meta:
        verbose_name = 'Источник данных'
        verbose_name_plural = 'Источники данных'
        ordering = ('-t_source_data', '-t_source_created')
        # constraints = [
        #     # Уникальное ограничение: один продавец может иметь несколько источников,
        #     # но комбинация (продавец + тип источника) должна быть уникальна
        #     models.UniqueConstraint(fields=['k_source_to_seller', 'l_source_type'],
        #                            name='idx_source_unique_by_seller_type'),
        # ]



# ============================================================================
# ИСТОРИЯ ИЗМЕНЕНИЙ ОФФЕРОВ
# ============================================================================
class TbOfferHistory(models.Model):
    """
    История изменений оффера (снапшот цены, количества, наличия).
    Создаётся автоматически при каждом сохранении оффера, если цена или количество изменились.
    
    АВТОМАТИЧЕСКОЕ СОЗДАНИЕ:
    - При создании нового оффера: создаёт первую запись с текущей ценой/количеством
    - При обновлении оффера: сравнивает последнюю запись истории с текущими значениями
    - Новая запись создаётся только если произошли изменения в цене ИЛИ количестве
    
    РЕДАКТИРОВАНИЕ ИСТОРИЧЕСКИХ ДАННЫХ:
    - Поле t_history_created можно редактировать (editable=True)
    - Используется для импорта исторических данных из Excel-файлов и других источников
    - Позволяет восстановить временную линию цены/наличия для аналитики
    
    МЕТОДЫ:
    • save(): вызывается автоматически из TbOffer.save() с параметрами цены/количества
    """
    k_history_to_offer = models.ForeignKey(
        TbOffer,
        on_delete=models.CASCADE,
        related_name='offer_to_history',  # ← offer.offer_to_history.all()
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Оффер',
    )
    f_history_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=0.00,
        verbose_name='Старая цена',
    )
    i_history_quantity = models.IntegerField(
        # Устанавливая количество в ноль, можно указать, что предложение более не доступно. Если оффер вернется,
        # то через новую запись в TbOfferHistory можно будет отследить, что он был в наличии, пропал, а потом
        # снова появился (со старой или новой ценой).
        default=0,
        verbose_name='Старое количество',
    )
    j_history_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Метаданные',
        help_text='Метаданные, указывающие координаты данных внутри источника (например, внутри Excel-файла:'
                  ' название вкладки, номер строки, номер столбца с ценой и количеством,'
                  ' или URL + CSS-селектор для HTML-страницы и т.п.',
    )
    t_history_created = models.DateTimeField(
       default=timezone.now,
       db_index=True,
       verbose_name="Дата создания",
       help_text="Дата создания записи истории. Автоматически устанавливается на текущее время при создании, "
                 "но может быть отредактирована для загрузки исторических данных из Excel-файлов.",
    )
    # Нам не нужен `t_history_updated` потому что это "снимок состояния" и его не нужно менять
    # после создания. И если вдруг понадобится, то правильнее будет добавить новую запись.

    def __str__(self):
        return f"history #{self.id} for offer {self.k_history_to_offer_id}"

    class Meta:
        verbose_name = 'История оффера'
        verbose_name_plural = 'Истории офферов'
        ordering = ('-t_history_created',)
        indexes = [
            # Составной индекс: найти историю оффера, отсортированную по времени (для хронологии изменений цены)
            models.Index(fields=['k_history_to_offer', '-t_history_created'], name='idx_history_by_offer_date'),
        ]
