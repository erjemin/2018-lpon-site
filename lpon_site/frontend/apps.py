import os
import hashlib
import logging
from io import BytesIO
from typing import Tuple

from django.apps import AppConfig
from django.core.files.base import ContentFile, File
from django.core.exceptions import ValidationError
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

# Регистрируем плагин HEIF в Pillow для поддержки HEIC/HEIF файлов
pillow_heif.register_heif_opener()

# Настройка параллельного декодирования HEIF/HEIC файлов
# DECODE_THREADS: количество потоков для декодирования
# - 0 = использовать количество ядер процессора (рекомендуется)
# - N > 0 = использовать N потоков (больше потоков = быстрее, но больше памяти)
pillow_heif.options.DECODE_THREADS = 0

# Дополнительные опции Pillow для обработки изображений
# LOAD_TRUNCATED_IMAGES: загружать некорректно завершенные изображения
# (полезно для некачественных или поврежденных файлов)
PILImage.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)


# ==============================================================================
# Конфигурация приложения для фронтенда lpon
# ==============================================================================
class FrontendConfig(AppConfig):
    name = 'frontend'
    verbose_name = 'Сайт lpon.ru'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self) -> None:
        """Инициализация Django Admin с кастомным заголовком и названиями."""
        from django.contrib import admin
        admin.site.site_header = 'Управление LPON'
        admin.site.site_title = 'LPON Administrator'
        admin.site.index_title = 'Добро пожаловать в LPON'


# ==============================================================================
# Кастомная конфигурация для django-filer
# Патчинг MultiStorageFieldFile.save() для автоматической конвертации в WebP
# ==============================================================================
class CustomFilerConfig(AppConfig):
    name = 'filer'
    verbose_name = 'Медиафайлы'

    # Атрибуты конфигурации Django-Filer (импортированы из settings.py)
    FILER_ENABLE_PERMISSIONS = FILER_ENABLE_PERMISSIONS
    FILER_UPLOADER_MAX_FILE_SIZE = FILER_UPLOADER_MAX_FILE_SIZE
    FILER_WHITELIST_FOR_PATH_ACCESS = FILER_WHITELIST_FOR_PATH_ACCESS
    MIME_TYPE_WHITELIST = MIME_TYPE_WHITELIST
    FILE_VALIDATORS = FILE_VALIDATORS

    @staticmethod
    def _convert_to_webp_if_needed(
        name: str, content: File
    ) -> Tuple[File, str, bool, int | None, int | None]:
        """
        Преобразует загруженное изображение в WebP формат.
        Поддерживает JPEG, PNG, BMP, TIFF и HEIC/HEIF.

        Args:
            name: Имя файла с расширением
            content: Содержимое файла (Django File object)

        Returns:
            Кортеж: (content, new_name, was_converted, image_width, image_height)
            - content: WebP файл или исходный файл
            - new_name: Новое имя файла (.webp)
            - was_converted: Был ли произведен конвертирование
            - image_width: Ширина изображения в пикселях (None если не конвертирован)
            - image_height: Высота изображения в пикселях (None если не конвертирован)

        Raises:
            ValidationError: Если произошла ошибка при конвертации

        Размеры ОБЯЗАТЕЛЬНО получаются из исходного изображения перед конвертацией.
        При конвертации в WebP размеры пикселей не меняются, меняется только качество файла.
        """
        _, original_ext = os.path.splitext(name)

        # PNG исключено, т.к. их планирую использовать для иконок (может быть, верну позже)
        convertible_extensions = [".jpg", ".jpeg", ".bmp", ".tiff", ".heic", ".heif"]

        if original_ext.lower() in convertible_extensions:
            try:
                # Открываем исходный файл с помощью PIL
                content.seek(0)
                img = PILImage.open(BytesIO(content.read()))

                # Получаем размеры изображения ДО конвертации (они не меняются при сохранении в WebP)
                image_width, image_height = img.size

                # Конвертируем CMYK в RGB если требуется
                if img.mode == 'CMYK':
                    img = img.convert('RGB')

                # Сохраняем в WebP формат в памяти
                webp_buffer = BytesIO()
                img.save(webp_buffer, format="WEBP", quality=THUMBNAIL_WEBP_QUALITY)
                webp_data = webp_buffer.getvalue()

                # Изменяем расширение на .webp
                new_name = os.path.splitext(name)[0] + ".webp"

                return ContentFile(webp_data), new_name, True, image_width, image_height

            except Exception as e:
                # Поднимаем ValidationError чтобы она показывалась в админке
                error_msg = f"Ошибка при конвертации '{name}' в WebP: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise ValidationError(error_msg)

        # Если файл не нуждается в конвертации, возвращаем как есть
        content.seek(0)
        return content, name, False, None, None

    def ready(self) -> None:
        """
        Инициализация: патчинг MultiStorageFieldFile.save() для WebP конвертации.
                       Добавление поддержки HEIC/HEIF в filer.
        """
        from filer.fields.multistorage_file import MultiStorageFieldFile
        from filer import settings as filer_settings

        original_save = MultiStorageFieldFile.save

        # Важно: Добавляем поддержку HEIC/HEIF файлов в filer
        # IMAGE_EXTENSIONS это глобальные константы в filer, которые нельзя переопределить через settings.py
        # Единственный способ - модифицировать после импорта в ready() методе AppConfig
        filer_settings.IMAGE_EXTENSIONS  = list(set(filer_settings.IMAGE_EXTENSIONS + ['.heic', '.heif']))
        filer_settings.IMAGE_MIME_TYPES = list(set(filer_settings.IMAGE_MIME_TYPES + ['heic', 'heif']))

        def patched_save(
            self_instance, name: str, content: File, save: bool = True
        ) -> str | None:
            """
            Патчированг MultiStorageFieldFile.save().
            Конвертирует загруженные картинки в WebP и обновляет метаданные.

            Args:
                self_instance: Экземпляр MultiStorageFieldFile
                name: Имя файла
                content: Содержимое файла
                save: Нужно ли сохранять в БД (по умолчанию True)

            Returns:
                Имя сохраненного файла или None
            """
            new_content, new_name, converted, img_width, img_height = (
                CustomFilerConfig._convert_to_webp_if_needed(name, content)
            )

            if converted:
                # Переустанавливаем корректный mime_type (всё станет WebP)
                self_instance.instance.mime_type = "image/webp"

                # Обновляем original_filename если есть
                if hasattr(self_instance.instance, 'original_filename'):
                    if self_instance.instance.original_filename:
                        original_filename, _ = os.path.splitext(self_instance.instance.original_filename)
                        self_instance.instance.original_filename = f"{original_filename}.webp"

                # КРИТИЧНО: Обновляем размер файла и sha1 на основе WebP данных, а не исходных
                new_content.seek(0)
                webp_bytes = new_content.read()
                new_content.seek(0)
                self_instance.instance._file_size = len(webp_bytes)
                self_instance.instance.sha1 = hashlib.sha1(webp_bytes).hexdigest()

            # Вызываем оригинальный save() метод
            result = original_save(self_instance, new_name, new_content, save)

            # После сохранения гарантируем что mime_type=image/webp в БД
            if converted and new_name.lower().endswith('.webp'):
                if self_instance.instance.id:
                    self_instance.instance.__class__.objects.filter(
                        id=self_instance.instance.id
                    ).update(mime_type='image/webp')

            return result

        MultiStorageFieldFile.save = patched_save
