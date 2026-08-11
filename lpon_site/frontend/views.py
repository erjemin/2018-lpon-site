#

from dataclasses import dataclass
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpRequest, HttpResponse, Http404
from frontend.models import TbArticle
from frontend.utils import get_hub_context, parse_article_metadata
from lpon_site.settings import *
import json

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


def info_articles_list(request: HttpRequest | None) -> HttpResponse:
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
    5. Рендерит шаблон `info_list.html`, передавая в контекст список статей и хлебные крошки.

    Аргументы:
        request (HttpRequest | None): Объект HTTP-запроса Django.

    Возвращает:
        HttpResponse: Сформированная HTML-страница со списком текстовых статей.
    """
    # Выбираем опубликованные текстовые статьи из базы данных с правильной сортировкой
    articles = (
        TbArticle.objects.filter(
            l_article_type=TbArticle.ArticleType.INFO,
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
    return render(request, "roll/info_list.html", context)


def info_article_detail(request: HttpRequest | None, slug: str) -> HttpResponse:
    """
    Представление (View) для детального отображения отдельной текстовой статьи (тип ArticleType.INFO).

    Функциональность:
    -----------------
    1. Ищет опубликованную статью (b_article_published=True) по её слагу (slug).
       Если статья не найдена или не опубликована — возвращает HTTP 404 (Page Not Found).
    2. Вызывает метод `increment_views()` у объекта статьи для атомарного увеличения
       счётчика просмотров `i_article_views`.
    3. Формирует цепочку хлебных крошек (BreadcrumbItem):
       - "Инструкции" (со ссылкой на /info/);
       - Заголовок текущей статьи (без ссылки, текущий пункт).
    4. Рендерит шаблон `content/article_detail.html`, передавая объект статьи и крошки.

    Аргументы:
        request (HttpRequest | None): Объект HTTP-запроса Django.
        slug (str): Уникальный URL-слаг статьи.

    Возвращает:
        HttpResponse: Сформированная HTML-страница детального просмотра статьи.
    """
    # Получаем опубликованную статью по слагу или отдаем 404 Not Found
    article = get_object_or_404(
        TbArticle,
        slug=slug,
        b_article_published=True,
    )

    # Безопасно инкрементируем счетчик просмотров статьи
    article.increment_views()

    # Формируем цепочку хлебных крошек (пункт "Главная" добавляется автоматически в шаблоне)
    article_title = article.s_article_title_html or article.s_article_title
    breadcrumbs = [
        BreadcrumbItem(title="Инструкции", url="/info/"),
        BreadcrumbItem(title=article_title),
    ]

    # Получаем контекст с учетом возможных блоков HUB DSL
    context = get_hub_context(article)
    context["breadcrumbs"] = breadcrumbs

    return render(request, "content/article_detail.html", context)


def hub_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Универсальное представление (View) для хабов (включая страницы, запрашиваемые из корня сайта /<slug>).

    Функциональность:
    -----------------
    1. Ищет опубликованную статью (b_article_published=True) по её слагу (slug).
    2. Если статья принадлежит к каноническому типу с отдельным роутом (не HUB и не OTHER),
       выполняет HTTP 301 Permanent Redirect на её канонический адрес (article.get_absolute_url()).
    3. Валидирует j_article_metadata и наличие ключа HUB. Если статья — хаб, но метаданные
       невалидны или ключ HUB отсутствует — отдаёт HTTP 404 status с подсказкой для администратора.
    4. Увеличивает счётчик просмотров статьи, формирует хлебные крошки и рендерит шаблон хаба.

    Аргументы:
        request (HttpRequest): Объект HTTP-запроса Django.
        slug (str): Уникальный URL-слаг хаба или страницы.

    Возвращает:
        HttpResponse: Сформированная HTML-страница хаба либо страница ошибки 404.
    """
    # Ищем опубликованную статью по запрошенному слагу
    article = TbArticle.objects.filter(
        slug=slug,
        b_article_published=True,
    ).first()

    # Если статья не найдена — отдаём честный статус 404
    if article is None:
        admin_hint = (f"Статья или хаб со&nbsp;слагом «<strong>{ slug }</strong>» отсутствует в&nbsp;базе данных."
                      f" Создайте статью со&nbsp;слагом «<strong>{ slug }</strong>» (тип&nbsp;<code>HUB</code>)"
                      " в&nbsp;админис&shy;тративной панели.")
        return render(request, "404.html", {"admin_hint": admin_hint}, status=404)

    # Если нашлась статья с таким слагом и у неё каноническая ветка роутинга — 301-редирект
    if article.l_article_type not in (TbArticle.ArticleType.HUB, TbArticle.ArticleType.OTHER):
        return redirect(article.get_absolute_url(), permanent=True)

    # Проверяем и валидируем метаданные j_article_metadata
    metadata, error_msg = parse_article_metadata(article)
    if error_msg or not metadata:
        admin_hint = (f"Статья со&nbsp;слагом «<strong>{ slug }</strong>» (<code>id={ article.id }</code>) объявлена"
                      f" как&nbsp;хаб, но&nbsp;у&nbsp;неё <u>{ error_msg }</u>. Добавьте описание хаба (ключ"
                      f" <code>{ KEY_ARTICLE_HUB }</code>) в&nbsp;метаданные через&nbsp;<a  target='_blank'"
                      f" href='/{ADMIN_URL}frontend/tbarticle/{ article.id }/change/'>адми&shy;нистра&shy;тивную панель</a>.")
        return render(request, "404.html", {"admin_hint": admin_hint}, status=404)

    # Проверяем, что в метаданных есть ключ HUB
    if KEY_ARTICLE_HUB not in metadata:
        admin_hint = (f"Статья со&nbsp;слагом «<strong>{ slug }</strong>» (<code>id={ article.id }</code>) объявлена"
                      f" как&nbsp;хаб, но&nbsp;в&nbsp;её&nbsp;мета-данных нет ключа <code>{ KEY_ARTICLE_HUB }</code>"
                      " с&nbsp;описанием хаба. Внесите изменения в&nbsp;<a  target='_blank'"
                      f" href='/{ADMIN_URL}frontend/tbarticle/{ article.id }/change/'>адми&shy;нистра&shy;тивную панели</a>.")
        return render(request, "404.html", {"admin_hint": admin_hint}, status=404)

    # Формируем контекст с данными хаба и хлебными крошками
    context = get_hub_context(article, metadata)
    article_title = article.s_article_title_html or article.s_article_title
    context["breadcrumbs"] = [
        BreadcrumbItem(title=article_title),
    ]

    # Безопасно увеличиваем счетчик просмотров
    article.increment_views()

    return render(request, "content/hub.html", context)