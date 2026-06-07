import os
import hashlib
import logging
from io import BytesIO
from django.apps import AppConfig
from django.core.files.base import ContentFile
from PIL import Image as PILImage

from lpon_site.settings import DEBUG, THUMBNAIL_WEBP_QUALITY

# Получаем логгер для текущего модуля
logger = logging.getLogger(__name__)


class FrontendConfig(AppConfig):
    name = 'frontend'
    verbose_name = 'Сайт lpon.ru'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        from django.contrib import admin
        admin.site.site_header = 'Управление LPON'
        admin.site.site_title = 'LPON Administrator'
        admin.site.index_title = 'Добро пожаловать в LPON'


class CustomFilerConfig(AppConfig):
    name = 'filer'
    verbose_name = 'Медиафайлы'

    # ========================================================================
    # Конфигурация Django-Filer, которая читается во время выполнения
    # ========================================================================
    FILER_ENABLE_PERMISSIONS = DEBUG
    FILER_MAX_UPLOAD_SIZE = 100 * 1024 * 1024
    FILER_WHITELIST_FOR_PATH_ACCESS = (
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',
        '.doc', '.docx', '.pdf', '.txt', '.xls', '.xlsx', '.csv',
    )
    MIME_TYPE_WHITELIST = (
        'image/jpeg', 'image/png', 'image/gif', 'image/svg+xml', 'image/webp',
        'application/pdf', 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain', 'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/csv',
    )
    FILE_VALIDATORS = {}

    @staticmethod
    def _convert_to_webp_if_needed(name: str, content):
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
        from filer.fields.multistorage_file import MultiStorageFieldFile

        logger.info("Patching MultiStorageFieldFile.save() for WebP conversion...")
        original_save = MultiStorageFieldFile.save

        def patched_save(self_instance, name, content, save=True):
            new_content, new_name, converted = CustomFilerConfig._convert_to_webp_if_needed(name, content)
            if converted:
                self_instance.instance.mime_type = "image/webp"
                if hasattr(self_instance.instance, 'original_filename') and self_instance.instance.original_filename:
                    original_filename, _ = os.path.splitext(self_instance.instance.original_filename)
                    self_instance.instance.original_filename = f"{original_filename}.webp"
                new_content.seek(0)
                file_bytes = new_content.read()
                new_content.seek(0)
                self_instance.instance._file_size = len(file_bytes)
                self_instance.instance.sha1 = hashlib.sha1(file_bytes).hexdigest()
            
            return original_save(self_instance, new_name, new_content, save)

        MultiStorageFieldFile.save = patched_save
        logger.info("MultiStorageFieldFile.save() patched successfully.")
