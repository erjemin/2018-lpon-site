import os
import hashlib
from io import BytesIO
from django.apps import AppConfig
from django.core.files.base import ContentFile
from PIL import Image as PILImage

from lpon_site.settings import DEBUG, THUMBNAIL_WEBP_QUALITY


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

    @staticmethod
    def generate_upload_path_flr(instance, filename):
        from filer.utils.generate_filename import randomized
        base_path = randomized(instance, filename)
        return f'flr/{base_path}'

    @staticmethod
    def generate_upload_path_flrm(instance, filename):
        from filer.utils.generate_filename import randomized
        base_path = randomized(instance, filename)
        return f'flrm/{base_path}'

    class WebPConverter:
        def convert_to_webp_if_needed(self, name: str, content):
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
                    new_name = name.rsplit(original_ext, 1)[0] + ".webp"
                    return ContentFile(buffer.read()), new_name, True
                except Exception as e:
                    import sys
                    print(f"[WebPConverter] ERROR converting {name}: {e}", file=sys.stderr)
                    content.seek(0)
                    return content, name, False
            content.seek(0)
            return content, name, False

    def ready(self):
        import sys
        from filer.fields.multistorage_file import MultiStorageFieldFile

        print("[CustomFilerConfig.ready] Patching MultiStorageFieldFile.save()...", file=sys.stderr)
        original_save = MultiStorageFieldFile.save
        webp_converter = self.WebPConverter()

        def patched_save(self_instance, name, content, save=True):
            new_content, new_name, converted = webp_converter.convert_to_webp_if_needed(name, content)
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
        print("[CustomFilerConfig.ready] MultiStorageFieldFile.save() patched successfully", file=sys.stderr)

# Создаем псевдонимы на уровне модуля для функций, чтобы их мог найти Django
generate_upload_path_flr = CustomFilerConfig.generate_upload_path_flr
generate_upload_path_flrm = CustomFilerConfig.generate_upload_path_flrm
