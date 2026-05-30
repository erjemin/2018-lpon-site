from django.db import models
import datetime

# Create your models here.
class TbArtist(models.Model):
    s_artist = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name='Исполнитель',
        help_text="Исполнитель или группа.",
    )
    s_artist_html = models.TextField(
        blank=True, null=True, default='',
        verbose_name='Исполнитель (типографированно в HTML)',
        help_text='Исполнитель или группа, указанные на обложке релиза, с сохранением типографирования и спецсимволов в виде HTML-тегов.',
    )
    s_slug = models.SlugField(
        max_length=64,
    )
    j_artist_in_source = models.JSONField(
        default=list, blank=True, null=True,
        verbose_name='Исполнитель в источнике',
        help_text='Список вариантов написания исполнителя, встречающихся в источниках (в разных релизах/каталогах'
                  ' или у разных поставщиков). Например: <tt>["The Beatles", "Beatles", "Beatles, The"]</tt>.',
    )
    t_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата Создания записи в БД",
    )
    t_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата последнего обновления записи в БД",
    )

    def __unicode__(self):
        return f"product {self.id:0>4}: {self.s_artist}"

    def __str__(self):
        return self.__unicode__()

    class Meta:
        verbose_name = 'Исполнитель'
        verbose_name_plural = 'Исполнители'
        ordering = ('s_artist',)


class TbProduct(models.Model):
    # Абстрактный релиз / сущность / товар, который может быть представлен в виде одного или нескольких предложений
    # от разных продавцов.
    k_artists = models.ManyToManyField(
        TbArtist,
        blank=True,
        verbose_name='Исполнители',
        help_text="Выберите исполнителей или группы для этого релиза (можно не указывать)",
    )
    s_title = models.CharField(
        max_length=255, blank=False, null=False, default='',
        # db_index=True,
        verbose_name='Название товара (релиза)',
        help_text='Название товара (релиза), как указано на обложке. Например: <tt>Abbey Road (remastered)</tt>'
                  ' или <tt>TDK, CDing I, 90</tt>.',
    )
    s_title_html = models.TextField(
        blank=True, null=True, default='',
        verbose_name='Название товара (типографированно в HTML)',
        help_text='Название товара (релиза), как указано на обложке, с сохранением типографирования и спецсимволов'
                  ' в виде HTML-тегов.',
    )
    s_title_slug = models.SlugField(
        blank=True, null=True, default='',
        verbose_name='Слаг',
        help_text='Слаг для товара, формируемый на основе названия товара (релиза)',
    )
    t_title_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='Дата релиза',
        help_text='Дата релиза, если известна. Если известен только год, можно указать 1 января этого года.'
                  ' Например: <tt>1969-09-26</tt> или не указывать вовсе.',
    )
    i_discogs_master_id = models.IntegerField(
        blank=True, null=True, default=None,
        verbose_name='ID на мастер-релиз Discogs',
        help_text='Уникальный идентификатор мастер-релиза на Discogs, если он там есть. Например: <tt>306323</tt>',
    )
    j_product_metadata = models.JSONField(
        default=dict, blank=True, null=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные о релизе в виде JSON-словаря,',
    )
    t_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата Создания записи в БД",
    )
    t_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата последнего обновления записи в БД",
    )

    def __unicode__(self):
        return f"product {self.id:0>4}: {self.s_title}"

    def __str__(self):
        return self.__unicode__()

    class Meta:
        verbose_name = 'Релиз (товар)'
        verbose_name_plural = 'Релизы (товары)'
        ordering = ('s_title',)


class TbSeller(models.Model):
    # Продавец товара
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
    s_seller_slug = models.SlugField(
        max_length=32, blank=False, null=False, default='',
        verbose_name='Слаг',
        help_text='Слаг для продавца, формируемый на основе названия продавца',
    )
    l_seller_type = models.CharField(
        max_length=9, default=SellerType.SELLER, choices=SellerType.choices,
        verbose_name='Тип продавца',
    )
    j_seller_metadata = models.JSONField(
        default=dict, blank=True, null=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные о продавце в виде JSON-словаря',
    )
    
    def __unicode__(self):
        return f"vendor {self.id:0>3}: {self.s_vendor}"
    
    def __str__(self):
        return self.__unicode__()
    
    class Meta:
        verbose_name = 'Продавец'
        verbose_name_plural = 'Продавцы'
        ordering = ('s_seller',)
        
class TbLabel(models.Model):
    # Лейблы: производители (Улитка Рекородс, Мелодия, Sony... а так же производители TDK, AXIA, Maxwell и т.д.)
    s_label = models.CharField(
        max_length=32, blank=False, null=False, default='',
        verbose_name='Название лейбла',
        help_text='Название лейбла, например: <tt>Мелодия</tt> или <tt>TDK</tt>',
    )
    s_label_slug = models.SlugField(
        max_length=32, blank=False, null=False, default='',
        verbose_name='Слаг',
        help_text='Слаг для лейбла, формируемый на основе названия лейбла',
    )
    j_label_metadata = models.JSONField(
        default=dict, blank=True, null=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные о лейбле в виде JSON-словаря',
    )


#
class TbOffer(models.Model):
    # Конкретное предложение продавца
    class Format(models.TextChoices):
        LP = 'lp', 'vinyl'
        CD = 'cd', 'CD'
        BD = 'bd', 'Blu-ray'
        CS = 'cs', 'Cassette'
        MD = 'md', 'Minidisc'
        BX = 'bx', 'Box Set'
        HI = 'hi', 'Hi-Fi'
        AC = 'ac', 'Accessory'
        OTHER = '++', 'Other'

    class Condition(models.TextChoices):
        S = 's', 'Still Sealed (новое, запечатано)'
        M = 'm', 'Mint'
        NM = 'nm', 'Near Mint'
        VG = 'vg', 'Very Good'
        G = 'g', 'Good'
        F = 'f', 'Fair'
        P = 'p', 'Poor'
        OTHER = '++', 'Other'

    class Currency(models.TextChoices):
        RUB = 'rub', 'RUB: российский рубль'
        TRY = 'try', 'TRY: турецкая лира'
        AMD = 'amd', 'AMD: армянский драм'
        USD = 'usd', 'USD: американский доллар'
        EUR = 'eur', 'EUR: евро'
        JPY = 'jpy', 'JPY: японская иена'
        GBP = 'gbp', 'GBP: британский фунт'
        CNY = 'cny', 'CNY: китайский юань'
        BYN = 'byn', 'BYN: белорусский рубль'
        TON = 'ton', 'TON: криптовалюта TON'
        OTHER = '++', 'Other'

    s_catalog_num = models.TextField(
        blank=True, default='',
        verbose_name='Каталожный номер или barcode',
        help_text='Каталожный номер релиза, если он есть. Например: <tt>SD 16023</tt> для <i>ABBA — Super Trouper'
                  ' — 1980 — Atlantic (USA)</i>',
    )
    k_product = models.ForeignKey(
        TbProduct,
        blank=True, default=None,
        on_delete=models.SET_NULL, related_name='+',
        verbose_name='Релиз (товар)',
    )
    k_label = models.ForeignKey(
        TbLabel,
        null=True, default=None,
        on_delete=models.SET_NULL, related_name='+',
        verbose_name='Лейбл',
        help_text='Лейбл, на котором был выпущен релиз, если он известен. Например: <tt>Atlantic</tt> или <tt>Мелодия</tt>',
    )
    k_seller = models.ForeignKey(
        TbSeller,
        null=True, default=None,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Продавец',
    )
    l_primary_media = models.CharField(
        max_length=2,
        choices=Format.choices,
        default=Format.LP,
        verbose_name='Формат',
        help_text='Основной формат носителя (пластинка, CD, кассета и т.п.)'
    )
    i_discogs_id = models.IntegerField(
        blank=True,default=0,
        verbose_name='ID на релиз Discogs',
        help_text='Уникальный идентификатор релиза на Discogs, если он там есть. Например: <tt>306323</tt>',
    )
    l_condition_media = models.CharField(
        max_length=2,
        choices=Condition.choices,
        default=Condition.S,
        verbose_name="Состояние носителя",
        help_text='Состояние носителя (пластинки, CD и т.п.) по шкале от "Still Sealed" (запечатано) до "Poor" (плохое).',
    )
    l_condition_sleeve = models.CharField(
        max_length=2,
        choices=Condition.choices,
        default=Condition.S,
        verbose_name="Состояние обложки",
        help_text='Состояние обложки по шкале от "Still Sealed" (запечатано) до "Poor" (плохое).',
    )
    f_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True, default=0.00,
        verbose_name='Цена',
    )
    l_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.RUB,
        verbose_name="Валюта",
    )
    i_quantity = models.IntegerField(
        blank=True, default=0,
        verbose_name='Количество',
    )
    b_is_available = models.BooleanField(
        default=True,
        verbose_name='В наличии',
    )
    i_discount_to_daily_sale = models.IntegerField(
        blank=True, default=0,
        verbose_name='Скидка',
        help_text='Процент скидки, для ежедневной распродажи',
    )
    s_offer_comment = models.TextField(
        blank=True, default='',
        verbose_name='Доп.инфо',
        help_text='Дополнительная информация или комментарий к предложению от продавца, например:'
                  ' <tt>"Пластинка запаяна в целлофан, угол обложки замят."</tt>.',
    )
    j_offer_metadata = models.JSONField(
        default=dict, null=True,
        verbose_name='Дополнительные данные',
        help_text='Дополнительные данные о предложении в виде JSON-словаря.',
    )
    t_offer_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата Создания записи в БД",
    )
    t_offer_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата последнего обновления записи в БД",
    )

    class TbSource(models.Model):
        #  Источник данных (абстрактный), "место", откуда данные могут приходить многократно.

        class SoueceType(models.TextChoices):
            EXCEL = 'excel', 'Excel-файл от продавца или издателя'
            CSV = 'csv', 'CSV-файл от продавца или издателя'
            URL = 'url', 'URL страницы с данными (например, HTML-страница с каталогом товаров)'
            OTHER = '++', 'Другое'

        k_seller = models.ForeignKey(
            TbSeller,
            null=True, default=None,
            on_delete=models.SET_NULL,
            verbose_name='Продавец',
        )
        s_source_name = models.CharField(
            max_length=128, blank=True, default='',
            verbose_name='Название источника',
            help_text='Название источника данных (для удобства), например: <tt>Предзаказ на RSD-2025 от Полуэкта.</tt>',
        )
        l_source_type = models.CharField(
            max_length=5, default=SoueceType.EXCEL, choices=SoueceType.choices,
            verbose_name='Тип источника',
            help_text='Тип источника данных, например: <tt>Excel-файл от продавца или издателя</tt>, <tt>URL страницы'
                      ' с данными</tt> и т.д.',
        )
        t_source_data = models.DateField(
            blank=True, default=datetime.date.today,
            verbose_name='Дата данных',
            help_text='Дата, к которой относятся данные в источнике. Например, если это исторический Excel-файл.',
        )
        file_source = models.FileField(
            blank=True, default='', upload_to='sources/',
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
        s_source_file_hash = models.CharField(
            max_length=128, blank=True, default='',
            verbose_name='Хэш файла-источника',
            help_text='Контрольная сумма, хэш файла-источника (например, MD5 или SHA256), для проверки целостности'
                      ' и отслеживания изменений в файлах-источниках при повторных загрузках.',
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

        def __unicode__(self):
            return f"source {self.id:0>4}: {self.s_source_name}"

        def __str__(self):
            return self.__unicode__()

        class Meta:
            verbose_name = 'Источник данных'
            verbose_name_plural = 'Источники данных'
            ordering = ('-t_source_data', '-t_source_created')


class TbOfferHistory(models.Model):
    # История изменений оффера. Снапшот цены.
    #
    # Создаётся:
    # - только если что-то реально изменилось (обычно при новом импорте Excel)
    k_offer = models.ForeignKey(
        TbOffer,
        on_delete=models.CASCADE,
        related_name='history'
    )
    f_histopy_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, default=0.00,
        verbose_name='Цена (историческая)',
        help_text='Цена оффера в момент изменения (например, при новом импорте данных). Это историческая'
                  ' цена, которая может отличаться от текущей цены в оффере.'
    )
    i_histopy_quantity = models.IntegerField(
        default=0,
        verbose_name='Количество (историческое)',
        help_text='Количество товара в оффере в момент изменения (например, при новом импорте данных).'
                  ' Это историческое количество, которое может отличаться от текущего количества в оффере.'
    )
    b_histopy_available = models.BooleanField(
        default=True,
        verbose_name='В наличии (историческое)',
        help_text='Наличие товара в оффере в момент изменения (например, при новом импорте данных из Excel).'
                  ' <tt>False</tt> если оффер был в наличии, а при новом импорте стал недоступен.'
                  ' Это историческое наличие, которое может отличаться от текущего наличия в оффере.'
    )
    # Откуда приехало
    k_source = models.ForeignKey(
        to='TbSource',
        null=True, default=None,
        on_delete=models.SET_NULL,
        verbose_name='Источник данных',
        help_text='Источник данных, из которого были импортированы изменения (например, конкретный Excel-файл'
                  ' или URL страницы с данными). Указывать не обязательно, т.к. '
    )
    j_histopy_source_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Метаданные',
        help_text='Метаданные, указывающие координаты данных внутри источника (например, внутри Excel-файла:'
                  ' название вкладки, номер строки, номер столбца с ценой и количеством,'
                  ' или URL + CSS-селектор для HTML-страницы и т.п.',
    )
    t_histopy_source_created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания записи в БД",
    )
    t_histopy_source_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата последнего обновления записи в БД",
    )

    def __unicode__(self):
        return f"offer history {self.id:0>5} for offer {self.k_offer_id:0>4}"

    def __str__(self):
        return self.__unicode__()

    class Meta:
        verbose_name = 'История оффера'
        verbose_name_plural = 'Истории офферов'
        ordering = ('-t_histopy_source_created',)



#         │ 1
#         │
#         │ N
# ┌───────▼────────────┐
# │    ProductImage    │
# ├────────────────────┤
# │ id                 │
# │ product_id         │ FK
# │ image_type         │ ← cover/back/obi/matrix/etc
# │ source             │ ← discogs/manual/vendor
# │ url                │
# │ local_path         │
# │ is_primary         │
# │ sort_order         │
# │ metadata_json      │
# └────────────────────┘
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
