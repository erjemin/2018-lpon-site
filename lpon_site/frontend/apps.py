from django.apps import AppConfig


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
        ## Если надо, импортируем сигналы при запуске приложения
        # import myapp.signals


# Добавляем кастомный конфиг для filer, чтобы переименовать verbose_name
class CustomFilerConfig(AppConfig):
    name = 'filer'
    verbose_name = 'Медиафайлы'  # Напишите здесь желаемое имя вкладки