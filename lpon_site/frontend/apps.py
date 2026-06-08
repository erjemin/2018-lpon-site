import os
import hashlib
import logging
from io import BytesIO
from django.apps import AppConfig
from django.core.files.base import ContentFile
from PIL import Image as PILImage

from lpon_site.settings import (
    THUMBNAIL_WEBP_QUALITY,
    FILER_ENABLE_PERMISSIONS,
    FILER_UPLOADER_MAX_FILE_SIZE,
    FILER_WHITELIST_FOR_PATH_ACCESS,
    MIME_TYPE_WHITELIST,
    FILE_VALIDATORS,
)

# Получаем логгер для текущего модуля
logger = logging.getLogger(__name__)


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
#
# Все параметры конфигурации (MIME_TYPE_WHITELIST, FILER_WHITELIST_FOR_PATH_ACCESS и т.д.)
# определены в settings.py и импортируются оттуда.
# Удаление префикса filer_public_thumbnails/ достигается через THUMBNAIL_OPTIONS в settings.py
# ==============================================================================
class CustomFilerConfig(AppConfig):
    name = 'filer'
    verbose_name = 'Медиафайлы'

    # ========================================================================
    # Атрибуты конфигурации Django-Filer (импортированы из settings.py)
    # Единое место правды - settings.py
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
        Поддерживает JPEG, PNG, BMP и TIFF.
        """
        _, original_ext = os.path.splitext(name)
        if original_ext.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            try:
                content.seek(0)
                img = PILImage.open(BytesIO(content.read()))
                if img.mode == 'CMYK':
                    img = img.convert('RGB')
                buffer = BytesIO()
                img.save(buffer, format="WEBP", quality=THUMBNAIL_WEBP_QUALITY)
                buffer.seek(0)
                new_name = os.path.splitext(name)[0] + ".webp"
                logger.info(f"Successfully converted '{name}' to '{new_name}' (WebP).")
                return ContentFile(buffer.read()), new_name, True
            except Exception:
                logger.error(f"Error converting '{name}' to WebP.", exc_info=True)
                content.seek(0)
                return content, name, False
        content.seek(0)
        return content, name, False

    def ready(self):
        """
        Готовимся к работе: патчим MultiStorageFieldFile.save() для WebP конвертации.
        """
        from filer.fields.multistorage_file import MultiStorageFieldFile

        logger.info("Patching MultiStorageFieldFile.save() for WebP conversion...")
        original_save = MultiStorageFieldFile.save

        def patched_save(self_instance, name, content, save=True):
            # Преобразуем загруженный файл в WebP если требуется
            new_content, new_name, converted = CustomFilerConfig._convert_to_webp_if_needed(name, content)
            if converted:
                # Обновляем свойства файла для WebP версии
                self_instance.instance.mime_type = "image/webp"
                if hasattr(self_instance.instance, 'original_filename') and self_instance.instance.original_filename:
                    original_filename, _ = os.path.splitext(self_instance.instance.original_filename)
                    self_instance.instance.original_filename = f"{original_filename}.webp"
                # Сохраняем размер и контрольную сумму WebP файла
                new_content.seek(0)
                file_bytes = new_content.read()
                new_content.seek(0)
                self_instance.instance._file_size = len(file_bytes)
                self_instance.instance.sha1 = hashlib.sha1(file_bytes).hexdigest()

            return original_save(self_instance, new_name, new_content, save)

        MultiStorageFieldFile.save = patched_save
        logger.info("MultiStorageFieldFile.save() patched successfully.")

