# Кастомная конфигурация Django Admin для LPON сайта.
# Регистрируем модели с удобным интерфейсом.

from typing import Any
from django import forms
from django.forms import Textarea
from django.http import HttpRequest
from django.contrib import admin
from django.utils.html import format_html, mark_safe
from easy_thumbnails.files import get_thumbnailer
from .models import (
    TbImage, TbArticle, TbArtist, TbItem, TbLabel, TbSeller,
    TbOffer, TbSource, TbOfferHistory, TbMusicStyle
)
from .utils_validators import validate_entity_for_admin_form, generate_admin_save_message


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
# АДМИНИСТРИРОВАНИЕ TbImage
#
# Кастомня форма для админки TbImage
class TbImageAdminForm(CodeMirrorFormMixin):
    """
    Кастомная форма для TbImage в админке.
    Добавляет виртуальные поля для редактирования метаданных filer_image
    (default_alt_text и default_caption), которые не хранятся в TbImage, но есть в filer_image.
    
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
        model = TbImage
        fields = ('image', 'l_img_source', 'l_img_reality', 's_img_src_url', 'i_img_sort', 'f_img_confidence_score')

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
        self.setup_codemirror_field('s_img_src_url', language='url',
                                    css_class='codemirror-width-xl codemirror-no-lines')
        self.setup_codemirror_field('i_img_sort', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')
        self.setup_codemirror_field('f_img_confidence_score', language='text',
                                    css_class='codemirror-width-s codemirror-no-lines')


# Админка для TbImage с кастомной формой
class ImageAdmin(admin.ModelAdmin):
    """
    Админ для изображений TbImage с поддержкой редактирования метаданных filer_image.

    Позволяет пользователю заполнить default_alt_text и default_caption для картинки в filer
    прямо в админке TbImage, без необходимости отдельного редактирования filer.
    
    Использует TbImageAdminForm с наследованием от CodeMirrorFormMixin для поддержки CodeMirror.
    """
    form = TbImageAdminForm  # Используем кастомную форму с виртуальными полями (Media подключится через миксин)

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

    def save_model(
        self,
        request: HttpRequest,
        obj: TbImage,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
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

    list_display = ('id', 's_style_name', 'j_style_metadata', 't_style_created', 't_style_updated',)
    list_display_links = ('id', 's_style_name',)
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
    # Это гарантирует что все CSS/JS из формы будут загружены
    class Media(LabelAdminForm.Media):
        css = {'all': (*LabelAdminForm.Media.css['all'], 'css/validation-override.css', )}
        js = (*LabelAdminForm.Media.js, 'js/form-field-watcher.js', )

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
            'description': get_related_article_description(TbSeller),
            # 'classes': ('collapse',),
        }),
        ('Служебная информация', {
            'fields': ('t_seller_created', 't_seller_updated'),
            'classes': ('collapse',),
        }),
    )

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

#
class SourceAdmin(admin.ModelAdmin):
    """Админ для источников"""
    form = SourceAdminForm  # Используем кастомную форму с CodeMirror

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

