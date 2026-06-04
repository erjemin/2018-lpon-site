from django.db import models
from django.db.models import F
from django.utils.text import slugify
from filer.fields.image import FilerImageField
from filer.fields.file import FilerFileField
import datetime

# ============================================================================
# ИЗОБРАЖЕНИЯ
# ============================================================================
class TbImage(models.Model):
    """
    Изображение, связанное с релизом, оффером, исполнителем и т.д.
    """
    # Источник изображения
    class ImageSource(models.TextChoices):
        PARSER_UPLOAD = 'parser', 'Загружено парсером (из Discogs, Meshok или другого сайта)'
        MANUAL_UPLOAD = 'manual', 'Ручная загрузка пользователем'
        VENDOR = 'vendor', 'От продавца'
        OTHER = 'other', 'Другое'

    # Тип изображения (реальное или абстрактное)
    class ImageReality(models.TextChoices):
        REAL_PHOTO = 'real', 'Реальная фотография товара'
        ABSTRACT = 'abstract', 'Абстрактное (из внешнего источника)'

    image = FilerImageField(
        # Файл через django_filer
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Файл изображения',
        help_text='Файл изображения, загруженный через django_filer.',
    )
    l_img_source = models.CharField(
        max_length=10,
        choices=ImageSource.choices,
        default=ImageSource.MANUAL_UPLOAD,
        verbose_name='Источник',
        help_text='Как был получен этот снимок: загружен вручную, получен парсером из внешнего источника (например,'
                  ' Discogs), предоставлен продавцом и т.д.',
    )
    l_img_reality = models.CharField(
        max_length=10,
        choices=ImageReality.choices,
        default=ImageReality.ABSTRACT,
        verbose_name='Тип снимка',
        help_text='Реальная фотография товара или картинка из внешнего источника?',
    )
    s_img_src_url = models.URLField(
        blank=True,
        null=True,
        verbose_name='URL источника',
        help_text='Если изображение взято из внешнего источника (например, Discogs)',
    )
    i_img_sort = models.IntegerField(
        # Порядок (сортировка) вывода
        default=0,
        db_index=True,
        verbose_name='Cортировка',
        help_text='Порядок отображения изображений. Чем меньше число, тем выше в списке. Можно использовать'
                  ' для указания обложки (0), задника (1) и т.д.',
    )
    f_img_confidence_score = models.FloatField(
        # Доверие данным (для парсеров и API)
        null=True,
        blank=True,
        default=None,
        verbose_name='Уверенность (для автоматических данных)',
        help_text='0.0 - 1.0, насколько уверены, что это правильное изображение',
    )
    s_img_copyright = models.CharField(
        # Авторские права и лицензия
        max_length=255,
        blank=True,
        default='',
        verbose_name='Авторские права / Лицензия',
        help_text='Например: "© 2024 User" или "CC-BY"',
    )
    t_img_created = models.DateTimeField(
        # Timestamps
        auto_now_add=True,
        verbose_name='Дата добавления',
    )
    t_img_updated = models.DateTimeField(
        # Timestamps
        auto_now=True,
        verbose_name='Дата обновления',
    )

    class Meta:
        verbose_name = 'Изображение'
        verbose_name_plural = 'Изображения'
        ordering = ('-t_img_created', 'i_img_sort',)


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
    s_style_name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name='Стиль (канонический)',
        help_text='Основное название стиля. Например: "Rock", "Jazz", "Classical"',
    )
    s_style_slug = models.SlugField(
        max_length=50,
        unique=True,
        db_index=True,  # Индекс для быстрого поиска по слагу (но НЕ primary_key!)
        editable=False,  # Не дать админу редактировать вручную (автогенерируется)
        verbose_name='Слаг (уникальный идентификатор)',
        help_text='Автоматически генерируется из названия. Используется в URL и API.',
    )
    j_style_synonyms = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Синонимы из источников',
        help_text='Список вариантов названия из Discogs, MusicBrainz и т.д. для матчинга.'
                  ' Пример: ["rock", "Rock Music", "Rock & Roll", "Hard Rock"]',
    )
    t_style_created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    t_style_updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def save(self, *args, **kwargs):
        """
        Автоматически генерируем slug из названия стиля.
        Вызывается при каждом сохранении записи (создание или обновление).
        """
        # Если slug не установлен (новая запись) — генерируем его из названия
        if not self.s_style_slug:
            # Генерируем базовый slug (Rock → rock, Rock Music → rock-music)
            base_slug = slugify(self.s_style_name, allow_unicode=True)

            # Проверяем на уникальность и добавляем счетчик если нужно
            # Это гарантирует, что slug будет уникален даже для похожих названий
            slug = base_slug
            counter = 1
            while TbMusicStyle.objects.filter(s_style_slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.s_style_slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.s_style_name

    class Meta:
        verbose_name = 'Музыкальный стиль'
        verbose_name_plural = 'Музыкальные стили'
        ordering = ('s_style_name',)


# ============================================================================
# СТАТЬИ (любая текстовая информация о релизе, исполнителе, продавце и т.д...
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
        ITEM = 'item', 'Item: Альбом, релиз или товар (кассета, hifi, аксессуар)'
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
    k_article_to_image = models.ForeignKey(
        TbImage,
        on_delete=models.SET_NULL,
        related_name='image_to_article',
        blank=True,
        null=True,
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Изображение для статьи',
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
    k_article_to_styles = models.ManyToManyField(
        TbMusicStyle,
        blank=True,
        related_name='style_to_article',
        db_index=True,
        verbose_name='Музыкальные стили',
        help_text='Стили этой статьи/артиста/релиза (Rock, Jazz, Classical, ...)',
    )
    i_article_views = models.IntegerField(
        # Счетчик просмотров (включая просмотры артиста, итема/релиза/товара, лейбла и продавца)
        default=0,
        db_index=True,  # для сортировки "самые просматриваемые"
        verbose_name='Число просмотров',
    )
    i_article_favorites = models.IntegerField(
        # Счетчик добавлений в избранное (включая избранное артиста, итема/релиза/товара, лейбла и продавца)
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
    t_article_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    t_article_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
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
# ИСПОЛНИТЕЛИ
# ============================================================================
class TbArtist(models.Model):
    """Исполнитель или музыкальная группа."""
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
                  ' через статью может быть получена картинка, seo атрибуты, слаг (обязательно) и т.п.)<br />'
                  '<b>ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ</b> т.к. через статью получаем слаг для URL артиста.'
    )
    j_artist_metadata = models.JSONField(
        default=list,
        blank=True,
        null=True,
        verbose_name='Метаданные JSON',
        help_text='Включая варианты написания в источниках Список вариантов: ["The Beatles", "Beatles",'
                  ' "Beatles, The"]',
    )
    t_artist_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    t_artist_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    def __str__(self):
        return f"artist {self.id:0>4}: {self.s_artist}"

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
    k_item_to_article = models.OneToOneField(
        TbArticle,
        on_delete=models.SET_NULL,
        related_name='article_to_item',
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        default=None,
        null=True,
        blank=True,     # <-- Интерфейсное удобство. Связь будет сделана автоматически, и статья создана автоматически.
        verbose_name='Связанная статья',
        help_text='Связанная статья об альбоме/релизе/товаре (Типографированные заголовок, тизер и текст статьи.'
                  ' Так же через статью может быть получена картинка, seo атрибуты, слаг (обязательно) и т.п.)<br />'
                  '<b>ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ</b> т.к. через статью получаем слаг для URL альбома/релиза/товара.'
    )
    s_item_date = models.CharField(
        # Год выпуска (важно для коллекционеров). Так же в будущем можно использовать для "ЮБИЛЕЙНОГО ПРЕДЛОЖЕНИЯ"
        # и фан-календаря
        max_length=10,
        blank=True,
        null=True,
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
    t_item_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    t_item_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    def __str__(self):
        return f"Item {self.id:0>4}: {self.s_item}"

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
    s_label = models.CharField(
        max_length=128,
        blank=False,
        unique=True,
        verbose_name='Лейбл',
        help_text='Техническое название лейбла. Например: "Sony Records" или "Мелодия"',
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
                  ' Так же через статью может быть получена картинка, seo атрибуты, слаг (обязательно) и т.п.)<br />'
                  '<b>ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ</b> т.к. через статью получаем слаг для URL лейбла.'
    )
    j_label_metadata = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name='Метаданные',
        help_text='JSON: страна лейбла, официальный сайт и т.д.',
    )
    t_label_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    t_label_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    def __str__(self):
        return f"label: {self.id:0>5}: {self.s_label}"

    class Meta:
        verbose_name = 'Лейбл'
        verbose_name_plural = 'Лейблы'
        ordering = ('s_label',)


# ============================================================================
# ПРОДАВЦЫ / МАГАЗИНЫ
# ============================================================================

class TbSeller(models.Model):
    """Продавец или магазин, который продаёт товары."""
    class SellerType(models.TextChoices):
        SELLER = 'seller', 'Продавец'
        LABEL = 'label', 'Лейбл (издатель)'
        DIY = 'diy', 'Самиздат группы'
        CROWD = 'crowdfunding', 'Краудфандинг'
        OTHER = '++', 'Другое'

    s_seller = models.CharField(
        max_length=128,
        blank=False,
        unique=True,
        verbose_name='Название продавца',
        help_text='Техническое название продавца или магазина. Например: <tt>Клюква Рекодс</tt>. Может совпадать'
                  ' с названием продавца, если лейбл сам реализует свои издания через сайт.',
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
                  ' Так же через статью может быть получена картинка, seo атрибуты, слаг (обязательно) и т.п.)<br />'
                  '<b>ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ</b> т.к. через статью получаем слаг для URL продавца.'
    )
    l_seller_type = models.CharField(
        max_length=9,
        default=SellerType.SELLER,
        choices=SellerType.choices,
        verbose_name='Тип продавца',
    )
    j_seller_metadata = models.JSONField(
        default=dict, blank=True, null=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные о продавце в виде JSON-словаря. Телефон, email, адрес, ссылка на сайт и т.д.',
    )
    t_seller_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    t_seller_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    def __str__(self):
        return f"seller: {self.id:0>2}: {self.s_seller}"

    class Meta:
        verbose_name = 'Продавец'
        verbose_name_plural = 'Продавцы'
        ordering = ('s_seller',)


# ============================================================================
# ФОРМАТЫ НОСИТЕЛЕЙ
# ============================================================================
class TbFormat(models.Model):
    """
    Формат носителя (LP, CD, Cassette и т.д.).

    s_format_slug используется в качестве первичного ключа (вместо id).
    Это удобно для справочников и предотвращает "дыры" в ID при удалении.
    Slug автоматически генерируется из s_format в методе save().
    """
    s_format = models.CharField(
        max_length=16,
        blank=False,
        unique=True,
        db_index=True,
        verbose_name='Формат носителя',
        help_text='Название формата носителя, например: "LP", "CD", "Blu-ray", "Compact Cassette", "MiniDisc",'
                  ' "Hi-Fi", "Accessory" и т.д.',
    )
    s_format_slug = models.SlugField(
        max_length=16,
        blank=False,
        unique=True,
        verbose_name='Слаг',
    )

    def __str__(self):
        return f"format: {self.s_format}"

    class Meta:
        verbose_name = 'Формат носителя'
        verbose_name_plural = 'Форматы носителей'
        ordering = ('s_format',)


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
        OTHER = '++', 'Other'

    s_offer = models.CharField(
        max_length=128,
        blank=False,
        db_index=True,
        verbose_name='Название оффера',
        help_text='Техническое название оффера для внутреннего использования, например:'
                  ' "Abbey Road (LP) AnTrop NM/NM (МЗГ)" или "TDK CDing I 60 (б/у) VG/VG (Janan, 198x синяя-градиент)"'
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
        # Изображения товара (одна картинка может быть у многих офферов, а оффер иметь много картинок)
        # M2M связь для удобства в админке (filter_horizontal)
        # Порядок картинок определяется полем i_img_sort в TbImage
        TbImage,
        blank=True,
        related_name='image_to_offer',
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Изображения',
        help_text='Картинки этого товара. Порядок определяется полем i_img_sort в ка��тинке.',
    )
    # Характеристики
    s_offer_catalog_num = models.TextField(
        blank=True,
        default='',
        verbose_name='Каталожный номер / Barcode',
        help_text='Например: "SD 16023" или "5099923452355"',
    )
    k_offer_to_format = models.ManyToManyField(
        TbFormat,
        blank=True,
        related_name='format_to_offer',  # ← format.format_to_offers.all()
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Форматы',
        help_text='Форматы носителей (пластинка, CD, кассета и т.п.). Можно выбрать несколько.',
    )
    d_offer_date_release = models.DateField(
        blank=True,
        null=True,
        default=None,
        verbose_name='Дата релиза',
        help_text='Дата релиза, если она известна (например, дата выпуска переиздания)',
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
    t_offer_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    t_offer_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

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
        constraints = [
            # Уникальное ограничение: предотвратить дубликаты (один товар + один источник + один формат)
            models.UniqueConstraint(fields=['k_offer_to_item', 'k_offer_to_source', 'l_offer_primary_media'],
                                   name='idx_offer_unique_item_source_format'),
        ]


# ============================================================================
# ИСТОЧНИКИ ДАННЫХ
# ============================================================================
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
        OTHER = '++', 'Другое'

    class Currency(models.TextChoices):
        RUB = 'rub', 'RUB: российский рубль'
        USD = 'usd', 'USD: американский доллар'
        EUR = 'eur', 'EUR: евро'
        TRY = 'try', 'TRY: турецкая лира'
        AMD = 'amd', 'AMD: армянский драм'
        JPY = 'jpy', 'JPY: японская иена'
        GBP = 'gbp', 'GBP: британский фунт'
        CNY = 'cny', 'CNY: китайский юань'
        BYN = 'byn', 'BYN: белорусский рубль'
        TON = 'ton', 'TON: криптовалюта TON'
        OTHER = '++', 'Other'

    k_source_to_seller = models.ForeignKey(
        TbSeller,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name='seller_to_source',
        db_index=True,  # Принудительно создаем индекс, т.к. SQLite их сам не создаст.
        verbose_name='Продавец',
    )

    l_source_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.RUB,
        verbose_name='Валюта источника',
        help_text='В какой валюте указаны цены в этом источнике. Все офферы из этого источника будут в этой валюте.',
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
    t_source_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата Создания записи в БД",
    )
    t_source_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата последнего обновления записи в БД",
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
        verbose_name="Дата создания",
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

