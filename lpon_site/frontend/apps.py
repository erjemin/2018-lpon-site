import os
from io import BytesIO
from django.apps import AppConfig
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from django.db.models.signals import pre_save
from PIL import Image as PILImage


from lpon_site.settings import DEBUG

# 1.
class FrontendConfig(AppConfig):
    name = 'frontend'
    verbose_name = 'Сайт lpon.ru'
    # Переключаем на стандартный AutoField (до 2 млрд записей)
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        """
        Вызывается при инициализации приложения.
        Настраиваем админ-сайт (заголовки и т.п.)
        """
        from django.contrib import admin
        admin.site.site_header = 'Управление LPON'
        admin.site.site_title = 'LPON Administrator'
        admin.site.index_title = 'Добро пожаловать в LPON'
        ## Если надо, импортируем сигналы при запуске приложения.


# 2. Создаем кастомное файловое хранилище специально для filer
class FilerWebPStorage(FileSystemStorage):
    def _save(self, name, content):
        filename, ext = os.path.splitext(name)

        # Обрабатываем только форматы картинок, исключая webp, svg и гифки
        if ext.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            try:
                # Читаем исходные байты файла
                content.seek(0)
                image_bytes = content.read()

                # Конвертируем в WebP через Pillow
                img = PILImage.open(BytesIO(image_bytes))
                buffer = BytesIO()
                img.save(buffer, format="WEBP", quality=85)
                buffer.seek(0)

                # Подменяем имя и контент на честный WebP
                name = f"{filename}.webp"
                content = ContentFile(buffer.read(), name=os.path.basename(name))
            except Exception as e:
                print(f"[Filer Storage WebP Error]: {e}")

        # Передаем управление стандартному сохранению на диск
        return super()._save(name, content)



# Добавляем кастомный конфиг для filer, чтобы переименовать verbose_name и добавить конфиги
class CustomFilerConfig(AppConfig):
    name = 'filer'
    verbose_name = 'Медиафайлы'  # Переименование вкладки в админке

    # ========================================================================
    # Конфигурация Django-Filer (для загрузки файлов через админку)
    # ========================================================================
    FILER_ENABLE_PERMISSIONS = DEBUG  # В production установить True для ограничения доступа

    # Разрешенные расширения файлов для FilerImageField
    FILER_WHITELIST_FOR_PATH_ACCESS = (
        # ПОДУМАТЬ: поддержка '.heic' требует дополнительных пакетов (и разных для прода и дева) + обработчик сигналов
        #           для автоматической конвертации .heic в .webp при загрузке. Пока отключаем, и оставим на будущее
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',  # Изображения
        '.doc', '.docx', '.pdf', '.txt', '.xls', '.xlsx', '.csv',  # Документы
    )

    # Максимальный размер загружаемого файла (в байтах): 100 MB
    FILER_MAX_UPLOAD_SIZE = 100 * 1024 * 1024

    # MIME-типы разрешенные для загрузки
    MIME_TYPE_WHITELIST = (
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/svg+xml',
        'image/webp',
        'application/pdf',
        'application/msword',  # .doc
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
        'text/plain',
        'application/vnd.ms-excel',  # .xls
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
        'text/csv',
    )

    # Tiny Image Specifications для автоматических вариантов изображений
    THUMBNAIL_ALIASES = {
        '': {
            # Для галерей и витрин
            # Кратные 16х16 картинки для ускорения GPU-рендера браузеров, retina-дисплеев и "копеечная" экономии на сервере
            'admin_thumbnail': {'size': (64, 64), 'crop': True},  # Для админки
            'small': {'size': (256, 256), 'crop': True},  # Квадрат 256x256 для миниатюр
            'medium': {'size': (512, 512), 'crop': True},  # Квадрат 512x512 для просмотра
            'large': {'size': (1024, 1024), 'crop': 'smart'},  # Большое изображение с умным crop
        },
    }

    # Форматы сохранения для thumbnail'ов (миниатюр)
    THUMBNAIL_PRESERVE_FORMAT = False  # Не сохранять оригинальный формат для thumbnails
    # THUMBNAIL_FORMAT = 'WEBP'  # Конвертировать все thumbnails в WebP
    THUMBNAIL_FORCE_FORMAT = 'WEBP'
    THUMBNAIL_WEBP_QUALITY = 80  # Качество WebP (достаточно 75-85 для thumbnails)

    # Интерпретатор для обработки изображений
    THUMBNAIL_ENGINE = 'easy_thumbnails.engines.pil_engine.PilEngine'

    # Качество JPEG при сжатии (0-100, по умолчанию 85)
    # THUMBNAIL_QUALITY = 85

    # Источник кеша для миниатюр
    THUMBNAIL_DEBUG = DEBUG  # Показывать ошибки генерирования миниатюр в debug режиме

    # Валидаторы файлов (пусто = без ограничений)
    FILE_VALIDATORS = {}

    def ready(self):
        from django.db.models.signals import pre_save
        from filer import settings as filer_settings
        from filer.models.imagemodels import Image as FilerImage

        # ХАК 1: Принудительно заставляем filer использовать наше кастомное хранилище.
        # Теперь все оригиналы файлов будут сохраняться через класс FilerWebPStorage.
        filer_settings.FILER_STORAGES["public"]["main"] = {
            "ENGINE": "frontend.apps.FilerWebPStorage",
            "OPTIONS": {},
        }

        # ХАК 2: Подключаем легкий сигнал pre_save только для того, чтобы
        # прописать в базу данных правильный mime_type и расширение для админки.
        pre_save.connect(self.fix_meta_before_db_save, sender=FilerImage)

    @staticmethod
    def fix_meta_before_db_save(sender, instance, **kwargs):
        if not instance.file or not instance.file.name:
            return

        filename, ext = os.path.splitext(instance.file.name)
        if ext.lower() in [".webp", ".svg", ".gif"]:
            return

        # Меняем метаданные для базы данных, так как на диске файл СТОПРОЦЕНТНО будет .webp
        instance.file.name = f"{filename}.webp"
        instance.mime_type = "image/webp"
