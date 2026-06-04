from django.apps import AppConfig


class FrontendConfig(AppConfig):
    name = 'frontend'
    verbose_name = 'Сайт lpon.ru'
    # Переключаем на стандартный AutoField (до 2 млрд записей)
    default_auto_field = 'django.db.models.AutoField'

    # def ready(self):
        ## Импортируем сигналы при запуске приложения
        # import myapp.signals
