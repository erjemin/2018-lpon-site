import os
import logging
from io import BytesIO
from django.apps import AppConfig
from django.core.files.base import ContentFile
from django.db.models.signals import pre_save
from PIL import Image as PILImage
import pillow_heif

from lpon_site.settings import (
    THUMBNAIL_WEBP_QUALITY,
    FILER_ENABLE_PERMISSIONS,
    FILER_UPLOADER_MAX_FILE_SIZE,
    FILER_WHITELIST_FOR_PATH_ACCESS,
    MIME_TYPE_WHITELIST,
    FILE_VALIDATORS,
)

# Регистрируем плагин HEIF в Pillow
pillow_heif.register_heif_opener()

# Получаем логгер для текущего модуля
logger = logging.getLogger(__name__)

# Кэш для размеров изображений больше не нужен!
# Filer сам распознает WebP по mime_type и создаст Image запись
# PIL автоматически получит размеры из WebP файла


# ==============================================================================
# Конфигурация приложения для фронтенда lpon
# ==============================================================================
class FrontendConfig(AppConfig):
    name = 'frontend'
    verbose_name = 'Сайт lpon.ru'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        from django.contrib import admin
        admin.site.site_header = 'Управление LPON'
        admin.site.site_title = 'LPON Administrator'
        admin.site.index_title = 'Добро пожаловать в LPON'

# ==============================================================================
# Кастомная конфигурация для django-filer
# - Патчинг MultiStorageFieldFile.save() для автоматической конвертации в WebP
# ==============================================================================
class CustomFilerConfig(AppConfig):
    name = 'filer'
    verbose_name = 'Медиафайлы'

    # ========================================================================
    # Атрибуты конфигурации Django-Filer (импортированы из settings.py)
    # ========================================================================
    FILER_ENABLE_PERMISSIONS = FILER_ENABLE_PERMISSIONS
    FILER_UPLOADER_MAX_FILE_SIZE = FILER_UPLOADER_MAX_FILE_SIZE
    FILER_WHITELIST_FOR_PATH_ACCESS = FILER_WHITELIST_FOR_PATH_ACCESS
    MIME_TYPE_WHITELIST = MIME_TYPE_WHITELIST
    FILE_VALIDATORS = FILE_VALIDATORS


    @staticmethod
    def _convert_to_webp_if_needed(name: str, content):
        """
        Преобразует загруженное изображение в WebP формат.
        Поддерживает JPEG, PNG, BMP, TIFF и HEIC/HEIF.

        Возвращает кортеж: (content, new_name, was_converted, image_width, image_height)

        КРИТИЧНО: Функция ДОЛЖНА получать размеры из УЖЕ ПРЕОБРАЗОВАННОГО WebP файла, а не из исходника!
        Почему:
        - PIL может открыть HEIC (благодаря pillow_heif) но размеры исходного могут отличаться
        - После конвертации HEIC→WebP размеры могут измениться (масштабирование, кроппинг)
        - Filer использует размеры для определения каких миниатюр генерировать
        - Размеры ДОЛЖНЫ совпадать с реальным WebP файлом в хранилище!
        """
        _, original_ext = os.path.splitext(name)
        image_width = None
        image_height = None

        # Список расширений, которые конвертируем в WebP
        convertible_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".heic", ".heif"]

        if original_ext.lower() in convertible_extensions:
            try:
                # Шаг 1: Открываем исходный файл с помощью PIL (поддерживает HEIC благодаря pillow_heif)
                content.seek(0)
                img = PILImage.open(BytesIO(content.read()))
                logger.debug(f"Открыт файл '{name}' с расширением '{original_ext}'. Размер: {img.size}")

                # Шаг 2: Конвертируем CMYK в RGB если требуется (WebP не поддерживает CMYK)
                if img.mode == 'CMYK':
                    img = img.convert('RGB')
                    logger.debug("Конвертировано CMYK → RGB")

                # Шаг 3: Сохраняем исходное изображение в WebP формат в памяти (BytesIO)
                webp_buffer = BytesIO()
                img.save(webp_buffer, format="WEBP", quality=THUMBNAIL_WEBP_QUALITY)
                webp_buffer.seek(0)
                logger.debug(f"Изображение конвертировано в WebP (качество={THUMBNAIL_WEBP_QUALITY})")

                # Шаг 4: КРИТИЧНО - Переоткрываем WebP из памяти и получаем его РЕАЛЬНЫЕ размеры
                # Это гарантирует что размеры совпадают с тем что РЕАЛЬНО будет сохранено в хранилище!
                webp_buffer.seek(0)
                webp_img = PILImage.open(BytesIO(webp_buffer.read()))
                image_width, image_height = webp_img.size
                logger.info(f"Получены размеры CONVERTED WebP: {image_width}x{image_height}px")

                # Шаг 5: Возвращаем WebP контент в начало буфера для последующего сохранения
                webp_buffer.seek(0)

                # Шаг 6: Изменяем расширение на .webp
                new_name = os.path.splitext(name)[0] + ".webp"
                logger.info(f"Конвертировано '{name}' → '{new_name}' (WebP). "
                           f"Размеры: {image_width}x{image_height}px")

                # Возвращаем WebP контент и размеры из уже преобразованного файла
                return ContentFile(webp_buffer.read()), new_name, True, image_width, image_height

            except Exception:
                logger.error(f"Ошибка при конвертации '{name}' в WebP.", exc_info=True)
                # При ошибке возвращаем исходный файл без размеров
                content.seek(0)
                return content, name, False, None, None

        # Если файл не нуждается в конвертации, возвращаем как есть
        content.seek(0)
        return content, name, False, None, None

    def ready(self):
        """
        Готовимся к работе: патчим MultiStorageFieldFile.save() для WebP конвертации.
        """
        # КРИТИЧЕСКИ ВАЖНО: Переопределяем IMAGE_EXTENSIONS и IMAGE_MIME_TYPES в filer
        # Это гарантирует что filer распознает WebP файлы как изображения, а не как обычные файлы
        #
        # Почему это нужно делать здесь в apps.py:
        # - IMAGE_EXTENSIONS и IMAGE_MIME_TYPES в filer это ГЛОБАЛЬНЫЕ КОНСТАНТЫ (не getattr настройки)
        # - Они импортируются как: from filer.settings import IMAGE_EXTENSIONS
        # - Нет встроенного механизма для переопределения через settings.py
        # - Единственный способ - модифицировать их после импорта, в ready() методе AppConfig
        #
        # Это стандартная практика для переопределения внутренних настроек третьих пакетов в Django
        from filer import settings as filer_settings

        # Добавляем WebP и HEIC/HEIF расширения к списку расширений изображений
        if '.webp' not in filer_settings.IMAGE_EXTENSIONS:
            filer_settings.IMAGE_EXTENSIONS = list(filer_settings.IMAGE_EXTENSIONS) + ['.webp']
        if '.heic' not in filer_settings.IMAGE_EXTENSIONS:
            filer_settings.IMAGE_EXTENSIONS = list(filer_settings.IMAGE_EXTENSIONS) + ['.heic']
        if '.heif' not in filer_settings.IMAGE_EXTENSIONS:
            filer_settings.IMAGE_EXTENSIONS = list(filer_settings.IMAGE_EXTENSIONS) + ['.heif']

        # Добавляем WebP и HEIC/HEIF mime-типы
        if 'webp' not in filer_settings.IMAGE_MIME_TYPES:
            filer_settings.IMAGE_MIME_TYPES = list(filer_settings.IMAGE_MIME_TYPES) + ['webp']
        if 'heic' not in filer_settings.IMAGE_MIME_TYPES:
            filer_settings.IMAGE_MIME_TYPES = list(filer_settings.IMAGE_MIME_TYPES) + ['heic']
        if 'heif' not in filer_settings.IMAGE_MIME_TYPES:
            filer_settings.IMAGE_MIME_TYPES = list(filer_settings.IMAGE_MIME_TYPES) + ['heif']

        logger.info(f"Обновлены filer IMAGE_EXTENSIONS: {filer_settings.IMAGE_EXTENSIONS}")
        logger.info(f"Обновлены filer IMAGE_MIME_TYPES: {filer_settings.IMAGE_MIME_TYPES}")

        from filer.fields.multistorage_file import MultiStorageFieldFile

        logger.info("Patching MultiStorageFieldFile.save() for WebP conversion...")
        original_save = MultiStorageFieldFile.save

        def patched_save(self_instance, name, content, save=True):
             """
             Патчированная версия MultiStorageFieldFile.save() для конвертации HEIC/HEIF в WebP.

             Процесс:
             1. Конвертирует загруженное изображение в WebP (JPEG, PNG, BMP, TIFF, HEIC, HEIF)
             2. Устанавливает правильный mime_type=image/webp
             3. Вызывает оригинальный save() с преобразованным контентом
             4. Filer автоматически распознает WebP как Image, читает размеры и создает Image запись
             """
             # Шаг 1: Преобразуем загруженный файл в WebP если требуется
             # Метод вернет размеры ИЗ ПРЕОБРАЗОВАННОГО WebP (не исходного файла)
             new_content, new_name, converted, img_width, img_height = CustomFilerConfig._convert_to_webp_if_needed(name, content)

             # Шаг 2: Если файл был конвертирован в WebP, обновляем метаданные
             if converted:
                 # Важно: Устанавливаем mime_type ПЕРЕД сохранением
                 # Filer использует mime_type чтобы определить тип файла (Image vs File)
                 self_instance.instance.mime_type = "image/webp"
                 logger.info(f"[WebP] Конвертировано '{name}' → '{new_name}'. "
                           f"Size: {img_width}x{img_height}px, mime_type=image/webp")

                 # Обновляем original_filename если есть
                 if hasattr(self_instance.instance, 'original_filename') and self_instance.instance.original_filename:
                     original_filename, _ = os.path.splitext(self_instance.instance.original_filename)
                     self_instance.instance.original_filename = f"{original_filename}.webp"

             # Шаг 3: Вызываем оригинальный save() метод с new_name и new_content
             result = original_save(self_instance, new_name, new_content, save)

             # Шаг 4: После original_save() гарантируем что mime_type=image/webp сохранен в БД
             # (на случай если решение о типе файла уже было принято)
             if converted and new_name.lower().endswith('.webp'):
                 # Если instance имеет id после save, обновляем mime_type в БД
                 if self_instance.instance.id:
                      # Обновляем только mime_type
                     self_instance.instance.__class__.objects.filter(id=self_instance.instance.id).update(
                        mime_type='image/webp'
                     )
                     logger.info(f"[WebP] Updated mime_type in DB for id={self_instance.instance.id}")

             return result

        MultiStorageFieldFile.save = patched_save
        logger.info("MultiStorageFieldFile.save() patched successfully.")
        logger.info("Все остальное сделает filer - он распознает image/webp по mime_type и создаст Image запись!")

        # Регистрируем pre_save сигнал для изменения mime_type HEIC/HEIF файлов ДО их сохранения
        # Это гарантирует что filer распознает их как Image, а не как File
        from filer.models import File as FilerFile

        def fix_heic_mime_type_before_save(sender, instance, **kwargs):
            """
            Перехватывает HEIC/HEIF файлы ДО сохранения и восстанавливает mime_type='image/webp'.

            Проблема: Браузер отправляет mime_type='image/heic' для HEIC файлов.
            Filer видит расширение/имя и может неправильно определить тип.
            Решение: Устанавливаем mime_type='image/webp' ДО сохранения.
            Это гарантирует что filer распознает как Image, а не как File.
            """
            if instance.file and hasattr(instance.file, 'name'):
                file_name = instance.file.name.lower() if instance.file.name else ""

                # Если это WebP файл или конвертированный HEIC/HEIF, устанавливаем правильный mime_type
                if file_name.endswith('.webp') or file_name.endswith('.heic') or file_name.endswith('.heif'):
                    old_mime = instance.mime_type
                    instance.mime_type = 'image/webp'
                    logger.info(f"[PRE-SAVE] Fixed mime_type for {file_name}: '{old_mime}' → 'image/webp'")

        pre_save.connect(fix_heic_mime_type_before_save, sender=FilerFile, dispatch_uid="fix_heic_mime_before_save")
        logger.info("Pre-save signal handler for HEIC mime_type fixing registered.")

