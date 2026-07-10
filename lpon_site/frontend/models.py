# LPON Store — Django E-Commerce Database Schema (SQLite optimized)
# 
# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                    ER-ДИАГРАММА СХЕМЫ БД (v1.0)                            ║
# ╚════════════════════════════════════════════════════════════════════════════╝
# 
# Легенда:
#   Ключи:
#     PK = Primary Key (первичный ключ)
#     FK = Foreign Key (внешний ключ)
#     M2M = Many-to-Many (ключ многие-ко-многим)
#   Связи:
#     1:1 = OneToOne связь
#     1:M = One-to-Many связь
#     M:M = Many-to-Many связь
#
#
#  ##════════════════════════════════════════════════════════════════════════════##
#                         МЕДИА И СПРАВОЧНИКИ
#  ##════════════════════════════════════════════════════════════════════════════##
#
# ┌─────────────────────┐
# │   TbImage           │  Базовые изображения (обложки, фото и т.д.)
# ├─────────────────────┼─────────────────────────────────────────────────────
# │ PK: id              │  AutoField
# │ image               │  FilerImageField
# │ l_img_source        │  Источник (parser, manual, vendor, other)
# │ l_img_reality       │  Тип (real, abstract)
# │ i_img_sort          │  Порядок отображения
# │ f_img_confidence_   │  Доверие данным (0-1)
# │ t_img_created       │  Timestamp
# │ t_img_updated       │  Timestamp
# │                     │  ⬆ Индекс на: id (+), i_img_sort
# └─────────────────────┘
#         △
#         │ M:M TbOffer.k_offer_to_image
#         │ [промежуточная таблица: offer_id, image_id]
#         │
#         ├────┬───────────────────────────────────────────────────────────────────┐
#         │    │
#         │    ▼
#         │  ┌──────────────────────┐
#         │  │ TbArticle            │  Текстовый контент (статьи, SEO, теги)
#         │  ├──────────────────────┼──────────────────────────────────────────────────
#         │  │ PK: id               │  AutoField
#         │  │ s_article_title      │  Технический заголовок
#         │  │ l_article_type       │  Тип (artist, item, offer, seller, blog...)
#         │  │ b_article_published  │  Опубликовано (bool)
#         │  │ s_article_title_html │  HTML-заголовок
#         │  │ k_article_to_image   │  FK → TbImage (обложка статьи)
#         │  │ k_article_to_styles  │  M2M → TbMusicStyle (теги стилей)
#         │  │ i_article_views      │  Счетчик просмотров
#         │  │ i_article_favorites  │  Счетчик в избранном
#         │  │ slug                 │  URL-идентификатор (уникальный)
#         │  │ seo_title,           │  SEO метаданные
#         │  │ seo_description      │
#         │  │ t_article_created    │  Timestamps
#         │  │ t_article_updated    │  Timestamps
#         │  │                      │  ⬆ Индексы: id (+), l_article_type, b_article_published, slug,
#         │  │                      │   k_article_to_image, (type, published, created)
#         │  └──────────────────────┘
#         │         △
#         │         │ 1:1 (OneToOne обратные связи)
#         │         │
#         │     ┌───┴─────────┬────────────┬──────────────┐
#         │     │             │            │              │
#         │     ▼             ▼            ▼              ▼
#         │  ┌─────────┐    ┌───────┐    ┌─────────┐    ┌──────────┐
#         │  │TbArtist │    │TbItem │    │TbLabel  │    │TbSeller  │
#         │  ├─────────┤    ├───────┤    ├─────────┤    ├──────────┤
#         │  │PK: id   │    │PK: id │    │ PK: id  │    │ PK: id   │
#         │  │s_artist │    │s_item │    │ s_label │    │ s_seller │
#         │  └─────────┘    └───────┘    └─────────┘    └──────────┘
#         │      ▲
#         │      │ M:M TbItem.k_item_to_artist
#         │      │ (для поддержки коллабораций)
#         │      │
#         └──────┘
#
#
# ┌──────────────────┐
# │ TbMusicStyle     │  Музыкальные стили (теги для категоризации - собственные статьи)
# ├──────────────────┼────────────────────────────────────────────────────────
# │ PK: id           │  SmallAutoField
# │ s_style_name     │  Название (Rock, Jazz, Classical...)
# │ k_style_to_article│ 1:1 OneToOne FK → TbArticle (для SEO, слага, контента)
# │ j_style_metadata │  JSON синонимы из Discogs для матчинга при импорте
# │ t_style_created  │  Timestamp
# │ t_style_updated  │  Timestamp
# │                  │  ⬆ Индексы: id (+), related_name→article_to_style
# └──────────────────┘
#
#
#
#
#  ##════════════════════════════════════════════════════════════════════════════##
#                       ПРЕДЛОЖЕНИЯ И ЦЕНЫ
#  ##════════════════════════════════════════════════════════════════════════════##
#
# ┌──────────────────────┐
# │  TbSeller            │  Продавцы / магазины
# ├──────────────────────┼──────────────────────────────────────────────────────
# │ PK: id               │  AutoField
# │ s_seller             │  Название (уникальный)
# │ l_seller_currency    │  (rub, usd, eur, ...)
# │ l_seller_type        │  Тип (seller, label, diy, crowdfunding, other)
# │ k_seller_to_article  │  1:1 FK → TbArticle (content, SEO, slug)
# │ j_seller_metadata    │  JSON с дополнительными данными (ссылки, контакты, соцсети)
# │ t_seller_created     │  Timestamp
# │ t_seller_updated     │  Timestamp
# │                      │  ⬆ Индекс: id
# └──────────────────┬───┘
#                    │
#                    │ 1:M TbSource.k_source_to_seller
#                    ▼
#             ┌──────────────────────┐
#             │  TbSource            │  Источники данных (Excel, URL, CSV...)
#             ├──────────────────────┼───────────────────────────────────────
#             │ PK: id               │  AutoField
#             │ k_source_to_seller   │  FK → TbSeller [indexed]
#             │ l_source_type        │  (excel, csv, url, other)
#             │ s_source_name        │  Название источника
#             │ source_file          │  FilerFileField
#             │ s_source_url         │  URL источника
#             │ t_source_data        │  Дата данных
#             │ t_source_created     │  Timestamp
#             │ t_source_updated     │  Timestamp
#             │ ⬆ Индекс: k_source_to_seller
#             └──────────────────┬───┘
#                                │
#                                │ 1:M TbOffer.k_offer_to_source
#                                ▼
#                ┌────────────────────────────────┐
#                │  TbOffer                       │  Конкретное предложение товара
#                ├────────────────────────────────┼───────────────────────────────
#                │ PK: id                         │  AutoField
#                │ s_offer                        │  Название (indexed)
#                │ l_offer_to_format              │  Формат (CD, Vinyl, Digital...)
#                │ k_offer_to_item                │  FK → TbItem [indexed]
#                │ k_offer_to_label               │  FK → TbLabel [indexed]
#                │ k_offer_to_source              │  FK → TbSource [indexed]
#                │ k_offer_to_article             │  FK → TbArticle (опционально)
#                │ k_offer_to_image               │  M2M → TbImage (несколько фото)
#                │ b_offer_is_preorder            │  Предзаказ (bool, indexed)
#                │ d_offer_date_release           │  Дата релиза/ожидаемого выхода по предзаказу [indexed]
#                │ l_offer_condition_media        │  Состояние (s, m, nm, vg, g, f, p)
#                │ l_offer_condition_sleeve       │  Состояние (s, m, nm, vg, g, f, p)
#                │ f_offer_price                  │  Цена [indexed для сортировки]
#                │ i_offer_quantity               │  Количество в наличии [indexed]
#                │ i_offer_discount_to_daily_sale │  % скидка [indexed для фильтров]
#                │ s_offer_skip32                 │  Хеш для корзины (unique)
#                │ i_offer_views                  │  Счетчик просмотров
#                │ i_offer_favorites              │  Счетчик в избранном
#                │ t_offer_created                │  Timestamp
#                │ t_offer_updated                │  Timestamp
#                │                                │  ⬆ Индексы: (item, price↓), (item, quantity), (source, discount), (is_preorder), (date_release)
#                │                                │  ⬆ Constraint UNIQUE: (item, source, format)
#                └────────────────────┬───────────┘
#                                     │
#                                     │ 1:M TbOfferHistory.k_history_to_offer
#                                     ▼
#                          ┌────────────────────┐
#                          │ TbOfferHistory     │  История изменений цены/кол-ва
#                          ├────────────────────┼──────────────────────────────
#                          │ PK: id             │  AutoField
#                          │ k_history_to_offer │  FK → TbOffer [indexed]
#                          │ f_history_price    │  Старая цена
#                          │ i_history_quantity │  Старое количество
#                          │ t_history_created  │  Timestamp [indexed]
#                          │                    │  ⬆ Индекс: (offer, created↓)
#                          └────────────────────┘
#
#
#  ##════════════════════════════════════════════════════════════════════════════##
#                       КАТАЛОГ ТОВАРОВ
#  ##════════════════════════════════════════════════════════════════════════════##
#
# ┌────────────────────┐
# │ TbLabel            │  Издатели / лейблы
# ├────────────────────┼────────────────────────────────────────────────────────
# │ PK: id             │  AutoField
# │ s_label            │  Название (Sony, Atlantic, Мелодия...)
# │ k_label_to_article │  1:1 FK → TbArticle (content, SEO)
# └────────────────────┘
#         △
#         │ 1:M TbOffer.k_offer_to_label
#         │
# ┌─────────────────────┐
# │ TbItem              │  Товары в каталоге (релизы, носители, аксессуары)
# ├─────────────────────┼────────────────────────────────────────────────────────
# │ PK: id              │  AutoField
# │ s_item              │  Название (Abbey Road (LP), TDK CDing I...)
# │ k_item_to_artist    │  M2M → TbArtist (для коллабораций)
# │ k_item_to_style     │  M2M → TbMusicStyle (жанры альбома)
# │ k_item_to_article   │  1:1 FK → TbArticle (content, SEO, slug)
# │ s_item_date         │  Дата релиза (строка, неполная/текстовая) [indexed]
# │ t_item_date         │  Базовая дата релиза товара/альбома [indexed]
# │ i_discogs_master_id │  ID мастер-релиза на Discogs
# │ t_item_created      │  Timestamp
# │ t_item_updated      │  Timestamp
# └─────────────────────┘
#         △
#         │ 1:M TbOffer.k_offer_to_item
#         │
#         ├──────────────────── M2M → TbArtist.k_item_to_artist
#         │                    [промежуточная таблица: item_id, artist_id]
#         │
#         └──────────────────── M2M → TbMusicStyle.k_item_to_style
#                              [промежуточная таблица: item_id, musicstyle_id]
# ┌─────────────────────┐
# │  TbArtist           │  Исполнители / группы
# ├─────────────────────┼─────────────────────────────────────────────────────
# │ PK: id              │  AutoField
# │ s_artist            │  Название (The Beatles, David Bowie...)
# │ k_artist_to_article │  1:1 FK → TbArticle (content, SEO, slug)
# │ t_artist_created    │  Timestamp
# │ t_artist_updated    │  Timestamp
# │                     │
# │                     │  ⬆ Индекс: id, k_artist_to_article
# └─────────────────────┘
#
#
# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                           ИТОГО ТАБЛИЦ: 10                                 ║
# ║  Справочники:  TbImage, TbArticle, TbMusicStyle (1:1→article)              ║
# ║  Сущности:     TbSeller, TbLabel, TbArtist, TbItem                         ║
# ║  Коммерческие: TbSource, TbOffer (format как CharField), TbOfferHistory    ║
# ║  M2M связи:    offer←→images                                               ║
# ║                item←→artists (для коллабораций)                            ║
# ║                item←→styles (жанры альбома)                                ║
# ║  OneToOne:     style→article, artist→article, item→article, label→article  ║
# ║                seller→article (все равно связаны через TbArticle)          ║
# ╚════════════════════════════════════════════════════════════════════════════╝
#
# ОПТИМИЗАЦИЯ ДЛЯ SQLite:
#   - db_index=True на все FK поля (SQLite не создает их автоматически)
#   - Составные индексы на часто используемые комбинации
#   - PRAGMA auto_vacuum=2 для невручного сокращения файла БД
#   - PRAGMA journal_mode=WAL для лучшей concurrency
#   - M2M использует числовые FK (INT) вместо строк
#   - Slug'и как UNIQUE indexed fields (не primary_key) для экономии места

from django.db import models
from django.db.models import F
from filer.fields.image import FilerImageField
from filer.fields.file import FilerFileField
from frontend.utils import make_slug, update_synonyms_in_metadata, create_or_get_related_article
from frontend.utils_validators import validate_and_raise_for_duplicates
import datetime
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# МЕТАДАННЫЕ ИЗОБРАЖЕНИЙ
# ============================================================================
class TbImageMetadata(models.Model):
    """
    Метаданные к изображениям из django_filer.

    OneToOne связь с filer.Image. Хранит дополнительные поля:
    - i_img_sort: порядок сортировки изображений
    - j_img_metadata: JSON с гибкими данными (источник, тип, достоверность и т.д.)

    Данные можно заполнять вручную через админку или программно из парсеров.
    При создании новой filer.Image автоматически создаётся TbImageMetadata
    с дефолтными значениями (через signal).
    """

    image = FilerImageField(
        # Связь OneToOne с filer.Image (через наследование)
        null=False,
        blank=False,
        on_delete=models.DO_NOTHING,
        related_name='metadata',  # Встречный доступ: filer_image.metadata
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
        # Гибкие дополнительные данные о изображении
        # Пример: {"source": "discogs", "reality": "abstract", "confidence": 0.95, ...}
        default=dict,
        blank=True,
        null=True,
        verbose_name='Метаданные',
        help_text='JSON с дополнительными данными: источник (парсер, админка), тип (реальное/абстрактное), '
                  'достоверность, URL источника и т.д. Гибкое хранилище, позволяет добавлять новые поля '
                  'без миграций БД.',
    )

    # Эти поля ПОКА остаются (удалим после миграции данных)
    # но НЕ используются в новой архитектуре
    l_img_source = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name='[DEPRECATED] Источник',
        help_text='[DEPRECATED] Использовать j_img_metadata вместо этого поля.',
    )
    l_img_reality = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name='[DEPRECATED] Тип снимка',
        help_text='[DEPRECATED] Использовать j_img_metadata вместо этого поля.',
    )
    s_img_src_url = models.URLField(
        blank=True,
        null=True,
        verbose_name='[DEPRECATED] URL',
        help_text='[DEPRECATED] Использовать j_img_metadata вместо этого поля.',
    )
    f_img_confidence_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name='[DEPRECATED] Достоверность',
        help_text='[DEPRECATED] Использовать j_img_metadata вместо этого поля.',
    )
    t_img_created = models.DateTimeField(auto_now_add=True, verbose_name='[DEPRECATED] Дата добавления')
    t_img_updated = models.DateTimeField(auto_now=True, verbose_name='[DEPRECATED] Дата обновления')

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
    Статья, связанная с релизом, исполнителем, продавцом и т.д.
    Может быть использована для хранения любой текстовой информации, например, описания релиза из Википедии или
    Discogs, биографии исполнителя, описания продавца и т.д. Сохранение типографирования и спецсимволов в HTML.
    """
    class ArticleType(models.TextChoices):
        ARTIST = 'artist', 'Artis: артист, группа или бренд'
        STYLE = 'style', 'Slyle: музыкальный стиль'
        ITEM = 'item', 'Item: Альбом, релиз или товар (кассета, hifi, аксессуар)'
        LABEL = 'label', 'Label: Лейбл, издатель или компания'
        OFFER = 'offer', 'Offer: конкретное предложение от продавца'
        SELLER = 'seller', 'Seller: продавец или магазин'
        BLOG = 'blog', 'Новость или блог'
        ACTION = 'action', 'Спецпредложение, акция, распродажа и т.д.'
        TO_MAIN = 'to_main', 'Текст/Блок для главной страницы'
        ADV = 'adv', 'Реклама или баннер'
        OTHER = '???', 'Другое'

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
        # Прямая ссылка на filer.Image (вместо TbImage)
        # Метаданные изображения (сортировка, источник, тип и т.д.) находятся в TbImageMetadata
        to='filer.Image',
        on_delete=models.SET_NULL,
        related_name='article_images',
        blank=True,
        null=True,
        db_index=True,
        verbose_name='Изображение для статьи',
        help_text='Обложка или иллюстрация статьи из файлового хранилища (django_filer).'
                  ' Метаданные: image.metadata.i_img_sort и image.metadata.j_img_metadata.</br>'
                  '<b>ВАЖНО</b>: Так как статья призывается к исполнителям, лейблам, продавцам, музыкальным стилям,'
                  ' её можно использовать как логотип-пкитограмму или баннер этих сущностей. В этом случае '
                  ' рекомендуется использовать изображение с прозрачным фоном (движок поддерживает SVG, WebP и PNG).'
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

        super().save(*args, **kwargs)

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
    Музыкальный стиль (канонический / опорный).

    Один главный стиль может иметь несколько синонимов (из Discogs).
    Пример:
    - Главный: "Rock"
    - Синонимы: ["rock", "Rock Music", "Rock & Roll", "Hard Rock", ...]

    Примечание:
    - Slug автоматически генерируется из s_style_name в методе save()
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
    """Исполнитель или музыкальная группа."""
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
    Товар в каталоге: релиз (альбом, сингл, компиляция), носитель (кассета для записи),
    аксессуар (щётка для виниловых пластинок) и т.д.
    Может быть представлен в виде одного или нескольких предложений от разных продавцов.
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
    Лейбл или издатель релиза.
    Примеры: для винила, CD, Blu-Ray это: Sony, Мелодия, Atlantic, EMI ...
             для кассет под запись это: TDK, AXIA, Maxell, JVC ...
             для hi-fi это: Sony, Pioneer, Technics, Marantz ...
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
    """Продавец или магазин, который продаёт товары."""
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
                  ' <tt>{"formats": {"lp": 2, "cd": 1},}</tt>',
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
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name='label_to_offer',  # ← label.label_to_offers.all()
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Лейбл',
        help_text='Лейбл, на котором был выпущен релиз, если он известен. Например: <tt>Atlantic</tt> или <tt>Мелодия</tt>',
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
    k_offer_to_image = models.ManyToManyField(
        # Изображения товара из django_filer (одна картинка может быть у многих офферов, 
        # а оффер иметь много картинок)
        # M2M связь для удобства в админке (filter_horizontal)
        # Порядок картинок определяется полем i_img_sort в TbImageMetadata
        to='filer.Image',
        blank=True,
        related_name='offer_images',
        db_index=True,
        verbose_name='Изображения',
        help_text='Картинки этого товара/предложения. Порядок определяется полем i_img_sort в TbImageMetadata. '
                  'Доступ к метаданным: image.metadata.i_img_sort и image.metadata.j_img_metadata',
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
        blank=False,
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
        verbose_name='Скидка',
        help_text='Процент возможной скидки, если участвует в "ежедневной распродаже" или акции. Если указано'
                  ' <tt>0</tt> то данное предложение не может участвовать в распродажах, спецпредложениях и акциях',
    )
    j_offer_metadata = models.JSONField(
        # Метаданные оффера (сырые данные из источника, координаты в Excel и т.д.)
        default=dict, null=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные о предложении в виде JSON-словаря.',
    )
    s_offer_skip32 = models.CharField(
        max_length=12,
        unique=True,
        verbose_name='Код товара',
        help_text='Уникальный код товара для идентификации в корзине и при заказе (чтобы не светить id).'
                  ' Например: "4gfFCJ". Формируется автоматически связкой Skip32 (хаотичное перемешивание) и'
                  ' Base62 (компактная упаковка) из id оффера в методе save().',
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
        return f"offer {self.id:0>4} for item {self.k_offer_to_item_id} from seller {seller}"

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


class TbSource(models.Model):
    """
        Источник данных, из которого был импортирован оффер.
        Например, это может быть Excel-файл от продавца или издателя, CSV-файл, URL страницы с данными
        (например, HTML-страница с каталогом товаров) и т.д.
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
    Создаётся при каждом импорте, если что-то изменилось.
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
        auto_now_add=True,
        db_index=True,
        editable=False,
        verbose_name="Дата создания",)
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
