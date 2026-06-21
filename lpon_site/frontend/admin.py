# Кастомная конфигурация Django Admin для LPON сайта.
# Регистрируем модели с удобным интерфейсом.

from django import forms
from django.forms import Textarea
from django.contrib import admin
from django.utils.html import format_html, mark_safe
from easy_thumbnails.files import get_thumbnailer
from .models import (
    TbImage, TbArticle, TbArtist, TbItem, TbLabel, TbSeller,
    TbOffer, TbSource, TbOfferHistory, TbMusicStyle
)
from .utils import validate_entity_for_admin_form

# ============================================================================
# АДМИНИСТРИРОВАНИЕ TbImage
#
# Кастомня форма для админки TbImage
class TbImageAdminForm(forms.ModelForm):
    """
    Кастомная форма для TbImage в админке.
    Добавляет виртуальные поля для редактирования метаданных filer_image
    (default_alt_text и default_caption), которые не хранятся в TbImage, но есть в filer_image
    """
    # Виртуальные поля для заполнения метаданных filer_image
    alt_text = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Введите alt-текст для картинки',
        }),
        label='ALT (новый)',
        help_text='Текст для alt-атрибута картинки <tt>&lt;img alt="" .../&gt;</tt>.'
                  ' Будет сохранён в filer_image.default_alt_text'
    )
    title_text = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Введите title-описание картинки',
        }),
        label='TITLE (новый)',
        help_text='Текст для title-атрибута картинки <tt>&lt;img title="" .../&gt;</tt>.'
                  ' Будет сохранён в filer_image.default_caption'
    )
    copyright_text = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'XXXX, Авторские права на изображение',
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
        # Атрибуты для активации CodeMirror редактора
        codemirror_attrs = {
            'data-codemirror-editor': '1',
            'data-width': '100%',    # Ширина для патча (100% займет полную ширину)
        }

        super().__init__(*args, **kwargs)

        # Если редактируем существующую запись, получаем текущие значения из filer
        if self.instance and self.instance.pk and hasattr(self.instance, 'image') and self.instance.image:
            try:
                # Получаем связанные данные из filer_image
                filer_image = self.instance.image

                # Устанавливаем значения из filer в виртуальные поля
                self.fields['alt_text'].initial = filer_image.default_alt_text or ''
                self.fields['title_text'].initial = filer_image.default_caption or ''
                self.fields['copyright_text'].initial = filer_image.author or ''

                # Активируем CodeMirror и устанавливаем CSS-классы для виртуальных полей
                self.fields['alt_text'].widget = Textarea(attrs={
                    **codemirror_attrs,
                    'class': 'codemirror-width-m',
                })
                self.fields['title_text'].widget = Textarea(attrs={
                    **codemirror_attrs,
                    'class': 'codemirror-width-l',
                })
                self.fields['copyright_text'].widget = Textarea(attrs={
                    **codemirror_attrs,
                    'class': 'codemirror-width-m',
                })
            except Exception:
                # Если ошибка при получении filer_image, просто оставляем пустые значения
                pass

        # Активируем CodeMirror и устанавливаем классы для реальных полей
        self.fields['s_img_src_url'].widget = Textarea(attrs={
            **codemirror_attrs,
            'data-language': 'url',
            'class': 'codemirror-width-xl',
        })
        self.fields['i_img_sort'].widget = Textarea(attrs={
            **codemirror_attrs,
            'class': 'codemirror-width-s codemirror-no-lines',
        })
        self.fields['f_img_confidence_score'].widget = Textarea(attrs={
            **codemirror_attrs,
            'class': 'codemirror-width-s codemirror-no-lines',
        })

# Админка для TbImage с кастомной формой
class ImageAdmin(admin.ModelAdmin):
    """
    Админ для изображений TbImage с поддержкой редактирования метаданных filer_image.

    Позволяет пользователю заполнить default_alt_text и default_caption для картинки в filer
    прямо в админке TbImage, без необходимости отдельного редактирования filer.
    """
    form = TbImageAdminForm  # Используем кастомную форму с виртуальными полями

    # Подключаем JS через Media (правильный способ!)
    class Media:
        css = {
            'all': ('codemirror/codemirror-styles.css',)  # Стили для CodeMirror
        }
        js = (
            'codemirror/editor.js',              # Основной CodeMirror
            'codemirror/codemirror-patch.js',    # Патч для управления высотой/шириной
        )

    list_display = ('id', 'image_thumbnail', 'image', '_display_alt_text', 'i_img_sort', 't_img_created')
    list_display_links = ('id', 'image_thumbnail', 'image')
    list_filter = ('l_img_source', 'l_img_reality', 't_img_created')
    ordering = ('image', 'i_img_sort')
    readonly_fields = ('t_img_created', 't_img_updated', '_display_alt_text', '_display_title_text')

    fieldsets = (
        ('Изображение', {
            'fields': ('image', 'l_img_source', 'l_img_reality', 's_img_src_url', 'i_img_sort',
                       'f_img_confidence_score'),
            'description': 'Основные данные об изображении и источнике',
        }),
        ('Метаданные filer (SEO для картинок)', {
            'fields': ('_display_alt_text', '_display_title_text', 'alt_text', 'title_text',
                       'copyright_text'),
            'description': 'Редактируемые поля для заполнения ALT-, TITLE- и ©-текста в filer. Если не заполнить,'
                           ' текущие значения останутся без изменений (и не будут заполнены при создании).',
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

    def _display_alt_text(self, obj):
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

    _display_alt_text.short_description = 'ALT из filer'

    def _display_title_text(self, obj):
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

    _display_title_text.short_description = 'TITLE из filer'

    def save_model(self, request, obj, form, change):
        """
        Переопределяем save_model для обновления метаданных filer_image.

        Если пользователь заполнил виртуальные поля alt_text или title_text,
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
                alt_text = form.cleaned_data.get('alt_text', '').strip()
                if alt_text:  # Если пользователь что-то ввел
                    filer_image.default_alt_text = alt_text

                # Обновляем caption (TITLE), если было заполнено в форме
                caption = form.cleaned_data.get('title_text', '').strip()
                if caption:  # Если пользователь что-то ввел
                    filer_image.default_caption = caption

                # Обновляем author (copyrughight), если было заполнено в форме
                author = form.cleaned_data.get('copyright_text', '').strip()
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
# АДМИНКА для музыкальных стилей, таблица TbMusicStyle
#
# Кастомная форма для MusicStyleAdmin
class MusicStyleAdminForm(forms.ModelForm):
    """
    Кастомная форма для админки музыкальных стилей.
    Добавляет виджеты CodeMirror для текстовых полей
    """
    class Meta:
        model = TbMusicStyle
        fields = ('s_style_name', 'j_style_synonyms', 'k_style_to_article',)

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем
        """
        # Атрибуты для активации CodeMirror редактора
        codemirror_attrs = {
            'data-codemirror-editor': '1',
            'data-width': '100%',  # Ширина для патча (100% займет полную ширину)
        }

        super().__init__(*args, **kwargs)

        # Активируем CodeMirror и устанавливаем классы для реальных полей
        self.fields['s_style_name'].widget = Textarea(attrs={
            **codemirror_attrs,
            'data-codemirror-mode': 'text',
            'class': 'codemirror-width-xl codemirror-no-lines',
        })
        self.fields['j_style_synonyms'].widget = Textarea(attrs={
            **codemirror_attrs,
            'data-language': 'json',
            'class': 'codemirror-width-l codemirror-min-height-5',
        })

# Админка для TbMusicStyle с кастомной формой MusicStyleAdminForm
class MusicStyleAdmin(admin.ModelAdmin):
    """Админ для музыкальных стилей"""
    form = MusicStyleAdminForm

    # Подключаем JS через Media (правильный способ!)
    class Media:
        css = {
            'all': ('codemirror/codemirror-styles.css',)  # Стили для CodeMirror
        }
        js = (
            'codemirror/editor.js',              # Основной CodeMirror
            'codemirror/codemirror-patch.js',    # Патч для управления высотой/шириной
        )

    list_display = ('id', 's_style_name', 'j_style_synonyms', 't_style_created', 't_style_updated',)
    list_display_links = ('id', 's_style_name',)
    search_fields = ('s_style_name', 'j_style_synonyms',)
    readonly_fields = ('t_style_created', 't_style_updated',)
    fieldsets = (
        ('Основные данные о музыкальном стиле', {
            'fields': ('s_style_name', 'j_style_synonyms',),
        }),
        ('Связанная публикация', {
            'fields': ('k_style_to_article',),
            'description': 'Прикреп&shy;ленная статья (если есть) будет отображаться на&nbsp;странице музыкального'
                           ' стиля на&nbsp;сайте. Также позволяет получать список всех альбомов музыкального стиля,'
                           ' управлять SEO-атрибутами для&nbsp;улучшения видимости поисковых систем, иметь красивый'
                           ' slag для&nbsp;URL-странички, подсчитывать число просмотров и&nbsp;добавлений'
                           ' в&nbsp;избранные. <b style=\'color: green;\'>ОЧЕНЬ РЕКОМЕН&shy;ДУЕТСЯ СОЗДАВАТЬ'
                           ' И&nbsp;ПРИВЯЗЫВАТЬ СТАТЬЮ ВРУЧНУЮ</b>. Если публикация не&nbsp;создана вручную,'
                           ' то&nbsp;она будет создана автоматически (пустая) при&nbsp;сохранении музыкального стиля,'
                           ' со&nbsp;всеми SEO-атрибутами и&nbsp;slag, но&nbsp;автоматика несовершенна.<br />&nbsp;',
            # 'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_style_created', 't_style_updated'),
            'classes': ('collapse',),
        }),
    )


# ============================================================================
# АДМИНКА для Исполнителей/Групп/Артистов, таблица TbArtist
#
# Кастомная форма для ArtistAdmin
class ArtistAdminForm(forms.ModelForm):
    """
    Кастомная форма для админки продавца (Seller).
    Добавляет виджеты CodeMirror для текстовых полей
    """
    class Meta:
        model = TbArtist
        fields = ('s_artist', 'k_artist_to_article', 'j_artist_metadata', )

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем
        """
        # Атрибуты для активации CodeMirror редактора
        codemirror_attrs = {
            'data-codemirror-editor': '1',
            'data-width': '100%',    # Ширина для патча (100% займет полную ширину)
        }

        super().__init__(*args, **kwargs)

        # Активируем CodeMirror и устанавливаем классы для реальных полей
        self.fields['s_artist'].widget = Textarea(attrs={
            **codemirror_attrs,
            'data-codemirror-mode': 'text',
            'class': 'codemirror-width-xl codemirror-no-lines',
        })
        self.fields['j_artist_metadata'].widget = Textarea(attrs={
            **codemirror_attrs,
            'data-language': 'json',
            'class': 'codemirror-width-l codemirror-min-height-5',
        })

# Админка для TbArtist с кастомной формой ArtistAdminForm
class ArtistAdmin(admin.ModelAdmin):
    """Админ для артистов"""
    form = ArtistAdminForm  # Используем кастомную форму с виртуальными полями

    # Подключаем JS через Media (правильный способ!)
    class Media:
        css = {
            'all': ('codemirror/codemirror-styles.css',)  # Стили для CodeMirror
        }
        js = (
            'codemirror/editor.js',              # Основной CodeMirror
            'codemirror/codemirror-patch.js',    # Патч для управления высотой/шириной
        )

    list_display = ('id', 's_artist', 't_artist_created')
    list_display_links = ('id', 's_artist',)
    search_fields = ('s_artist',)
    readonly_fields = ('t_artist_created', 't_artist_updated')
    fieldsets = (
        ('Основные данные об исполнителе (артисте, группе)', {
            'fields': ('s_artist', 'j_artist_metadata',),
        }),
        ('Связанная публикация', {
            'fields': ('k_artist_to_article', ),
            'description': 'Прикреп&shy;ленная статья (если есть) будет отображаться на&nbsp;странице исполнителя'
                           ' на&nbsp;сайте. Также позволяет получать список всех альбомов исполнителя, управлять'
                           ' SEO-атрибутами для&nbsp;улучшения видимости поисковых систем, иметь красивый'
                           ' slag для&nbsp;URL-странички, подсчитывать число просмотров и&nbsp;добавлений'
                           ' в&nbsp;избранные. <b style=\'color: green;\'>ОЧЕНЬ РЕКОМЕН&shy;ДУЕТСЯ СОЗДАВАТЬ'
                           ' И&nbsp;ПРИВЯЗЫВАТЬ СТАТЬЮ ВРУЧНУЮ</b>. Если публикация не&nbsp;создана вручную,'
                           ' то&nbsp;она будет создана автоматически (пустая) при&nbsp;сохранении исполнителя,'
                           ' со&nbsp;всеми SEO-атрибутами и&nbsp;slag, но&nbsp;автоматика несовершенна.<br />&nbsp;',
            # 'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_artist_created', 't_artist_updated'),
            'classes': ('collapse',),
        }),
    )


# ================
# АДМИН-ПАНЕЛЬ ДЛЯ ЛЕЙБЛОВ/ИЗДАТЕЛЕЙ
#
# Кастомная форма
class LabelAdminForm(forms.ModelForm):
    """
    Кастомная форма для админки лейблов (Label).
    Добавляет виджеты CodeMirror для текстовых полей
    """

    class Meta:
        model = TbLabel
        fields = ('s_label', 'k_label_to_article', 'j_label_metadata',)

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror.
        Получаем request из kwargs, переданных из get_form_kwargs в AdminClass.
        """
        # Извлекаем request из kwargs если он есть
        self.request = kwargs.pop('request', None)

        # Атрибуты для активации CodeMirror редактора
        codemirror_attrs = {
            'data-codemirror-editor': '1',
            'data-width': '100%',    # Ширина для патча (100% займет полную ширину)
        }

        super().__init__(*args, **kwargs)


        # Активируем CodeMirror и устанавливаем классы для реальных полей
        self.fields['s_label'].widget = Textarea(attrs={
            **codemirror_attrs,
            'class': 'codemirror-width-xl codemirror-no-lines',
            'data-language': 'text',
        })
        self.fields['j_label_metadata'].widget = Textarea(attrs={
            **codemirror_attrs,
            'class': 'codemirror-width-l codemirror-min-height-5',
            'data-language': 'json',
        })


    def clean(self):
        """
        Валидируем форму: проверяем на совпадения (дубликаты) основного поля s_label.
        Используем GET параметр ignore_validate для пропуска валидации при переотправке.
        """
        cleaned_data = super().clean()

        # Используем универсальный хелпер для проверки дубликатов
        # Модель берется автоматически из self.Meta.model
        # Передаем request для проверки GET параметра ignore_validate
        validate_entity_for_admin_form(
            self,
            cleaned_data,
            main_field_name='s_label',
            metadata_field_name='j_label_metadata',
            request=self.request,
        )

        return cleaned_data

# Админ для лейбла (Label)
class LabelAdmin(admin.ModelAdmin):
    """Админ для лейблов"""
    form = LabelAdminForm  # Используем кастомную форму с виджетами CodeMirror

    # Подключаем JS через Media (правильный способ!)
    class Media:
        css = {
            'all': ('codemirror/codemirror-styles.css',)  # Стили для CodeMirror
        }
        js = (
            'codemirror/editor.js',              # Основной CodeMirror
            'codemirror/codemirror-patch.js',    # Патч для управления высотой/шириной
        )

    list_display = ('id', 's_label', 't_label_created')
    list_display_links = ('id', 's_label',)
    search_fields = ('s_label',)
    readonly_fields = ('t_label_created', 't_label_updated')
    fieldsets = (
        ('Основные данные о лейбле/издателе', {
            'fields': ('s_label', 'j_label_metadata',),
        }),
        ('Связанная публикация', {
            'fields': ('k_label_to_article', ),
            'description': 'Прикреп&shy;ленная статья (если есть) будет отображаться на&nbsp;странице лейбла'
                           ' на&nbsp;сайте. Также позволяет получать список всех альбомов лейбла, управлять'
                           ' SEO-атрибутами для&nbsp;улучшения видимости поисковых систем, иметь красивый'
                           ' slag для&nbsp;URL-странички, подсчитывать число просмотров и&nbsp;добавлений'
                           ' в&nbsp;избранные. <b style=\'color: green;\'>ОЧЕНЬ РЕКОМЕН&shy;ДУЕТСЯ СОЗДАВАТЬ'
                           ' И&nbsp;ПРИВЯЗЫВАТЬ СТАТЬЮ ВРУЧНУЮ</b>. Если публикация не&nbsp;создана вручную,'
                           ' то&nbsp;она будет создана автоматически (пустая) при&nbsp;сохранении лейбла,'
                           ' со&nbsp;всеми SEO-атрибутами и&nbsp;slag, но&nbsp;автоматика несовершенна.<br />&nbsp;',
            # 'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_label_created', 't_label_updated'),
            'classes': ('collapse',),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """
        Переопределяем get_form чтобы передать request в форму.
        Создаем оборачивающий класс который передаст request в __init__.
        """
        FormClass = super().get_form(request, obj, **kwargs)

        # Сохраняем request в замыкании для доступа в классе
        request_ref = request

        class FormWithRequest(FormClass):
            """Оборачивающий класс который передает request при инстанцировании"""
            def __init__(form_instance, *args, **init_kwargs):
                # Добавляем request в kwargs перед вызовом __init__ родителя
                init_kwargs['request'] = request_ref
                super().__init__(*args, **init_kwargs)

        return FormWithRequest




# ================
# АДМИН-ПАНЕЛЬ ДЛЯ ПРОДАВЦА/SELLER
#
# Кастомная форма
class SellerAdminForm(forms.ModelForm):
    """
    Кастомная форма для админки продавца (Seller).
    Добавлaет виджеты CodeMirror для текстовых полей
    """
    class Meta:
        model = TbSeller
        fields = ('id', 's_seller', 'l_seller_currency', 'k_seller_to_article', 'l_seller_type',
                  'j_seller_metadata',)

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем
        """
        # Атрибуты для активации CodeMirror редактора
        codemirror_attrs = {
            'data-codemirror-editor': '1',
            'data-width': '100%',    # Ширина для патча (100% займет полную ширину)
        }

        super().__init__(*args, **kwargs)

        # Активируем CodeMirror и устанавливаем классы для реальных полей
        self.fields['s_seller'].widget = Textarea(attrs={
            **codemirror_attrs,
            'class': 'codemirror-width-l codemirror-no-lines',
            'data-language': 'text',
        })
        self.fields['j_seller_metadata'].widget = Textarea(attrs={
            **codemirror_attrs,
            'class': 'codemirror-width-xl codemirror-min-height-5',
            'data-language': 'json',
        })

# Админ для продавца (Seller)
class SellerAdmin(admin.ModelAdmin):
    """Админ для продавцов"""
    form = SellerAdminForm  # Используем кастомную форму с виртуальными полями

    # Подключаем JS через Media (правильный способ!)
    class Media:
        css = {
            'all': ('codemirror/codemirror-styles.css',)  # Стили для CodeMirror
        }
        js = (
            'codemirror/editor.js',              # Основной CodeMirror
            'codemirror/codemirror-patch.js',    # Патч для управления высотой/шириной
        )
    list_display = ('id', 's_seller', 'l_seller_type', 'l_seller_currency', 't_seller_created',)
    list_display_links = ('id', 's_seller',)
    list_filter = ('l_seller_type', 'l_seller_currency',)
    search_fields = ('s_seller',)
    readonly_fields = ('t_seller_created', 't_seller_updated',)
    fieldsets = (
        ('Основные данные о продавце', {
            'fields': ('s_seller', 'l_seller_currency', 'l_seller_type',
                       'j_seller_metadata',),
        }),
        ('Связанная публикация', {
            'fields': ('k_seller_to_article', ),
            'description': 'Прикреп&shy;ленная статья (если есть) будет отображаться на&nbsp;странице продавца'
                           ' на&nbsp;сайте. Также позволяет получать список всех предложений продавца, управлять'
                           ' SEO-атрибутами для&nbsp;улучшения видимости поисковых систем, иметь красивый'
                           ' slag для&nbsp;URL-странички, подсчитывать число просмотров и&nbsp;добавлений'
                           ' в&nbsp;избранные. <b style=\'color: green;\'>ОЧЕНЬ РЕКОМЕН&shy;ДУЕТСЯ СОЗДАВАТЬ'
                           ' И&nbsp;ПРИВЯЗЫВАТЬ СТАТЬЮ ВРУЧНУЮ</b>. Если публикация не&nbsp;создана вручную,'
                           ' то&nbsp;она будет создана автоматически (пустая) при&nbsp;сохранении продавца,'
                           ' со&nbsp;всеми SEO-атрибутами и&nbsp;slag, но&nbsp;автоматика несовершенна.<br />&nbsp;',
            # 'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_seller_created', 't_seller_updated'),
            'classes': ('collapse',),
        }),
    )


# ============================================================================
# АДМИНКА ИСТОЧНИКОВ ДАННЫХ
#
# Кастомная форма
class SourceAdminForm(forms.ModelForm):
    """
    Кастомная форма для админки источников данных (TbSource).
    Добавляет виджеты CodeMirror для текстовых полей
    """
    class Meta:
        model = TbSource
        fields = ('id', 'k_source_to_seller', 's_source_name', 'l_source_type', 't_source_data',
                  'source_file', 's_source_url', 'j_source_metadata',)

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем
        """
        # Атрибуты для активации CodeMirror редактора
        codemirror_attrs = {
            'data-codemirror-editor': '1',
            'data-width': '100%',    # Ширина для патча (100% займет полную ширину)
        }

        super().__init__(*args, **kwargs)

        # Активируем CodeMirror и устанавливаем классы для реальных полей
        self.fields['s_source_name'].widget = Textarea(attrs={
            **codemirror_attrs,
            'class': 'codemirror-width-l codemirror-no-lines',
            'data-language': 'text',
        })
        self.fields['s_source_url'].widget = Textarea(attrs={
            **codemirror_attrs,
            'class': 'codemirror-width-xl codemirror-no-lines',
            'data-language': 'url',
        })
        self.fields['j_source_metadata'].widget = Textarea(attrs={
            **codemirror_attrs,
            'class': 'codemirror-width-l codemirror-min-height-5',
            'data-language': 'json',
        })

#
class SourceAdmin(admin.ModelAdmin):
    """Админ для источников"""
    form = SourceAdminForm  # Используем кастомную форму с виртуальными полями

    # Подключаем JS через Media (правильный способ!)
    class Media:
        css = {
            'all': ('codemirror/codemirror-styles.css',)  # Стили для CodeMirror
        }
        js = (
            'codemirror/editor.js',              # Основной CodeMirror
            'codemirror/codemirror-patch.js',    # Патч для управления высотой/шириной
        )
    list_display = ('id', 's_source_name', 'k_source_to_seller', 'l_source_type', 't_source_data')
    list_display_links = ('id', 's_source_name',)
    list_filter = ('l_source_type', 't_source_data')
    search_fields = ('s_source_name',)
    readonly_fields = ('t_source_created', 't_source_updated')


# ============================================================================
# Остальные ModelAdmin классы
# ============================================================================


class ItemAdmin(admin.ModelAdmin):
    """Админ для товаров"""
    list_display = ('id', 's_item', 't_item_date', 't_item_created')
    list_filter = ('t_item_date', 't_item_created')
    search_fields = ('s_item',)
    filter_horizontal = ('k_item_to_artist', 'k_item_to_style')
    readonly_fields = ('t_item_created', 't_item_updated')


class OfferAdmin(admin.ModelAdmin):
    """Админ для предложений"""
    list_display = ('id', 's_offer', 'k_offer_to_item', 'f_offer_price', 'i_offer_quantity', 'i_offer_views')
    list_filter = ('l_offer_condition_media', 'l_offer_condition_sleeve', 't_offer_created', 'l_offer_to_format')
    search_fields = ('s_offer',)
    filter_horizontal = ('k_offer_to_image',)
    readonly_fields = ('s_offer_skip32', 't_offer_created', 't_offer_updated', 'i_offer_views', 'i_offer_favorites')


class ArticleAdmin(admin.ModelAdmin):
    """Админ для статей"""
    list_display = ('id', 's_article_title', 'l_article_type', 'b_article_published', 't_article_created')
    list_filter = ('l_article_type', 'b_article_published', 't_article_created')
    search_fields = ('s_article_title', 'slug')
    prepopulated_fields = {'slug': ('s_article_title',)}
    readonly_fields = ('t_article_created', 't_article_updated')
    # filter_horizontal = ('k_article_to_styles',)


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



