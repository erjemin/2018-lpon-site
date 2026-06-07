import os
import hashlib
from io import BytesIO
from django.apps import AppConfig
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from PIL import Image as PILImage

from lpon_site.settings import DEBUG, MEDIA_ROOT


# 0. Кастомная функция генерирования имен файлов специально для WebP
def generate_filename_webp(instance, filename):
    """
    Генерирует имя файла для сохранения. Если исходный файл был конвертирован в WebP,
    гарантирует что расширение файла будет .webp.
    """
    _, ext = os.path.splitext(filename)
    if ext.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        base_path = filename.rsplit(ext, 1)[0]
        return f"{base_path}.webp"
    return filename


# 0.1. Функция для генерирования путей с префиксом 'flr/' для основных файлов
def generate_upload_path_flr(instance, filename):
    """
    Генерирует путь для сохранения файла с префиксом 'flr/'.
    """
    from filer.utils.generate_filename import randomized
    base_path = randomized(instance, filename)
    return f'flr/{base_path}'


# 0.2. Функция для генерирования путей с префиксом 'flrm/' для миниатюр
def generate_upload_path_flrm(instance, filename):
    """
    Генерирует путь для сохранения миниатюр с префиксом 'flrm/'.
    """
    from filer.utils.generate_filename import randomized
    base_path = randomized(instance, filename)
    return f'flrm/{base_path}'


# 1.
class FrontendConfig(AppConfig):
    name = 'frontend'
    verbose_name = 'Сайт lpon.ru'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        from django.contrib import admin
        admin.site.site_header = 'Управление LPON'
        admin.site.site_title = 'LPON Administrator'
        admin.site.index_title = 'Добро пожаловать в LPON'


# 2.
class FilerWebPStorage(FileSystemStorage):
    """
    Кастомное хранилище для Filer. Основная логика конвертации перенесена
    в патч для MultiStorageFieldFile.save, чтобы обновлять метаданные до сохранения.
    """
    def _save(self, name: str, content):
        return super()._save(name, content)


# Добавляем кастомный конфиг для filer
class CustomFilerConfig(AppConfig):
    name = 'filer'
    verbose_name = 'Медиафайлы'

    # Конфигурация Django-Filer
    FILER_ENABLE_PERMISSIONS = DEBUG
    FILER_WHITELIST_FOR_PATH_ACCESS = (
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',
        '.doc', '.docx', '.pdf', '.txt', '.xls', '.xlsx', '.csv',
    )
    FILER_MAX_UPLOAD_SIZE = 100 * 1024 * 1024
    MIME_TYPE_WHITELIST = (
        'image/jpeg', 'image/png', 'image/gif', 'image/svg+xml', 'image/webp',
        'application/pdf', 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain', 'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/csv',
    )
    THUMBNAIL_ALIASES = {
        '': {
            'admin_thumbnail': {'size': (64, 64), 'crop': True},
            'small': {'size': (256, 256), 'crop': True},
            'medium': {'size': (512, 512), 'crop': True},
            'large': {'size': (1024, 1024), 'crop': 'smart'},
        },
    }
    THUMBNAIL_PRESERVE_FORMAT = False
    THUMBNAIL_FORCE_FORMAT = 'WEBP'
    THUMBNAIL_WEBP_QUALITY = 80
    THUMBNAIL_ENGINE = 'easy_thumbnails.engines.pil_engine.PilEngine'
    THUMBNAIL_DEBUG = DEBUG
    FILE_VALIDATORS = {}

    def ready(self):
        import sys
        from filer.fields.multistorage_file import MultiStorageFieldFile

        print("[CustomFilerConfig.ready] Patching MultiStorageFieldFile.save()...", file=sys.stderr)
        original_save = MultiStorageFieldFile.save
        webp_converter = WebPConverter()

        def patched_save(self, name, content, save=True):
            """
            Переопределенный save(), который преобразует изображение в WebP, обновляет
            метаданные модели (MIME-тип, размер, SHA1) и затем сохраняет.
            """
            new_content, new_name, converted = webp_converter.convert_to_webp_if_needed(name, content)

            if converted:
                # Обновляем метаданные прямо в инстансе модели
                self.instance.mime_type = "image/webp"
                
                if hasattr(self.instance, 'original_filename') and self.instance.original_filename:
                    original_filename, _ = os.path.splitext(self.instance.original_filename)
                    self.instance.original_filename = f"{original_filename}.webp"

                # Вручную пересчитываем размер и SHA1-хэш для нового файла .webp
                new_content.seek(0)
                file_bytes = new_content.read()
                new_content.seek(0)
                
                self.instance._file_size = len(file_bytes)
                self.instance.sha1 = hashlib.sha1(file_bytes).hexdigest()

            # Вызываем оригинальный метод save() с (возможно) новым контентом и именем
            return original_save(self, new_name, new_content, save)

        MultiStorageFieldFile.save = patched_save
        print("[CustomFilerConfig.ready] MultiStorageFieldFile.save() patched successfully", file=sys.stderr)


class WebPConverter:
    """
    Класс, инкапсулирующий логику преобразования изображений в WebP.
    """
    def convert_to_webp_if_needed(self, name: str, content):
        """
        Проверяет формат файла и, если это необходимо, преобразует его в WebP.
        Возвращает кортеж (новое_содержимое, новое_имя, флаг_конвертации).
        """
        _, original_ext = os.path.splitext(name)

        if original_ext.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            try:
                content.seek(0)
                img = PILImage.open(BytesIO(content.read()))
                
                if img.mode == 'CMYK':
                    img = img.convert('RGB')

                buffer = BytesIO()
                img.save(buffer, format="WEBP", quality=80)
                buffer.seek(0)

                new_name = name.rsplit(original_ext, 1)[0] + ".webp"
                
                return ContentFile(buffer.read()), new_name, True

            except Exception as e:
                import sys
                print(f"[WebPConverter] ERROR converting {name}: {e}", file=sys.stderr)
                content.seek(0)
                return content, name, False
        
        content.seek(0)
        return content, name, False
