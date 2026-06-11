# Кастомная конфигурация Django Admin для LPON сайта.
# Регистрируем модели с удобным интерфейсом.

from django import forms
from django.contrib import admin
from django.utils.html import format_html, mark_safe
from easy_thumbnails.files import get_thumbnailer
from .models import (
    TbImage, TbArticle, TbArtist, TbItem, TbLabel, TbSeller,
    TbOffer, TbSource, TbOfferHistory, TbMusicStyle, TbFormat
)

# ============================================================================
# Кастомная форма для админки TbImage
# ============================================================================
class TbImageAdminForm(forms.ModelForm):
    """
    Кастомная форма для TbImage в админке.
    Добавляет виртуальные поля для редактирования метаданных filer_image
    (default_alt_text и default_caption), которые не хранятся в TbImage, но есть в filer_image
    """
    # Виртуальные поля для заполнения метаданных filer_image
    filer_alt_text = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Введите alt-текст для картинки',
            'class': 'vTextField',
            'size': 200,
        }),
        label='ALT (новый)',
        help_text='Текст для alt-атрибута картинки <tt>&lt;img alt="" .../&gt;</tt>.'
                  ' Будет сохранён в filer_image.default_alt_text'
    )
    filer_caption = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Введите title-описание картинки',
            'class': 'vTextField',
            'cols': 120,
        }),
        label='TITLE (новый)',
        help_text='Текст для title-атрибута картинки <tt>&lt;img title="" .../&gt;</tt>.'
                  ' Будет сохранён в filer_image.default_caption'
    )
    filer_copyright = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'XXXX, Авторские права на изображение',
            'class': 'vTextField',
            'cols': 120,
        }),
        label='Copyright',
        help_text='Авторские права на изображение (например: <tt>2025, Sergei Erjemin</tt>. Будет сохранён в filer_image.author'
    )

    class Meta:
        model = TbImage
        fields = ('image', 'l_img_source', 'l_img_reality', 's_img_src_url', 'i_img_sort', 'f_img_confidence_score')

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем текущие значения alt/caption из filer_image.
        """
        super().__init__(*args, **kwargs)

        # Если редактируем существующую запись, получаем текущие значения из filer
        if self.instance and self.instance.pk and hasattr(self.instance, 'image') and self.instance.image:
            try:
                filer_image = self.instance.image
                # Получаем текущие значения из filer и заполняем виртуальные поля
                self.fields['filer_alt_text'].initial = filer_image.default_alt_text or ''
                self.fields['filer_caption'].initial = filer_image.default_caption or ''
                self.fields['filer_copyright'].initial = filer_image.author or ''
            except Exception:
                # Если ошибка при получении filer_image, просто оставляем пустые значения
                pass


class ImageAdmin(admin.ModelAdmin):
    """
    Админ для изображений TbImage с поддержкой редактирования метаданных filer_image.

    Позволяет пользователю заполнить default_alt_text и default_caption для картинки в filer
    прямо в админке TbImage, без необходимости отдельного редактирования фiler.
    """
    form = TbImageAdminForm  # Используем кастомную форму с виртуальными полями
    list_display = ('id', 'image_thumbnail', 'image', '_display_filer_alt_text', 'i_img_sort', 't_img_created')
    list_display_links = ('id', 'image_thumbnail', 'image')
    list_filter = ('l_img_source', 'l_img_reality', 't_img_created')
    ordering = ('image', 'i_img_sort')
    readonly_fields = ('t_img_created', 't_img_updated', '_display_filer_alt_text', '_display_filer_caption')
    fieldsets = (
        ('Изображение', {
            'fields': ('image', 'l_img_source', 'l_img_reality', 's_img_src_url', 'i_img_sort',
                       'f_img_confidence_score'),
            'description': 'Основные данные об изображении и источнике',
        }),
        ('Метаданные filer (SEO для картинок)', {
            'fields': ('_display_filer_alt_text', '_display_filer_caption', 'filer_alt_text', 'filer_caption',
                       'filer_copyright'),
            'description': 'Редактируемые поля для заполнения Alt текста и описания в filer. Если не заполнить,'
                           ' текущие значения останутся без изменений (или не будут заполнены при создании).',
            # 'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_img_created', 't_img_updated'),
            'classes': ('collapse',),
        }),
    )

    def image_thumbnail(self, obj):
        """
        Отображает миниатюру картинки (40x40) в списке и в list_display_links.
        Использует easy_thumbnails для автоматического создания и кэширования миниатюр.
        """
        if obj and obj.image:
            try:
                # Получаем thumbnailer для картинки через easy_thumbnails
                thumbnailer = get_thumbnailer(obj.image.file)

                # Генерируем или получаем уже созданную миниатюру размером 40x40
                thumbnail = thumbnailer.get_thumbnail({
                    'size': (40, 40),            # Размер миниатюры: 40x40 пикселей
                    'crop': 'smart',             # Умное обрезание для сохранения центра картинки
                    'quality': 95,               # Качество JPEG/WebP (95% для хорошего вида)
                })

                # Возвращаем HTML тег img с миниатюрой
                # format_html автоматически экранирует опасные символы
                return format_html(
                    '<img src="{}" width="40" height="40" alt="{}" '
                    'style="border-radius: 4px; object-fit: cover; cursor: pointer;"/>',
                    thumbnail.url,
                    obj.image.name or 'картинка'  # Alt текст для доступности
                )
            except Exception as e:
                # Если ошибка при генерации миниатюры (нет файла, ошибка формата и т.д.)
                return mark_safe('<span style="color: #ccc;">(ошибка)</span>')

        # Если картинка не привязана
        return mark_safe('<span style="color: #ccc;">(нет картинки)</span>')

    # Установляем название столбца в админке
    image_thumbnail.short_description = 'Миниатюра (40x40)'

    def _display_filer_alt_text(self, obj):
        """
        Display-метод для отображения текущего alt-текста в filer (read-only).
        Показывает, какой текст сейчас установлен в filer_image.
        """
        if obj and obj.pk and obj.image:
            try:
                current = obj.image.default_alt_text or '(пусто)'
                return f'ALT: {current}'
            except Exception:
                return '(ошибка при получении)'
        return '(новая запись, значение будет установлено после сохранения)'

    _display_filer_alt_text.short_description = 'ALT из filer'

    def _display_filer_caption(self, obj):
        """
        Display-метод для отображения текущего caption в filer (read-only).
        Показывает, какой текст сейчас установлен в filer_image.
        """
        if obj and obj.pk and obj.image:
            try:
                current = obj.image.default_caption or '(пусто)'
                return f'TITLE: {current}'
            except Exception:
                return '(ошибка при получении)'
        return '(новая запись, значение будет установлено после сохранения)'

    _display_filer_caption.short_description = 'TITLE из filer'

    def save_model(self, request, obj, form, change):
        """
        Переопределяем save_model для обновления метаданных filer_image.

        Если пользователь заполнил виртуальные поля filer_alt_text или filer_caption,
        их значения сохраняются в соответствующие поля filer_image.
        Если поля не заполнены, текущие значения в filer остаются без изменений.
        """
        # Сначала сохраняем саму запись TbImage
        super().save_model(request, obj, form, change)

        # Работаем с meta-данными filer только если картинка привязана
        if obj.image:
            try:
                filer_image = obj.image

                # Обновляем alt_text (ALT), если было заполнено в форме
                alt_text = form.cleaned_data.get('filer_alt_text', '').strip()
                if alt_text:  # Если пользователь что-то ввел
                    filer_image.default_alt_text = alt_text

                # Обновляем caption (TITLE), если было заполнено в форме
                caption = form.cleaned_data.get('filer_caption', '').strip()
                if caption:  # Если пользователь что-то ввел
                    filer_image.default_caption = caption

                # Обновляем author (copyrughight), если было заполнено в форме
                author = form.cleaned_data.get('filer_copyright', '').strip()
                if author:
                    filer_image.author = author

                # Сохраняем filer_image с новыми метаданными
                filer_image.save()

            except Exception as e:
                # Логируем ошибку, но не прерываем процесс сохранения
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Ошибка при сохранении метаданных filer_image: {e}')


# ============================================================================
# Остальные ModelAdmin классы
# ============================================================================

class ArticleAdmin(admin.ModelAdmin):
    """Админ для статей"""
    list_display = ('id', 's_article_title', 'l_article_type', 'b_article_published', 't_article_created')
    list_filter = ('l_article_type', 'b_article_published', 't_article_created')
    search_fields = ('s_article_title', 'slug')
    prepopulated_fields = {'slug': ('s_article_title',)}
    readonly_fields = ('t_article_created', 't_article_updated')
    filter_horizontal = ('k_article_to_styles',)


class MusicStyleAdmin(admin.ModelAdmin):
    """Админ для музыкальных стилей"""
    list_display = ('id', 's_style_name', 's_style_slug')
    search_fields = ('s_style_name', 's_style_slug')
    readonly_fields = ('s_style_slug',)


class FormatAdmin(admin.ModelAdmin):
    """Админ для форматов"""
    list_display = ('id', 's_format', 's_format_slug')
    search_fields = ('s_format',)
    readonly_fields = ('s_format_slug',)


class ArtistAdmin(admin.ModelAdmin):
    """Админ для артистов"""
    list_display = ('id', 's_artist', 't_artist_created')
    search_fields = ('s_artist',)
    readonly_fields = ('t_artist_created', 't_artist_updated')


class ItemAdmin(admin.ModelAdmin):
    """Админ для товаров"""
    list_display = ('id', 's_item', 't_item_date', 't_item_created')
    list_filter = ('t_item_date', 't_item_created')
    search_fields = ('s_item',)
    filter_horizontal = ('k_item_to_artist',)
    readonly_fields = ('t_item_created', 't_item_updated')


class LabelAdmin(admin.ModelAdmin):
    """Админ для лейблов"""
    list_display = ('id', 's_label', 't_label_created')
    search_fields = ('s_label',)
    readonly_fields = ('t_label_created', 't_label_updated')


class SellerAdmin(admin.ModelAdmin):
    """Админ для продавцов"""
    list_display = ('id', 's_seller', 'l_seller_type', 't_seller_created')
    list_filter = ('l_seller_type',)
    search_fields = ('s_seller',)
    readonly_fields = ('t_seller_created', 't_seller_updated')


class SourceAdmin(admin.ModelAdmin):
    """Админ для источников"""
    list_display = ('id', 's_source_name', 'k_source_to_seller', 'l_source_type', 'l_source_currency', 't_source_data')
    list_filter = ('l_source_type', 'l_source_currency', 't_source_data')
    search_fields = ('s_source_name',)
    readonly_fields = ('t_source_created', 't_source_updated')


class OfferAdmin(admin.ModelAdmin):
    """Админ для предложений"""
    list_display = ('id', 's_offer', 'k_offer_to_item', 'f_offer_price', 'i_offer_quantity', 'i_offer_views')
    list_filter = ('l_offer_condition_media', 'l_offer_condition_sleeve', 't_offer_created')
    search_fields = ('s_offer',)
    filter_horizontal = ('k_offer_to_format', 'k_offer_to_image')
    readonly_fields = ('s_offer_skip32', 't_offer_created', 't_offer_updated', 'i_offer_views', 'i_offer_favorites')


class OfferHistoryAdmin(admin.ModelAdmin):
    """Админ для истории изменений офферов"""
    list_display = ('id', 'k_history_to_offer', 'f_history_price', 'i_history_quantity', 't_history_created')
    list_filter = ('t_history_created',)
    readonly_fields = ('t_history_created',)


# ============================================================================
# Регистрация моделей в дефолтном admin.site
# ============================================================================
admin.site.register(TbImage, ImageAdmin)
admin.site.register(TbArticle, ArticleAdmin)
admin.site.register(TbMusicStyle, MusicStyleAdmin)
admin.site.register(TbFormat, FormatAdmin)
admin.site.register(TbArtist, ArtistAdmin)
admin.site.register(TbItem, ItemAdmin)
admin.site.register(TbLabel, LabelAdmin)
admin.site.register(TbSeller, SellerAdmin)
admin.site.register(TbSource, SourceAdmin)
admin.site.register(TbOffer, OfferAdmin)
admin.site.register(TbOfferHistory, OfferHistoryAdmin)

# User и Group уже зарегистрированы auth приложением

# ============================================================================
# Кастомизация админ-сайта через ready() в apps.py (переименование через verbose_name)
# ============================================================================



