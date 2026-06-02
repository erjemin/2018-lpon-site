from django.db import models
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

    # Порядок вывода
    i_img_sort = models.IntegerField(
        default=0,
        db_index=True,
        verbose_name='Cортировка',
        help_text='Порядок отображения изображений. Чем меньше число, тем выше в списке. Можно использовать'
                  ' для указания обложки (0), задника (1) и т.д.',
    )

    # Доверие данным (для парсеров и API)
    f_img_confidence_score = models.FloatField(
        null=True,
        blank=True,
        default=None,
        verbose_name='Уверенность (для автоматических данных)',
        help_text='0.0 - 1.0, насколько уверены, что это правильное изображение',
    )
    # Авторские права
    s_img_copyright = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Авторские права / Лицензия',
        help_text='Например: "© 2024 User" или "CC-BY"',
    )

    # Timestamps
    t_img_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления',
    )
    t_img_updated = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления',
    )

    class Meta:
        verbose_name = 'Изображение'
        verbose_name_plural = 'Изображения'
        ordering = ('i_img_sort', 't_img_created')


# ============================================================================
# ИСПОЛНИТЕЛИ
# ============================================================================
class TbArtist(models.Model):
    """Исполнитель или музыкальная группа."""

    s_artist = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name='Исполнитель',
        help_text="Исполнитель или группа.",
    )
    s_artist_html = models.TextField(
        blank=True,
        null=True,
        default='',
        verbose_name='Исполнитель (типографированно в HTML)',
        help_text='С сохранением типографирования и спецсимволов (всякие "метки" и иконки, типа "Иноагент",'
                  ' тоже можно заверстать сюда.',
    )
    k_artist_to_image = models.OneToOneField(
        TbImage,
        on_delete=models.SET_NULL,
        related_name='image_to_artist',
        blank=True,
        null=True,
        verbose_name='Изображение для исполнителя',
        help_text='Изображение исполнителя, например, логотип группы или фотография. Если указано, будет'
                  ' отображаться рядом с именем исполнителя.',
    )
    s_artist_article_html = models.TextField(
        blank=True,
        null=True,
        default='',
        verbose_name='Статья',
        help_text='Статья об исполнителе (типографированно в HTML)',
    )
    s_slug = models.SlugField(
        max_length=64,
        verbose_name='Слаг',
    )
    j_artist_in_source = models.JSONField(
        default=list,
        blank=True,
        null=True,
        verbose_name='Варианты написания в источниках',
        help_text='Список вариантов: ["The Beatles", "Beatles", "Beatles, The"]',
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


class TbItem(models.Model):
    """
    Товар в каталоге: релиз (альбом, сингл, компиляция), носитель (кассета для записи),
    аксессуар (щётка для виниловых пластинок) и т.д.
    Может быть представлен в виде одного или нескольких предложений от разных продавцов.
    """

    # Исполнители (ManyToMany для поддержки коллабораций)
    # Например: "David Bowie & Queen", "Elton John & Tim Rice"
    k_item_to_artist = models.ManyToManyField(
        TbArtist,
        blank=True,
        related_name='artist_to_item',  # artist.products.all() — найти все релизы артиста
        verbose_name='Исполнители',
        help_text="Один или несколько для коллабораций",
    )
    s_item_title = models.CharField(
        max_length=255, blank=False, null=False, default='',
        # db_index=True,
        verbose_name='Название товара (релиза)',
        help_text='Название товара (релиза), как указано на обложке. Например: <tt>Abbey Road</tt>'
                  ' или <tt>TDK, CDing I, 90</tt>.',
    )
    s_item_title_html = models.TextField(
        blank=True,
        null=True,
        default='',
        verbose_name='Название (типографированно)',
        help_text='С HTML-тегами для типографирования',
    )
    s_item_to_image = models.OneToOneField(
        TbImage,
        on_delete=models.SET_NULL,
        related_name='image_to_item',
        blank=True,
        null=True,
        verbose_name='Изображение',
        help_text='Изображение товара из каталога, например, обложка альбома. Если указано, будет отображаться'
                  ' рядом с названием товара.',
    )
    s_item_article_html = models.TextField(
        blank=True,
        null=True,
        default='',
        verbose_name='Статья',
        help_text='Статья о релизе, например, описание из Википедии или Discogs (а также список композиций,'
                  ' исполнители и т.п.). Для товара это может быть техническое описание и характеристики.'
                  ' Текст сверстан в HTML с сохранением типографирования и спецсимволов.',
    )
    s_item_slug = models.SlugField(
        blank=True,
        null=True,
        default='',
        verbose_name='Слаг',
        help_text='Слаг для товара, формируемый на основе названия товара (релиза)',
    )
    # Год выпуска (важно для коллекционеров)
    s_item_date = models.CharField(
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
        return f"Item {self.id:0>4}: {self.s_item_title}"

    class Meta:
        verbose_name = 'Товар в каталоге (релиз, носитель, аксессуар)'
        verbose_name_plural = 'Товары в каталоге'
        ordering = ('s_item_title',)


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
        null=False,
        default='',
        verbose_name='Название лейбла',
        help_text='Например: "Sony Records" или "Мелодия"',
    )
    s_label_article_html = models.TextField(
        blank=True,
        null=True,
        default='',
        verbose_name='Статья',
        help_text='Статья о лейбле (типографированно в HTML)',
    )
    s_label_slug = models.SlugField(
        max_length=64,
        blank=False,
        null=False,
        default='',
        verbose_name='Слаг',
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
    t_tabel_updated = models.DateTimeField(
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
        max_length=32, blank=False, null=False, default='',
        verbose_name='Название продавца',
        help_text='Название продавца или магазина, например: <tt>Клюква Рекодс</tt>',
    )
    s_seller_article_html = models.TextField(
        blank=True,
        null=True,
        default='',
        verbose_name='Статья',
        help_text='Статья о продавце (типографированно в HTML)',
    )
    s_seller_slug = models.SlugField(
        max_length=32, blank=False, null=False, default='',
        verbose_name='Слаг',
        help_text='Слаг для продавца, формируемый на основе названия продавца',
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
# ПРЕДЛОЖЕНИЯ / ОФФЕРЫ
# ============================================================================
class TbOffer(models.Model):
    """
    Конкретное предложение от продавца.
    Один и тот же релиз может быть несколько раз в системе от разных продавцов.
    """

    class Format(models.TextChoices):
        LP = 'lp', 'vinyl'
        CD = 'cd', 'CD'
        BD = 'bd', 'Blu-ray'
        CR = 'cr', 'Кассета с записью (фирменная)'
        CS = 'cs', 'Кассета под запись (новая или б/у)'
        MD = 'md', 'MiniDisc'
        BX = 'bx', 'Box Set'
        HI = 'hi', 'Hi-Fi (аппаратура)'
        AC = 'ac', 'Accessory (Аксессуар)'
        OTHER = '++', 'Other'

    class Condition(models.TextChoices):
        S = 's', 'Still Sealed (новое, запечатано)'
        M = 'm', 'Mint (новое, распакованное)'
        NM = 'nm', 'Near Mint (почти новое)'
        VG = 'vg', 'Very Good (очень хорошее)'
        G = 'g', 'Good (хорошее)'
        F = 'f', 'Fair (удовлетворительное)'
        P = 'p', 'Poor (плохое)'
        OTHER = '++', 'Other'

    # Связи
    k_offer_to_item = models.ForeignKey(
        TbItem,
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name='item_to_offer',  # ← product.product_offers.all()
        verbose_name='Релиз (товар)',
    )

    k_offer_to_label = models.ForeignKey(
        TbLabel,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
        related_name='label_to_offer',  # ← label.label_offers.all()
        verbose_name='Лейбл',
        help_text='Лейбл, на котором был выпущен релиз, если он известен. Например: <tt>Atlantic</tt> или <tt>Мелодия</tt>',
    )

    k_offer_to_source = models.ForeignKey(
        to='TbSource',
        null=True,
        default=None,
        on_delete=models.CASCADE,  # ← если удалён источник, удалены офферы
        related_name='source_to_offer',
        verbose_name='Источник данных',
        help_text='Обязательно - каждый оффер должен иметь источник. Через источник получаем данные '
                  'продавца: offer.k_offer_to_source.k_source_to_seller',
    )

    # Изображения товара (одна картинка может быть у многих офферов, а офер иметь много картинок)
    # M2M связь для удобства в админке (filter_horizontal)
    # Порядок картинок определяется полем i_img_sort в TbImage
    k_offer_to_image = models.ManyToManyField(
        TbImage,
        blank=True,
        related_name='image_to_offer',
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

    l_offer_primary_media = models.CharField(
        max_length=2,
        choices=Format.choices,
        default=Format.LP,
        verbose_name='Формат',
        help_text='Основной формат носителя (пластинка, CD, кассета и т.п.)'
    )

    d_offer_date_release = models.DateField(
        blank=True,
        null=True,
        default=None,
        verbose_name='Дата релиза',
        help_text='Дата релиза, если она известна (например, дата выпуска переиздания)',
    )

    i_offer_discogs_id = models.IntegerField(
        blank=True,default=0,
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
        blank=True,
        default=0.00,
        verbose_name='Цена',
        help_text='Цена в валюте источника. Валюта определяется в TbSource: offer.k_offer_to_source.l_currency',
    )

    i_offer_quantity = models.IntegerField(
        # Устанавливая количество в ноль, можно указать, что предложение в настоящее время не доступно.
        blank=True,
        default=0,
        db_index=True,
        verbose_name='Количество в наличии',
    )

    i_offer_discount_to_daily_sale = models.IntegerField(
        blank=True,
        default=0,
        db_index=True,
        verbose_name='Скидка',
        help_text='Процент возможной скидки, если участвует в "ежедневной распродаже" или акции. Если указано'
                  ' <tt>0</tt> то данное предложение не может участвовать в распродажах, спецпредложениях и акциях',
    )
    s_offer_comment_html = models.TextField(
        blank=True,
        default='',
        verbose_name='Доп.инфо',
        help_text='Дополнительная информация или комментарий к предложению от продавца с сохранением'
                  ' типографирования и спецсимволов.',
    )
    j_offer_metadata = models.JSONField(
        # Метаданные оффера (сырые данные из источника, координаты в Excel и т.д.)
        default=dict, null=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные о предложении в виде JSON-словаря.',
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

    class Meta:
        verbose_name = 'Оффер (предложение)'
        verbose_name_plural = 'Офферы (предложения)'
        ordering = ('-t_offer_updated', '-t_offer_created')


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
        related_name='offer_to_history',  # ← offer.history_to_offer.all()
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


#
#
# ┌────────────────────┐
# │ ProductEnrichment  │
# ├────────────────────┤
# │ id                 │
# │ product_id         │ FK
# │ source             │ ← discogs/api/scraper
# │ confidence_score   │
# │ data_json          │
# │ fetched_at         │
# └────────────────────┘
#
#
