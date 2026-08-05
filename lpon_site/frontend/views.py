#

from dataclasses import dataclass

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

from frontend.models import TbArticle

# Create your views here.


@dataclass(frozen=True)
class BreadcrumbItem:
    """
    Один пункт хлебных крошек (например, "Главная", "Каталог", "Винил").

    ЧТО ТАКОЕ dataclass (если видите это в первый раз)
    ----------------------------------------------------
    `@dataclass` — это декоратор из стандартной библиотеки Python (модуль `dataclasses`).
    Он берёт класс, в котором просто перечислены имена полей и их типы (без ручного
    __init__), и САМ генерирует за вас служебные методы:
        - __init__(self, title, url=None)  — конструктор класса. Благодаря нему можно
          писать BreadcrumbItem(title="Каталог", url="/catalog") без единой строчки
          кода конструктора;
        - __repr__   — красивое текстовое представление для print()/логов, например:
          BreadcrumbItem(title='Каталог', url='/catalog');
        - __eq__     — сравнение двух объектов по значениям полей, то есть
          BreadcrumbItem('Каталог', '/catalog') == BreadcrumbItem('Каталог', '/catalog')
          вернёт True (без dataclass пришлось бы сравнивать id() объектов).

    Без dataclass пришлось бы писать руками:

        class BreadcrumbItem:
            def __init__(self, title, url=None):
                self.title = title
                self.url = url

    С dataclass — просто пишем поля (см. ниже) и всё перечисленное выше Python
    сгенерирует сам. Это НЕ меняет то, как объект используется — просто экономит
    код и снижает риск ошибок при ручном написании __init__/__repr__/__eq__.

    Чем dataclass отличается от NamedTuple (typing.NamedTuple)?
    ---------------------------------------------------------------
    Обе конструкции решают одну и ту же задачу — описать "структуру из нескольких
    полей" без лишнего кода, но по-разному устроены внутри:
        - `NamedTuple` — это, по сути, обычный tuple с именами полей. Он ВСЕГДА
          неизменяем (immutable), поддерживает распаковку как обычный tuple
          (title, url = item) и итерацию (for value in item);
        - `dataclass` — это обычный класс. По умолчанию он изменяем (можно
          присвоить item.title = "..." в любой момент), но можно сделать
          неизменяемым через параметр frozen=True (как сделано ниже). В отличие
          от NamedTuple, dataclass НЕ поддерживает распаковку как tuple, зато его
          проще расширять методами, наследованием и сложными полями по умолчанию
          (списками, словарями и т.п.).

    Для хлебных крошек подошёл бы любой из двух вариантов. Здесь выбран dataclass
    с frozen=True — то есть объект ведёт себя как неизменяемый: попытка сделать
    `item.title = "другое значение"` после создания вызовет исключение. Это
    логично: один и тот же пункт крошек не должен "мутировать" по ходу рендеринга
    страницы.

    КОНТРАКТ С ШАБЛОНОМ (важно!):
    -------------------------------
    Шаблон lpon_site/templates/block/breadcrumbs.html ожидает контекстную
    переменную `breadcrumbs` — список объектов именно с такими двумя полями:

    Атрибуты:
        title (str):
            Видимый текст пункта, например "Каталог", "Винил".
        url (str | None):
            Ссылка на пункт. Если None (значение по умолчанию) — пункт
            считается ТЕКУЩЕЙ страницей: шаблон покажет его БЕЗ ссылки, с
            атрибутом aria-current="page". Обычно url=None указывают только
            у ПОСЛЕДНЕГО пункта в списке крошек.

    ВАЖНО: пункт "Главная" в этот список включать НЕ нужно — ссылку на
    главную страницу (в виде иконки домика) шаблон breadcrumbs.html
    добавляет сам, одинаково для всех страниц. Список крошек должен
    начинаться сразу со следующего уровня (например, с "Каталог").

    Пример использования — см. функцию catalog() ниже.
    """
    title: str
    url: str | None = None


def index(request: HttpRequest | None) -> HttpResponse:
    return render(request, 'index.html', {})


def catalog(request: HttpRequest | None) -> HttpResponse:
    """
    Страница каталога (пока черновик вёрстки, см. lpon_site/templates/catalog.html).

    ТЕСТОВЫЕ ДАННЫЕ ДЛЯ ХЛЕБНЫХ КРОШЕК:
    В реальной вьюхе список крошек будет собираться динамически (в зависимости
    от применённых фильтров, выбранной категории и т.п.). Пока каталог — черновик,
    здесь захардкожен простой пример из двух пунктов, чтобы продемонстрировать
    работу block/breadcrumbs.html: "Каталог" — обычный пункт со ссылкой, а
    "Компакт-кассеты" — текущая страница (url не передан, поэтому он покажется без
    ссылки). Пункт "Главная" передавать не нужно — его в виде иконки домика
    сам добавляет шаблон breadcrumbs.html.
    """
    breadcrumbs = [
        BreadcrumbItem(title="Каталог", url="/catalog"),
        BreadcrumbItem(title="Компакт-кассеты", url="/catalog/compact-cassettes"),  # url передан -> обычный пункт со ссылкой
        BreadcrumbItem(title="Для перезаписи" ),  # url передан -> обычный пункт со ссылкой
    ]
    return render(request, 'catalog.html', {"breadcrumbs": breadcrumbs})


def txt_articles_list(request: HttpRequest | None) -> HttpResponse:
    """
    Представление (View) для отображения списка текстовых статей (тип ArticleType.TXT).

    Функциональность:
    -----------------
    1. Выбирает из БД все опубликованные статьи (b_article_published=True) с типом 'txt'.
    2. Сортирует их по полю приоритета i_article_sort (по возрастанию, чем меньше число —
       тем выше в списке), затем по дате создания (-t_article_created) и названию.
    3. Оптимизирует выборку связанного файла обложки (k_article_to_image) через select_related,
       чтобы избежать N+1 запросов при рендеринге изображений в списке.
    4. Формирует хлебные крошки (BreadcrumbItem) с элементом "Инструкции".
    5. Рендерит шаблон `txt_list.html`, передавая в контекст список статей и хлебные крошки.

    Аргументы:
        request (HttpRequest | None): Объект HTTP-запроса Django.

    Возвращает:
        HttpResponse: Сформированная HTML-страница со списком текстовых статей.
    """
    # Выбираем опубликованные текстовые статьи из базы данных с правильной сортировкой
    articles = (
        TbArticle.objects.filter(
            l_article_type=TbArticle.ArticleType.TXT,
            b_article_published=True,
        )
        .select_related('k_article_to_image')
        .order_by('i_article_sort', '-t_article_created', 's_article_title')
    )

    # Формируем цепочку хлебных крошек (пункт "Главная" добавляется автоматически в шаблоне)
    breadcrumbs = [
        BreadcrumbItem(title="Инструкции"),
    ]

    # Передаём контекст в шаблон списка текстовых статей
    context = {
        "articles": articles,
        "breadcrumbs": breadcrumbs,
    }
    return render(request, "roll/txt_list.html", context)