from django.conf import settings
from django.http import HttpRequest


def is_debug(request: HttpRequest) -> dict:
    """
    Контекст-процессор Django.

    ЗАЧЕМ ЭТО НУЖНО:
        Автоматически добавляет флаг режима отладки во ВСЕ шаблоны проекта,
        без необходимости передавать его вручную в контексте каждой вьюхе.
        Контекстный-процессор необходимо зарегистрировать в settings.py:
        TEMPLATES['OPTIONS']['context_processors']

    ПОЧЕМУ НЕ штатный django.template.context_processors.debug:
        Штатный context-processor отдаёт переменную `debug` только если
        ОДНОВРЕМЕННО: settings.DEBUG == True И IP клиента входит в
        settings.INTERNAL_IPS (сверяется по request.META['REMOTE_ADDR']).
        В проекте с Docker/reverse-proxy — REMOTE_ADDR может быть не 127.0.0.1,
        а IP шлюза docker-сети, и потому штатный контекстный-процессор ненадёжен.

    :return
        dict: словарь с единственным ключом IS_DEBUG (bool)
              будет доступен во всех шаблонах как переменная контекста:
              {% if IS_DEBUG %}...{% endif %}
    """
    return {"IS_DEBUG": settings.DEBUG}
