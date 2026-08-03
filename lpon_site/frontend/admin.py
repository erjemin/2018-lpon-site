# Кастомная конфигурация Django Admin для LPON сайта.
# Регистрируем модели с удобным интерфейсом.

import etpgrf
import logging
from typing import Any
from django import forms
from django.forms import Textarea
from django.http import HttpRequest
from django.contrib import admin
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.html import format_html, mark_safe
from easy_thumbnails.files import get_thumbnailer
from .models import (
    TbImageMetadata, TbArticle, TbArtist, TbItem, TbLabel, TbSeller,
    TbOffer, TbSource, TbOfferHistory, TbMusicStyle
)
from .utils_validators import validate_entity_for_admin_form, generate_admin_save_message
from .utils import make_slug

logger = logging.getLogger(__name__)


# ============================================================================
# ЛОКАЛЬНЫЕ ХЕЛПЕРЫ ДЛЯ АДМИНКИ
# ============================================================================

def get_related_article_description(model_class):
    """
    Генерирует HTML-описание для fieldset'а 'Связанная публикация'.

    Описание объясняет роль связанной статьи и предлагает создавать её вручную.
    Использует verbose_name из модели для универсальности.

    Args:
        model_class: Класс модели (TbLabel, TbArtist, TbMusicStyle и т.д.)

    Returns:
        str: HTML-описание для fieldset'а

    Пример:
        'description': get_related_article_description(TbLabel)
    """
    # Получаем наименование модели в родительном падеже (для описания)
    verbose_name = model_class._meta.verbose_name.upper()

    # Получаем наименование во множественном числе (для списков альбомов)
    verbose_name_plural = model_class._meta.verbose_name_plural.upper()

    return (f'Прикреп&shy;ленная статья (если есть) будет отображаться на&nbsp;странице <u>{verbose_name}</u>'
            f' на&nbsp;сайте. Также позволяет получать список всех альбомов <u>{verbose_name_plural}</u>,'
            f' управлять SEO-атрибутами для&nbsp;улучшения видимости поисковых систем, иметь красивый'
            f' slag для&nbsp;URL-странички, подсчитывать число просмотров и&nbsp;добавлений'
            f' в&nbsp;избранные. <b style=\'color: green;\'>ОЧЕНЬ РЕКОМЕН&shy;ДУЕТСЯ СОЗДАВАТЬ'
            f' И&nbsp;ПРИВЯЗЫВАТЬ СТАТЬЮ ВРУЧНУЮ</b>. Если публикация не&nbsp;создана вручную,'
            f' то&nbsp;она будет создана автоматически (пустая) при&nbsp;сохранении <u>{verbose_name}</u>,'
            f' со&nbsp;всеми SEO-атрибутами и&nbsp;slag, но&nbsp;автоматика несовершенна.<br />&nbsp;')


def render_image_thumbnail(image_field, size=(40, 40), title='img'):
    """
    Универсальный хелпер для отображения миниатюры изображения в админке.
     
    Используется в ModelAdmin.list_display для показа превью картинок.
    Использует easy_thumbnails для автоматического создания и кэширования миниатюр.
    Параметры качества и формата берутся из settings (THUMBNAIL_FORMAT, THUMBNAIL_QUALITY).
     
    Args:
        image_field: Объект изображения (FilerImageField или ImageFieldFile) или None
        size: Кортеж (ширина, высота) для миниатюры. По умолчанию (40, 40)
        title: Описание картинки в alt атрибуте (по умолчанию 'img')
     
    Returns:
        str: HTML-строка с тегом img или сообщение об ошибке
     
    Примеры:
        # В методе ModelAdmin:
        def image_thumbnail(self, obj):
            return render_image_thumbnail(obj.image, size=(40, 40), title='Изображение')
    """
    if image_field:
        try:
            # Получаем thumbnailer для картинки через easy_thumbnails
            thumbnailer = get_thumbnailer(image_field.file)

            # Генерируем или получаем уже созданную миниатюру
            # Параметры берутся из django.conf.settings (THUMBNAIL_FORMAT, THUMBNAIL_QUALITY)
            # Это гарантирует единообразие со всеми остальными миниатюрами в проекте
            thumbnail = thumbnailer.get_thumbnail({
                'size': size,                                              # Размер миниатюры
                'crop': 'smart',                                           # Умное обрезание для сохранения центра
                'quality': getattr(settings, 'THUMBNAIL_QUALITY', 80),     # Качество из settings (по умолчанию 80)
            })

            # Возвращаем HTML тег img с миниатюрой
            # format_html автоматически экранирует опасные символы
            width, height = size
            return format_html(
                '<img src="{}" width="{}" height="{}" title="{}" alt="" style="object-fit: cover; "/>',
                thumbnail.url,  # ← Параметры отдельно
                width//2,
                height//2,
                image_field.name or title
            )
        except Exception as e:
            # Если ошибка при генерации миниатюры (нет файла, ошибка формата и т.д.)
            logger.exception(f"Ошибка при генерации миниатюры изображения: {e}")
            return mark_safe('<span style="color: #ccc;">(ошибка)</span>')

    # Если картинка не привязана
    return mark_safe('<img width="20" height="20" title="Нет изображения" alt="" style="background: #90909060;"/>')



# ============================================================================
# МИКСИНЫ ДЛЯ АДМИНКИ
# ============================================================================
class RequestInFormMixin(admin.ModelAdmin):
    """
    Миксин для передачи request объекта в форму.

    Используется когда форма нуждается в доступе к request для проверки POST параметров
    или другой информации о текущем HTTP-запросе.

    Переопределяет get_form() и передает request в __init__ формы через kwargs.
    """

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


class CodeMirrorFormMixin(forms.ModelForm):
    """
    Миксин для форм с поддержкой CodeMirror редактора.

    Предоставляет:
    - Готовый Media класс с CSS и JS для CodeMirror
    - Helper метод setup_codemirror_field() для конфигурации полей
    - Базовые атрибуты для активации CodeMirror

    Использование:
        class MyForm(CodeMirrorFormMixin):
            class Meta:
                model = MyModel
                fields = (...)

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.setup_codemirror_field('field_name', 'json', 'codemirror-width-l')
    """

    # ===== MEDIA КЛАСС ДЛЯ CODEMIRROR =====
    class Media:
        """Подключаем CSS и JS для CodeMirror редактора"""
        css = {
            'all': ('codemirror/codemirror-styles.css',)  # Стили для CodeMirror
        }
        js = (
            'codemirror/editor.js',              # Основной CodeMirror
            'codemirror/codemirror-patch.js',    # Патч для управления высотой/шириной
        )

    # ===== БАЗОВЫЕ АТРИБУТЫ CODEMIRROR =====
    CODEMIRROR_ATTRS_BASE = {
        'data-codemirror-editor': '1',
        'data-width': '100%',  # Ширина для патча (100% займет полную ширину)
    }

    def setup_codemirror_field(self, field_name: str, language: str = 'text', css_class: str = 'codemirror-width-l'):
        """
        Конфигурирует поле для использования CodeMirror редактором.

        Применяет Textarea виджет с нужными атрибутами и CSS классами для CodeMirror.

        Args:
            field_name: Имя поля в форме (например, 's_label')
            language: Язык для подсветки синтаксиса (text, json, html, url и т.д.)
            css_class: CSS класс для управления размерами (codemirror-width-s, codemirror-width-l и т.д.)

        Пример:
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.setup_codemirror_field('s_label', 'text', 'codemirror-width-xl codemirror-no-lines')
                self.setup_codemirror_field('j_metadata', 'json', 'codemirror-width-l')
        """
        # Собираем атрибуты для поля
        attrs = {
            **self.CODEMIRROR_ATTRS_BASE,
            'data-language': language,
            'class': css_class,
        }

        # Применяем Textarea виджет с атрибутами
        self.fields[field_name].widget = Textarea(attrs=attrs)


# ============================================================================
# АДМИНИСТРИРОВАНИЕ TbImageMetadata
#
# Кастомная форма для админки TbImageMetadata
class TbImageMetadataAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для TbImageMetadata в админке.
    Добавляет виртуальные поля для редактирования метаданных filer_image
    (default_alt_text и default_caption), которые не хранятся в TbImageMetadata, но есть в filer_image.
    
    Наследует от CodeMirrorFormMixin для поддержки редактора CodeMirror.
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
        model = TbImageMetadata
        fields = ('image', 'i_img_sort', 'j_img_metadata')

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем текущие значения alt/caption из filer_image.
        Настраиваем поля для работы с CodeMirror редактором.
        """
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

            except Exception:
                # Если ошибка при получении filer_image, просто оставляем пустые значения
                pass

        # Активируем CodeMirror для виртуальных полей
        self.setup_codemirror_field('alt_text', language='text',
                                    css_class='codemirror-width-m codemirror-no-lines')
        self.setup_codemirror_field('title_text', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('copyright_text', language='text',
                                    css_class='codemirror-width-m codemirror-no-lines')

        # Активируем CodeMirror для реальных полей
        self.setup_codemirror_field('i_img_sort', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('j_img_metadata', language='json',
                                    css_class='codemirror-width-xl')


# Админка для TbImageMetadata с кастомной формой
class ImageMetadataAdmin(admin.ModelAdmin):
    """
    Админ для метаданных изображений TbImageMetadata с поддержкой редактирования метаданных filer_image.

    Позволяет пользователю заполнить default_alt_text и default_caption для картинки в filer
    прямо в админке TbImageMetadata, без необходимости отдельного редактирования filer.
    
    Использует TbImageMetadataAdminForm с наследованием от CodeMirrorFormMixin для поддержки CodeMirror.
    """
    form = TbImageMetadataAdminForm  # Используем кастомную форму с виртуальными полями (Media подключится через миксин)

    list_display = ('id', 'image_thumbnail', 'image', '_display_alt_text', 'i_img_sort')
    list_display_links = ('id', 'image_thumbnail', 'image')
    list_filter = ('i_img_sort',)
    ordering = ('image', 'i_img_sort')
    readonly_fields = ('_display_alt_text', '_display_title_text')

    fieldsets = (
        ('Изображение', {
            'fields': ('image', 'i_img_sort'),
            'description': 'Файл изображения и порядок его отображения (i_img_sort)',
        }),
        ('Метаданные (JSON)', {
            'fields': ('j_img_metadata',),
            'description': 'Гибкие дополнительные данные в JSON формате (источник, тип, достоверность и т.д.). '
                           'Пример: {"source": "discogs", "reality": "abstract", "confidence": 0.95}',
        }),
        ('Метаданные filer (SEO для картинок)', {
            'fields': ('_display_alt_text', '_display_title_text', 'alt_text', 'title_text',
                       'copyright_text'),
            'description': 'Редактируемые поля для заполнения ALT-, TITLE- и ©-текста в filer. Если не заполнить,'
                           ' текущие значения останутся без изменений (и не будут заполнены при создании).',
            # 'classes': ('collapse',),
        }),
    )

    def image_thumbnail(self, obj):
        """
        Отображает миниатюру картинки (40x40) в списке и в list_display_links.
        Использует universal helper render_image_thumbnail().
        """
        return render_image_thumbnail(obj.image if obj else None, title='картинка')

    # Установляем название столбца в админке
    image_thumbnail.short_description = 'img 40x40'

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

    def save_model(
        self,
        request: HttpRequest,
        obj: TbImageMetadata,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
        """
        Переопределяем save_model для обновления метаданных filer_image.

        Если пользователь заполнил виртуальные поля alt_text или title_text,
        их значения сохраняются в соответствующие поля filer_image.
        Если поля не заполнены, текущие значения в filer остаются без изменений.
        """
        # Сначала сохраняем саму запись TbImageMetadata
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
class MusicStyleAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для админки музыкальных стилей.
    Добавляет виджеты CodeMirror для текстовых полей
    """
    class Meta:
        model = TbMusicStyle
        fields = ('s_style_name', 'j_style_metadata', 'k_style_to_article',)

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror редактор
        """
        # Извлекаем request из kwargs если он есть
        self.request = kwargs.pop('request', None)

        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('s_style_name', language='text',
                                    css_class='codemirror-width-xl codemirror-no-lines')
        self.setup_codemirror_field('j_style_metadata', language='json',
                                    css_class='codemirror-width-l codemirror-min-height-5')

    def clean(self):
        """
        Валидируем форму: проверяем на совпадения (дубликаты) основного поля s_style_name.
        Используем GET параметр ignore_validate для пропуска валидации при переотправке.
        """
        # Получаем очищенные данные формы (может быть None, но обычно это dict)
        cleaned_data: dict[str, Any] | None = super().clean()

        # Если clean() вернул None, возвращаем пустой dict (для совместимости)
        if cleaned_data is None:
            cleaned_data = {}

        # После проверки выше, очищены данные гарантированно dict[str, Any]
        assert isinstance(cleaned_data, dict), "cleaned_data должен быть словарём"

        # Используем универсальный хелпер для проверки дубликатов
        # Модель берется автоматически из self.Meta.model
        # Передаем request для проверки GET параметра ignore_validate
        validate_entity_for_admin_form(
            self,
            cleaned_data,
            main_field_name='s_style_name',
            metadata_field_name='j_style_metadata',
            request=self.request,
        )

        return cleaned_data

# Админка для TbMusicStyle с кастомной формой MusicStyleAdminForm
class MusicStyleAdmin(RequestInFormMixin, admin.ModelAdmin):
    """Админ для музыкальных стилей"""
    form = MusicStyleAdminForm

    # Media наследуется автоматически из CodeMirrorFormMixin
    # ...(no custom Media needed)

    list_display = ('id', 'style_thumbnail', 's_style_name', 'j_style_metadata', 't_style_created', 't_style_updated',)
    list_display_links = ('id', 'style_thumbnail', 's_style_name',)
    search_fields = ('s_style_name', 'j_style_metadata',)
    readonly_fields = ('t_style_created', 't_style_updated',)

    fieldsets = (
        ('Основные данные о музыкальном стиле', {
            'fields': ('s_style_name', 'j_style_metadata',),
        }),
        ('Связанная публикация', {
            'fields': ('k_style_to_article',),
            'description': get_related_article_description(TbMusicStyle),
            # 'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_style_created', 't_style_updated'),
            'classes': ('collapse',),
        }),
    )

    # Обогащение Media из формы (CodeMirrorFormMixin)
    # Используем наследование для расширения, а не перекрытия
    # Это гарантирует что все CSS/JS из формы будут загружены
    class Media(MusicStyleAdminForm.Media):
        css = {'all': (*MusicStyleAdminForm.Media.css['all'], 'css/validation-override.css',)}
        js = (*MusicStyleAdminForm.Media.js, 'js/form-field-watcher.js',)

    def style_thumbnail(self, obj):
        """Миниатюра стиля через связанную статью."""
        article = obj.k_style_to_article
        image = article.k_article_to_image if article else None
        return render_image_thumbnail(image, title='Логотип музыкального стиля')

    style_thumbnail.short_description = 'Лого'

    def save_model(
       self,
       request: HttpRequest,
       obj: TbMusicStyle,
       form: forms.ModelForm,
       change: bool,
    ) -> None:
        """
        Переопределяем save_model для добавления информативных сообщений в админку.

        Максимально поджарый код - все сложности с получением старого значения
        и определением типа операции делает хелпер generate_admin_save_message().
        """
        # Стандартное сохранение записи через Django
        # (в т.ч. автоматическое создание связанной статьи в методе save модели TbMusicStyle)
        super().save_model(request, obj, form, change)

        # Генерируем и отправляем информативное сообщение о сохранении
        # Хелпер сам:
        # - определяет тип операции (create vs update)
        # - формирует нужное сообщение (success vs warning)
        generate_admin_save_message(
            request=request,
            obj=obj,
            is_new=not change,  # Django: change=False для новых, True для существующих
            related_article=obj.k_style_to_article,
            obj_field_name='s_style_name',
            article_title_field='s_article_title',
        )


# ============================================================================
# АДМИНКА для Исполнителей/Групп/Артистов, таблица TbArtist
#
# Кастомная форма для ArtistAdmin
class ArtistAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для админки артистов.
    Добавляет виджеты CodeMirror для текстовых полей
    """
    class Meta:
        model = TbArtist
        fields = ('s_artist', 'k_artist_to_article', 'j_artist_metadata', )

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror редактор
        """
        # Извлекаем request из kwargs если он есть
        self.request = kwargs.pop('request', None)
        
        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('s_artist', language='text',
                                    css_class='codemirror-width-xl codemirror-no-lines')
        self.setup_codemirror_field('j_artist_metadata', language='json',
                                    css_class='codemirror-width-l codemirror-min-height-5')

    def clean(self):
        """
        Валидируем форму: проверяем на совпадения (дубликаты) основного поля s_artist.
        Используем GET параметр ignore_validate для пропуска валидации при переотправке.
        """
        # Получаем очищенные данные формы (может быть None, но обычно это dict)
        cleaned_data: dict[str, Any] | None = super().clean()

        # Если clean() вернул None, возвращаем пустой dict (для совместимости)
        if cleaned_data is None:
            cleaned_data = {}

        # После проверки выше, очищены данные гарантированно dict[str, Any]
        assert isinstance(cleaned_data, dict), "cleaned_data должен быть словарём"

        # Используем универсальный хелпер для проверки дубликатов
        # Модель берется автоматически из self.Meta.model
        # Передаем request для проверки GET параметра ignore_validate
        validate_entity_for_admin_form(
            self,
            cleaned_data,
            main_field_name='s_artist',
            metadata_field_name='j_artist_metadata',
            request=self.request,
        )

        return cleaned_data

# Админка для TbArtist с кастомной формой ArtistAdminForm
class ArtistAdmin(RequestInFormMixin, admin.ModelAdmin):
    """Админ для артистов"""
    form = ArtistAdminForm  # Используем кастомную форму с CodeMirror

    list_display = ('id', 'artist_thumbnail', 's_artist', 't_artist_created')
    list_display_links = ('id', 'artist_thumbnail', 's_artist',)
    search_fields = ('s_artist',)
    readonly_fields = ('t_artist_created', 't_artist_updated')
    fieldsets = (
        ('Основные данные об исполнителе (артисте, группе)', {
            'fields': ('s_artist', 'j_artist_metadata',),
        }),
        ('Связанная публикация', {
            'fields': ('k_artist_to_article', ),
            'description': get_related_article_description(TbArtist),
            # 'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_artist_created', 't_artist_updated'),
            'classes': ('collapse',),
        }),
    )

    # Обогащение Media из формы (CodeMirrorFormMixin)
    # Используем наследование для расширения, а не перекрытия
    # Это гарантирует что все CSS/JS из формы будут загружены
    class Media(ArtistAdminForm.Media):
        css = {'all': (*ArtistAdminForm.Media.css['all'], 'css/validation-override.css', )}
        js = (*ArtistAdminForm.Media.js, 'js/form-field-watcher.js', )

    def artist_thumbnail(self, obj):
        """
        Отображает миниатюру изображения артиста через связанную статью в списке.
        Использует universal helper render_image_thumbnail().
        """
        article = obj.k_artist_to_article
        image = article.k_article_to_image if article else None
        return render_image_thumbnail(image, title='Фото или логотип исполнителя')

    artist_thumbnail.short_description = 'Лого'

    def save_model(
        self,
        request: HttpRequest,
        obj: TbArtist,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
        """
        Переопределяем save_model для добавления информативных сообщений в админку.

        Максимально поджарый код - все сложности с получением старого значения
        и определением типа операции делает хелпер generate_admin_save_message().
        """
        # Стандартное сохранение записи через Django
        # (в т.ч. автоматическое создание связанной статьи в методе save модели TbArtist)
        super().save_model(request, obj, form, change)

        # Генерируем и отправляем информативное сообщение о сохранении
        # Хелпер сам:
        # - определяет тип операции (create vs update)
        # - формирует нужное сообщение (success vs warning)
        generate_admin_save_message(
            request=request,
            obj=obj,
            is_new=not change,  # Django: change=False для новых, True для существующих
            related_article=obj.k_artist_to_article,
            obj_field_name='s_artist',
            article_title_field='s_article_title',
        )


# ================
# АДМИН-ПАНЕЛЬ ДЛЯ ЛЕЙБЛОВ/ИЗДАТЕЛЕЙ
#
# Кастомная форма
class LabelAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для админки лейблов (Label).
    Добавляет виджеты CodeMirror для текстовых полей
    """

    class Meta:
        model = TbLabel
        fields = ('s_label', 'k_label_to_article', 'j_label_metadata',)

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror редактор.
        Получаем request из kwargs, переданных из get_form_kwargs в AdminClass.
        """
        # Извлекаем request из kwargs если он есть
        self.request = kwargs.pop('request', None)

        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('s_label', language='text',
                                    css_class='codemirror-width-xl codemirror-no-lines')
        self.setup_codemirror_field('j_label_metadata', language='json',
                                    css_class='codemirror-width-l codemirror-min-height-5')

    def clean(self):
        """
        Валидируем форму: проверяем на совпадения (дубликаты) основного поля s_label.
        Используем GET параметр ignore_validate для пропуска валидации при переотправке.
        """
        # Получаем очищенные данные формы (может быть None, но обычно это dict)
        cleaned_data: dict[str, Any] | None = super().clean()

        # Если clean() вернул None, возвращаем пустой dict (для совместимости)
        if cleaned_data is None:
            cleaned_data = {}

        # После проверки выше, очищены данные гарантированно dict[str, Any]
        assert isinstance(cleaned_data, dict), "cleaned_data должен быть словарём"

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

# Админ для лейбла (Label) через миксин
class LabelAdmin(RequestInFormMixin, admin.ModelAdmin):
    """Админ для лейблов с поддержкой передачи request в форму"""
    form = LabelAdminForm  # Используем кастомную форму с CodeMirror

    list_display = ('id', 'label_thumbnail', 's_label', 't_label_created')
    list_display_links = ('id', 'label_thumbnail', 's_label',)
    search_fields = ('s_label',)
    readonly_fields = ('t_label_created', 't_label_updated')

    fieldsets = (
        ('Основные данные о лейбле/издателе', {
            'fields': ('s_label', 'j_label_metadata',),
        }),
        ('Связанная публикация', {
            'fields': ('k_label_to_article', ),
            'description': get_related_article_description(TbLabel),
            # 'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_label_created', 't_label_updated'),
            'classes': ('collapse',),
        }),
    )

    # Обогащение Media из формы (CodeMirrorFormMixin)
    # Используем наследование для расширения, а не перекрытия
    # Это гарантирует, что все CSS/JS из формы будут загружены
    class Media(LabelAdminForm.Media):
        css = {'all': (*LabelAdminForm.Media.css['all'], 'css/validation-override.css', )}
        js = (*LabelAdminForm.Media.js, 'js/form-field-watcher.js', )

    def label_thumbnail(self, obj):
        """Миниатюра лейбла через связанную статью."""
        article = obj.k_label_to_article
        image = article.k_article_to_image if article else None
        return render_image_thumbnail(image, title='Логотип лейбла/издателя/производителя')

    label_thumbnail.short_description = 'Лого'

    def save_model(
        self,
        request: HttpRequest,
        obj: TbLabel,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
        """
        Переопределяем save_model для добавления информативных сообщений в админку.

        Максимально поджарый код - все сложности с получением старого значения
        и определением типа операции делает хелпер generate_admin_save_message().
        """
        # Стандартное сохранение записи через Django
        # (в т.ч. автоматическое создание связанной статьи в методе save модели TbLabel)
        super().save_model(request, obj, form, change)

        # Генерируем и отправляем информативное сообщение о сохранении
        # Хелпер сам:
        # - определяет тип операции (create vs update)
        # - формирует нужное сообщение (success vs warning)
        generate_admin_save_message(
            request=request,
            obj=obj,
            is_new=not change,  # Django: change=False для новых, True для существующих
            related_article=obj.k_label_to_article,
            obj_field_name='s_label',
            article_title_field='s_article_title',
        )


# ================
# АДМИН-ПАНЕЛЬ ДЛЯ ПРОДАВЦА/SELLER
#
# Кастомная форма
class SellerAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для админки продавца (Seller).
    Добавляет виджеты CodeMirror для текстовых полей
    """
    class Meta:
        model = TbSeller
        fields = ('id', 's_seller', 'l_seller_currency', 'k_seller_to_article', 'l_seller_type',
                  'j_seller_metadata',)

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror редактор
        """
        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('s_seller', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('j_seller_metadata', language='json',
                                    css_class='codemirror-width-xl codemirror-min-height-5')

# Админ для продавца (Seller)
class SellerAdmin(admin.ModelAdmin):
    """Админ для продавцов"""
    form = SellerAdminForm  # Используем кастомную форму с CodeMirror

    list_display = ('id', 'seller_thumbnail', 's_seller', 'l_seller_type', 'l_seller_currency', 't_seller_created',)
    list_display_links = ('id', 'seller_thumbnail', 's_seller',)
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
            'description': get_related_article_description(TbSeller),
            # 'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_seller_created', 't_seller_updated'),
            'classes': ('collapse',),
        }),
    )

    def seller_thumbnail(self, obj):
        """Миниатюра продавца через связанную статью."""
        article = obj.k_seller_to_article
        image = article.k_article_to_image if article else None
        return render_image_thumbnail(image, title='Логотип продавца')

    seller_thumbnail.short_description = 'Лого'

    # ВАЖНО. Так как продавцам не нужны синонимы, то CSS и JS для админки обогащать не нужно.
    def save_model(
        self,
        request: HttpRequest,
        obj: TbSeller,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
        """
        Переопределяем save_model для добавления информативных сообщений в админку.

        Максимально поджарый код - все сложности с получением старого значения
        и определением типа операции делает хелпер generate_admin_save_message().
        """
        # Стандартное сохранение записи через Django
        # (в т.ч. автоматическое создание связанной статьи в методе save модели TbSeller)
        super().save_model(request, obj, form, change)

        # Генерируем и отправляем информативное сообщение о сохранении
        # Хелпер сам:
        # - определяет тип операции (create vs update)
        # - формирует нужное сообщение (success vs warning)
        generate_admin_save_message(
            request=request,
            obj=obj,
            is_new=not change,  # Django: change=False для новых, True для существующих
            related_article=obj.k_seller_to_article,
            obj_field_name='s_seller',
            article_title_field='s_article_title',
        )



# ============================================================================
# АДМИНКА ИСТОЧНИКОВ ДАННЫХ
#
# Кастомная форма
class SourceAdminForm(CodeMirrorFormMixin):
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
        При инициализации формы подгружаем CodeMirror редактор
        """
        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('s_source_name', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('s_source_url', language='url',
                                    css_class='codemirror-width-xl codemirror-no-lines')
        self.setup_codemirror_field('j_source_metadata', language='json',
                                    css_class='codemirror-width-l codemirror-min-height-5')


class SourceAdmin(admin.ModelAdmin):
    """Админ для источников"""
    form = SourceAdminForm  # Используем кастомную форму с CodeMirror

    list_display = ('id', 's_source_name', 'k_source_to_seller', 'l_source_type', 't_source_data')
    list_display_links = ('id', 's_source_name',)
    list_filter = ('l_source_type', 't_source_data')
    search_fields = ('s_source_name',)
    readonly_fields = ('t_source_created', 't_source_updated')


# ============================================================================
# АДМИНКА РЕЛИЗОВ/АЛЬБОМОВ/ТОВАРОВ
#
# Кастомная форма
class ItemAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для админки источников данных (TbItem).
    Добавляет виджеты CodeMirror для текстовых полей
    """
    class Meta:
        model = TbItem
        fields = ('id', 's_item', 'k_item_to_artist', 'k_item_to_style', 'k_item_to_article',
                  's_item_date', 't_item_date', 'i_discogs_master_id', 'j_item_metadata')

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror редактор
        """
        # Извлекаем request из kwargs если он есть
        self.request = kwargs.pop('request', None)

        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('s_item', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('s_item_date', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('i_discogs_master_id', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('j_item_metadata', language='json',
                                    css_class='codemirror-width-l codemirror-min-height-5')


class ItemAdmin(RequestInFormMixin, admin.ModelAdmin):
    """Админ для товаров"""
    form = ItemAdminForm  # Используем кастомную форму с CodeMirror

    list_display = ('id', 'item_thumbnail', 's_item', 't_item_date', 't_item_created')
    list_display_links = ('id', 'item_thumbnail', 's_item',)
    list_filter = ('t_item_date', 't_item_created')
    search_fields = ('s_item',)
    filter_horizontal = ('k_item_to_artist', 'k_item_to_style')
    readonly_fields = ('t_item_created', 't_item_updated')

    def item_thumbnail(self, obj):
        """Миниатюра товара через связанную статью."""
        article = obj.k_item_to_article
        image = article.k_article_to_image if article else None
        return render_image_thumbnail(image, title='Обложка товара')

    item_thumbnail.short_description = 'Обложка'


# ============================================================================
# АДМИНКА СТАТЕЙ
#
# Статьи очень важная сущность сайта. Через них на сайте отпределяютя URL (slag), SEO-поля и "заголовочные" картинки
# многих сущностей (артистов, лейблов, музыкальных стилей и т.д.). Также тут опредлелентся, как на сайте  будут
# отображаться все эти сущности сверстанными в HTML.

# Кастомная форма
class ArticleAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для админки статей (TbArticle).
    Добавляет виджеты CodeMirror для текстовых полей.
    """
    # Виртуальные поля для настройки типографа
    etp_enable = forms.BooleanField(
        label="Включить типограф",
        initial=True,
        required=False,
        help_text="Включить автоматическую типографику для HTML полей (заголовок, тизер, контент)&nbsp;&nbsp;&nbsp;"
    )
    etp_language = forms.ChoiceField(
        label="Язык типографики",
        choices=[('ru', 'Русский'), ('en', 'English'), ('ru,en', 'Ru + En')],
        initial='ru',
        required=False
    )
    etp_quotes = forms.BooleanField(
        label="Кавычки",
        initial=True,
        required=False,
        help_text="Заменять кавычки<br/>(«ёлочки» для русского, “лапки” для английского)&nbsp;&nbsp;&nbsp;"
    )
    etp_hyphenation = forms.BooleanField(
        label="Расставлять переносы",
        initial=True,
        required=False,
        help_text="Расставлять мягкие переносы (&amp;shy;)&nbsp;&nbsp;&nbsp;<br/>"
                  "в словах длиннее <b>14</b> символов&nbsp;&nbsp;&nbsp;"
    )
    etp_sanitize = forms.BooleanField(
        label="Очистка HTML",
        initial=False,
        required=False,
        help_text="Удалять весь HTML из исходного текста&nbsp;&nbsp;&nbsp;"
    )
    etp_hanging_punctuation = forms.BooleanField(
        label="Висячая пунктуация",
        initial=False,
        required=False,
        help_text="Выносить пунктуацию в начало строк<br/>&nbsp;&nbsp;&nbsp;"
                  "(только для заголовков... для тизера и контента отключается автоматически)&nbsp;&nbsp;&nbsp;"
    )
    etp_mode = forms.ChoiceField(
        label="Режим вывода",
        choices=[('mixed', 'Смешанный (Mixed)'), ('unicode', 'Юникод (Unicode)'), ('mnemonic', 'Мнемоники')],
        initial='mixed',
        required=False,
        help_text="Формат спецсимволов (например, кавычек, тире, многоточий) в&nbsp;HTML: смешанный, юникод"
                  "&nbsp;или мнемоники&nbsp;&nbsp;&nbsp;"
    )

    class Meta:
        model = TbArticle
        fields = (
            # Виртуальные поля для настройки типографа
            'etp_enable', 'etp_language', 'etp_quotes', 'etp_hyphenation', 'etp_sanitize',
            'etp_hanging_punctuation', 'etp_mode',
            # Остальные поля модели TbArticle
            's_article_title', 'slug', 'l_article_type', 'b_article_published', 'k_article_to_image',
            's_article_title_html', 's_article_teaser_html', 's_article_content_html', 'seo_title',
            'seo_description', 'seo_keywords', 't_article_ended', 'i_article_views', 'i_article_favorites',
            'i_article_sort', 'j_article_metadata',
        )

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror редактор.
        Получаем request из kwargs, переданных из get_form_kwargs в AdminClass.
        """
        # Извлекаем request из kwargs если он есть
        self.request = kwargs.pop('request', None)
        
        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('s_article_title', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('slug', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('s_article_title_html', language='html',
                                    css_class='codemirror-width-l codemirror-min-height-2')
        self.setup_codemirror_field('s_article_teaser_html', language='html',
                                    css_class='codemirror-width-xl codemirror-min-height-5')
        self.setup_codemirror_field('s_article_content_html', language='html',
                                    css_class='codemirror-width-xl codemirror-min-height-10')
        self.setup_codemirror_field('seo_title', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('seo_description', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines codemirror-min-height-2')
        self.setup_codemirror_field('seo_keywords', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines codemirror-min-height-2')
        self.setup_codemirror_field('i_article_views', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('i_article_favorites', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('i_article_sort', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('j_article_metadata', language='json',
                                    css_class='codemirror-width-xl codemirror-min-height-5')

    def clean(self):
        """
        Валидируем форму: при редактировании проверяем изменился ли s_article_title_html
        и может ли измениться slug. Если да — показываем красную кнопку подтверждения.
        Используем GET параметр ignore_validate для пропуска при переотправке.
        """
        cleaned_data = super().clean()
        
        # Проверяем только при редактировании и не установлен ignore_validate
        if self.instance.pk and self.request and not self.request.GET.get('ignore_validate'):
            # Получаем старый объект из БД
            old_obj = TbArticle.objects.get(pk=self.instance.pk)
            
            if old_obj.s_article_title_html != cleaned_data.get('s_article_title_html'):
                # Заголовок изменился, проверяем, нужно ли менять slug
                title_source = cleaned_data.get('s_article_title_html') or cleaned_data.get('s_article_title') or ''
                new_potential_slug = make_slug(title_source)
                
                # Если новый slug не совпадает с началом текущего...
                if not self.instance.slug.startswith(new_potential_slug):
                    # ...предлагаем изменить slug
                    error_html = (
                        '<div class="confirmation-button-container">'
                        '  <big>Ой! Кажется, вы изменили заголовок статьи!</big><br/>'
                        f' Текущий slug: <b><tt><u>{self.instance.slug}</u></tt></b><br/>'
                        f' Для измененного заголовка «<tt><i><u>{cleaned_data.get('s_article_title_html')}</u></i></tt>»'
                        f' лучше сделать slug <b><tt><u>{new_potential_slug}</u></tt></b><br/><br/>'
                        '  Пожалуйста, проверьте, что это правильно. Если вы уверены — нажмите подтверждение.<br><br/>'
                        '  <button type="button" onclick="markSubmitButtonsToIgnoreValidation();">'
                        '    ✓ Я ПРОВЕРИЛ И УВЕРЕН!'
                        '  </button><br/>&nbsp;'
                        '</div>'
                    )
                    raise ValidationError(mark_safe(error_html))

        return cleaned_data

class ArticleAdmin(RequestInFormMixin, admin.ModelAdmin):
    """Админ для статей с поддержкой передачи request в форму"""
    form = ArticleAdminForm  # Используем кастомную форму с CodeMirror

    list_display = ('id', 'article_thumbnail', 's_article_title', 'l_article_type', 'i_article_sort',
                    'b_article_published', 't_article_created')
    list_display_links = ('id', 'article_thumbnail', 's_article_title',)
    list_filter = ('l_article_type', 'b_article_published', 't_article_created')
    search_fields = ('s_article_title', 'slug')
    prepopulated_fields = {'slug': ('s_article_title',)}
    readonly_fields = ('t_article_created', 't_article_updated')
    # filter_horizontal = ('k_article_to_styles',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('s_article_title', 'slug', 'l_article_type', 'b_article_published', 'i_article_sort',),
        }),
        ('Изображение', {
            'fields': ('k_article_to_image',),
            'description': 'Обложка или иллюстрация статьи. Используется в списках и на странице статьи.',
        }),
        ('Окончание публикации', {
            'fields': ('t_article_ended',),
            'classes': ('collapse',),
        }),
        ('Типограф', {
            'fields': (('etp_enable',), ('etp_language', 'etp_mode'), ('etp_quotes', 'etp_hyphenation', 'etp_sanitize', 'etp_hanging_punctuation')),
            'classes': ('collapse',),
            'description': 'Типограф применяется при сохранении и срабатывает на HTML-поля (ЗАГОЛОВОК, ТИЗЕР СТАТЬИ'
                           ' и СТАТЬЯ). Если выключить — HTML будет сохранен без изменений.',
        }),
        ('Содержание', {
            'fields': ('s_article_title_html', 's_article_teaser_html', 's_article_content_html'),
        }),
        ('Просмотры и избранное', {
            'fields': ('i_article_views', 'i_article_favorites',),
            'classes': ('collapse',),
        }),
        ('Метаданные и SEO', {
            'fields': ('j_article_metadata', 'seo_title', 'seo_description', 'seo_keywords'),
            'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_article_created', 't_article_updated'),
            'classes': ('collapse',),
        }),
    )

    # Подключаем CSS и JS для валидации
    # Переиспользуем стили и скрипты из админок Label/MusicStyle
    class Media(ArticleAdminForm.Media):
        css = {'all': (*ArticleAdminForm.Media.css['all'], 'css/validation-override.css', )}
        js = (*ArticleAdminForm.Media.js, 'js/form-field-watcher.js', )

    def article_thumbnail(self, obj):
        """
        Отображает миниатюру изображения статьи (40x40) в списке.
        Использует universal helper render_image_thumbnail().
        """
        return render_image_thumbnail(obj.k_article_to_image if obj else None, title='Обложка')

    article_thumbnail.short_description = 'img'

    def save_model(self, request, obj, form, change):
        """
        Переопределяем save_model для применения типографа.
        Username используется в TbArticle.save() для установки IMG_FROM в метаданные картинки.

        Args:
            request: HTTP-запрос (содержит info о пользователе)
            obj: инстанция TbArticle для сохранения
            form: валидированная форма
            change: True если редактирование, False если создание
        """
        # Типографика для HTML-полей (s_article_title_html, s_article_teaser_html, s_article_content_html)
        
        # Проверяем, включен ли типограф
        if form.cleaned_data.get('etp_enable', True):
            # Получаем все настройки из формы
            langs = form.cleaned_data.get('etp_language', 'ru').split(',')
            
            # 1. LayoutProcessor: включаем layout с базовыми настройками
            layout_option = etpgrf.LayoutProcessor(
                langs=langs,
                process_initials_and_acronyms=True,
                process_units=True
            )

            # 2. Hyphenator (переносы слов)
            hyphenation_option = False
            if form.cleaned_data.get('etp_hyphenation', True):
                hyphenation_option = etpgrf.Hyphenator(
                    langs=langs,
                    max_unhyphenated_len=14
                )

            # 3. Sanitizer (очистка HTML перед типографированием)
            # Режимы: 'html' (удаляет все теги), 'etp' (только висячая пунктуация), None/False (ничего не делает)
            if form.cleaned_data.get('etp_sanitize', True):
                sanitizer_option = 'html'  # Удаляет все HTML-теги
            else:
                sanitizer_option = False  # Санитайзер отключен

            # 4. Базовые настройки типографа (используются для всех полей)
            base_options = {
                'langs': langs,
                'process_html': True,
                'quotes': form.cleaned_data.get('etp_quotes', True),
                'layout': layout_option,
                'unbreakables': True,
                'hyphenation': hyphenation_option,
                'sanitizer': sanitizer_option,
                'symbols': True,
                'mode': form.cleaned_data.get('etp_mode', 'mixed'),
            }

            # 5. Для заголовков: висячая пунктуация может быть включена
            options_title = {
                **base_options,
                'hanging_punctuation': form.cleaned_data.get('etp_hanging_punctuation', True),
            }
            t_title = etpgrf.Typographer(**options_title)
            if obj.s_article_title_html:
                obj.s_article_title_html = t_title.process(obj.s_article_title_html)

            # 6. Для тизера и контента: висячая пунктуация всегда отключена
            options_body = {
                **base_options,
                'hanging_punctuation': False,
            }
            t_body = etpgrf.Typographer(**options_body)
            if obj.s_article_teaser_html:
                obj.s_article_teaser_html = t_body.process(obj.s_article_teaser_html)
            if obj.s_article_content_html:
                obj.s_article_content_html = t_body.process(obj.s_article_content_html)

        # Сохраняем username текущего пользователя для передачи в TbArticle.save() для IMG_FROM
        if request and request.user:
            obj._admin_username = request.user.username

        # Вызываем родительский save_model который вызовет obj.save()
        super().save_model(request, obj, form, change)


# ============================================================================
# АДМИНКА КОММЕРЧЕСКИХ ПРЕДЛОЖЕНИЙ (ОФФЕРОВ)
#
# Статьи очень важная сущность сайта. Через них на сайте отпределяютя URL (slag), SEO-поля и "заголовочные" картинки
# многих сущностей (артистов, лейблов, музыкальных стилей и т.д.). Также тут опредлелентся, как на сайте  будут
# отображаться все эти сущности сверстанными в HTML.

# Кастомная форма
class OfferAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для админки коммерческих предложений (TbOffer).
    Добавляет виджеты CodeMirror для текстовых полей
    """
    class Meta:
        model = TbOffer
        fields = (
            's_offer', 'l_offer_to_format', 'k_offer_to_article', 'k_offer_to_item', 'k_offer_to_label',
            'k_offer_to_source', 's_offer_catalog_num', 'b_offer_is_preorder', 'd_offer_date_release',
            'i_offer_discogs_id', 'l_offer_condition_media', 'l_offer_condition_sleeve', 'f_offer_price',
            'i_offer_quantity', 'i_offer_discount_to_daily_sale', 'j_offer_metadata', 'i_offer_views',
            'i_offer_favorites',
        )

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror редактор.
        Получаем request из kwargs, переданных из get_form_kwargs в AdminClass.
        """
        # Извлекаем request из kwargs если он есть
        self.request = kwargs.pop('request', None)

        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('s_offer', language='text',
                                    css_class='codemirror-width-l codemirror-no-lines')
        self.setup_codemirror_field('f_offer_price', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('i_offer_quantity', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('j_offer_metadata', language='json',
                                    css_class='codemirror-width-l codemirror-min-height-5')
        self.setup_codemirror_field('i_offer_views', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('i_offer_favorites', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('s_offer_catalog_num', language='text',
                                    css_class='codemirror-width-m codemirror-no-lines')
        self.setup_codemirror_field('i_offer_discogs_id', language='text',
                                    css_class='codemirror-width-m codemirror-no-lines')
        self.setup_codemirror_field('i_offer_discount_to_daily_sale', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')

# ============================================================================
# АДМИНКА ОФФЕРОВ (OfferAdminForm, OfferImageInlineForm, OfferAdmin)
# ============================================================================

class OfferImageInlineForm(CodeMirrorFormMixin):
    """Форма для inline картинок с CodeMirror стилями"""
    class Meta:
        model = TbImageMetadata
        fields = ('image', 'i_img_sort')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Стилизуем i_img_sort в стиле CodeMirror (как число, компактное)
        self.setup_codemirror_field('i_img_sort', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')

class OfferAdmin(RequestInFormMixin, admin.ModelAdmin):
    """Админ для предложений с поддержкой передачи request в форму"""
    form = OfferAdminForm  # Используем кастомную форму с CodeMirror

    
    class OfferImageInline(admin.TabularInline):
        """
        Inline для управления картинками оффера.
        
        Позволяет добавлять, редактировать и удалять картинки через:
        - FilerImageField для красивого выбора
        - i_img_sort для сортировки
        """
        model = TbImageMetadata
        form = OfferImageInlineForm
        fk_name = 'm_offer'
        extra = 1  # одна пустая строка для добавления новой картинки
        fields = ('image', 'i_img_sort')
        ordering = ('i_img_sort',)
        verbose_name = 'Изображения и метаданные-изображений коммерческого предложения'
        verbose_name_plural = 'Изображения и метаданные-изображений коммерческих предложений'
    
    list_display = ('id', 'offer_thumbnail', 's_offer', 'k_offer_to_item', 'f_offer_price', 'i_offer_quantity', 'i_offer_views')
    list_display_links = ('id', 'offer_thumbnail', 's_offer',)
    list_filter = ('l_offer_condition_media', 'l_offer_condition_sleeve', 't_offer_created', 'l_offer_to_format')
    search_fields = ('s_offer',)
    inlines = [OfferImageInline]  # Управление картинками в inline
    readonly_fields = ('s_offer_code', 't_offer_created', 't_offer_updated',)
    
    def offer_thumbnail(self, obj):
        """
        Отображает миниатюру первой картинки оффера (по i_img_sort) в списке.
        Использует universal helper render_image_thumbnail().
        """
        first_meta = obj.m_image.first()
        image = first_meta.image if first_meta else None
        return render_image_thumbnail(image, title='Первая картинка оффера')
    
    offer_thumbnail.short_description = '1\'st img'
    
    fieldsets = (
        ('Код товара в базе', {
            'fields': ('s_offer_code',),
            'description': 'Уникальный код товара в базе. Используется вместо ID для генерации ссылок на оффер'
                           ' и складского учёта с помощью QR-кодов. Не редактируется вручную.',
        }),
        ('Основная информация', {
            'fields': ('k_offer_to_item', 's_offer', 'f_offer_price', 'i_offer_quantity'),
        }),
        ('Дата релиза и метка если доступно только по предзаказу', {
            'fields': ('d_offer_date_release', 'b_offer_is_preorder',),
            'classes': ('collapse',),
        }),
        ('Дополнительные данные', {
            'fields': (
                'l_offer_to_format', 'l_offer_condition_media', 'l_offer_condition_sleeve', 'k_offer_to_article',
                'k_offer_to_label', 'k_offer_to_source', 's_offer_catalog_num', 'i_offer_discogs_id',
                'i_offer_discount_to_daily_sale',
            ),
        }),
        ('Метаданные коммерческого предложения', {
            'fields': ('j_offer_metadata',),
            'classes': ('collapse',),
            'description': 'Метаданные коммерческого предложения в формате JSON. '
                           'Используется для хранения дополнительных данных, которые не входят в основные поля модели.',
        }),
        ('Просмотры и избранное', {
            'fields': ('i_offer_views', 'i_offer_favorites',),
            'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_offer_created', 't_offer_updated'),
            'classes': ('collapse',),
        }),
    )





# ============================================================================
# АДМИНКА ИСТОРИИ ИЗМЕНЕНИЙ ОФФЕРОВ (история цен и остатков коммерческих предложений)
#
# Кастомная форма
class OfferHistoryAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для админки коммерческих предложений (TbOffer).
    Добавляет виджеты CodeMirror для текстовых полей
    """
    class Meta:
        model = TbOfferHistory
        fields = ('k_history_to_offer','f_history_price', 'i_history_quantity', 'j_history_metadata',
                  't_history_created')

    def __init__(self, *args, **kwargs):
        """
        При инициализации формы подгружаем CodeMirror редактор.
        """
        super().__init__(*args, **kwargs)

        # Конфигурируем поля для CodeMirror
        self.setup_codemirror_field('f_history_price', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('i_history_quantity', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('j_history_metadata', language='json',
                                    css_class='codemirror-width-l codemirror-min-height-5')

class OfferHistoryAdmin(admin.ModelAdmin):
    """Админ для истории изменений офферов"""
    form = OfferHistoryAdminForm  # Используем кастомную форму с CodeMirror
    list_display = ('id', 'k_history_to_offer', 'f_history_price', 'i_history_quantity', 't_history_created')
    list_display_links = ('id', 'k_history_to_offer',)
    list_filter = ('t_history_created',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('k_history_to_offer', 'f_history_price', 'i_history_quantity', ),
        }),
        ('Метаданные истории изменений', {
            'fields': ('j_history_metadata',),
        }),
        ('Служебная информация (но редактируемое, для загрузки исторических данных)', {
            'fields': ('t_history_created',),
            'classes': ('collapse',),
        }),
    )


# ============================================================================
# Регистрация моделей в дефолтном admin.site
# ============================================================================
admin.site.register(TbImageMetadata, ImageMetadataAdmin)
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

