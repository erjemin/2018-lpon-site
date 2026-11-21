# Docker, compose и CI по образцу hypn0

**Дата и время составления:** 2026-11-21 11:40
**Статус:** план. Файлы проекта не менялись. Образец: `/Users/e-serg/PRJ/2026-hypn0-site` (тоже Django, SQLite, внешний nginx, образ в реестре `git.cube2.ru`, Watchtower). Документ описывает, что переносим, что меняем и что сломано в текущих файлах lpon.
**Связанные документы:** `lpon--metadata-config.md` (каталог `config/metadata-toml/`), `OFFER-CODE-HASHIDS-SALT-GENERATION.md` (соль в `.env`), `DATA-SOURCES-PARSING.md` (команды импорта и cron).

---

## 1. Решение

Docker и CI в lpon устроить так же, как в hypn0:

1. **Один образ с Django**, который собирает CI при создании git-тега `v*` и публикует в реестр `git.cube2.ru/erjemin/2018-lpon-site`.
2. **Боевой compose** берёт готовый образ (`image:`), а не собирает его. Обновление на сервере делает Watchtower.
3. **Внешний nginx** на хосте проксирует на Gunicorn в контейнере и сам раздаёт статику и медиа из каталога `public/` на хосте.
4. **Тома с хоста**: `database/` (SQLite), `public/media/` (загрузки), `public/` (экспорт статики), `config/` (nginx, метаданные, cron).
5. Три compose-файла: dev, prod и prod-test (тот же prod, но с `build: .`).

## 2. Что есть сейчас в lpon

| Файл | Что делает сейчас |
|:---|:---|
| `Dockerfile` | собирает **только nginx** (`nginx:alpine`), копирует `public/` в его корень и `config/nginx/lpon--internal-nginx.conf`. Django в образе нет |
| `docker-compose.yml` | dev: собирает этот nginx, порт `127.0.0.1:8020:80` |
| `docker-compose.prod.yml` | prod: образ `git.cube2.ru/erjemin/2018-lpon-site:latest`, Watchtower (область `lpon-scope`), том `./config:/nginx_configs_host`, порт `127.0.0.1:8020:80` |
| CI | нет (каталога `.gitea/` нет) |
| внешний nginx | `config/nginx/lpon--external-nginx.conf`: проксирует всё (`location /`) на `127.0.0.1:8020`, статику и медиа не раздаёт |

То есть сейчас на проде сайт-заглушка из статических страниц; приложение Django в Docker ещё не упаковано. Файлы старые и «очень предварительные» (вы просили пока не смотреть), поэтому ниже это не критика, а список того, что при переносе всё равно пришлось бы исправить.

### Найдено при чтении (запуском не проверялось)

1. **`command` в `docker-compose.prod.yml` не запускает nginx.** Цепочка `mkdir && sed && if ... fi` заканчивается, а запуска `nginx` в ней нет. Команда заменяет стандартный запуск образа, значит контейнер после неё завершается и из-за `restart: always` перезапускается по кругу. Возможно, это работает иначе из-за деталей образа, но в самом файле запуска нет.
2. **Имя файла не совпадает.** Скрипт читает `/nginx_configs_host/nginx/lpon-app--external-nginx.conf`, а в репозитории `config/nginx/lpon--external-nginx.conf`. Если файла нет, `sed` падает, цепочка обрывается.
3. **Источник для `sed` лежит на хосте**, а не в образе (в hypn0 исходник берётся из образа `/home/app/web/config/nginx/...`, и это надёжнее: файл всегда есть).
4. **В подсказке запуска опечатка:** `docker compose -f docker compose -f compose.prod.yml up -d`.
5. **`volumes: static_volume`** объявлен и нигде не используется.
6. **`.dockerignore`:** комментарии стоят в одной строке с шаблонами (`.env  # ...`, `db.sqlite3  # ...`, `database/  # ...`, `public/media  # ...`). Docker так не читает, значит `.env`, `database/` и `public/media` могут попадать в образ. Ранее уже отмечено в `00_START_HERE.md`. Образец (`2026-hypn0-site/.dockerignore`) пишет комментарии отдельными строками.
7. В `.dockerignore` не исключены `_prj_blueprint/`, `datasources/`, `docs/`, `.junie/`, будущие `.gitea/`, `docker-compose*.yml`, `*.sqlite*`, `**/node_modules/`. Для Tailwind каталог `frontend-assembly/` в контексте нужен.

## 3. Образец hypn0: что именно переносим

### 3.1. Dockerfile (три стадии, 119 строк)

1. `frontend-builder` (`node:22-slim`): копирует `frontend-assembly/`, исходники шаблонов и `scripts/build-tailwind.sh`, собирает `public/static/css/tailwind.min.css`.
2. `builder` (`python:3.14-slim`): ставит Poetry и `poetry-plugin-export`, экспортирует `poetry.lock` в `requirements.txt`, ставит зависимости через `pip`.
3. `stage-final` (`python:3.14-slim`): копирует пакеты из `builder`, код проекта с владельцем 1000:1000, свежий CSS из `frontend-builder`; создаёт каталоги (`/nginx_configs_host/nginx`, `public/staticfiles`, `public/media/_error`, `database`); пользователь `1000`; `collectstatic` с фиктивным `SECRET_KEY`; `HEALTHCHECK` запросом к `/`; запуск `gunicorn` с двумя воркерами.

### 3.2. Боевой compose (184 строки)

- Сервис `tailwind-builder` (одноразовый, пересобирает CSS при старте) и `web` с `depends_on: service_completed_successfully`. В lpon это можно не переносить: CSS собирается в образе (стадия 1), второй раз на сервере не нужен. В hypn0 оба варианта оставлены.
- Сервис `web`: образ из реестра, `restart: always`, метка Watchtower, длинная `command` (миграции, `collectstatic`, экспорт статики на хост через `cp -u`, генерация конфига nginx, страницы ошибок, подсказка для cron, `gunicorn`).
- Порт только на localhost хоста: `127.0.0.1:8042:8000`.
- Тома: `./database`, `./public/media`, `./public` (в `/host_public`), `./config` (в `/nginx_configs_host`).
- `user: "0:0"` для первого запуска (иначе нет прав инициализировать каталоги на хосте). Позже можно ужесточить.
- `healthcheck` каждые 3 минуты (важно для Watchtower), ротация логов, лимиты ресурсов (0.5 CPU, 512 МБ).
- Сервис `watchtower`: интервал 1800 секунд, `--cleanup`, учётные данные реестра из `.env` (`REPO_USER`, `REPO_PASS`), область `*-scope`.

### 3.3. Dev и prod-test

- `docker-compose.dev.yml`: сборка из локального `Dockerfile`, порт 8042 на всех интерфейсах, код монтируется с хоста (`./hypn0:/home/app/web/hypn0`), `public/` и `database/` тоже, один воркер с `--reload`, `DJANGO_DEBUG=True`.
- `docker-compose.prod-test.yml` совпадает с prod, кроме `build: .` вместо `image:`. Нужен для проверки боевой схемы локально.

### 3.4. CI: `.gitea/workflows/docker-publish.yaml`

- Запуск: `push` тега `v*` (пример: `git tag v0.1.1 && git push origin v0.1.1`).
- Шаги: checkout, QEMU, Buildx, вход в реестр `git.cube2.ru` (пользователь `github.actor`, пароль из секрета `REGISTRY_PASSWORD`), метаданные тегов (тег версии и `latest`), сборка и публикация только под `linux/amd64`, кэш слоёв в реестре (тег `buildcache`), таймаут 30 минут.
- Файл содержит упоминание `HYPN0` в названии: в lpon заменить. Имя образа берётся из `github.repository`, поэтому оно подставится само.

## 4. Что меняем при переносе в lpon

| Что | hypn0 | lpon (предложение) |
|:---|:---|:---|
| Пакет проекта и `manage.py` | `hypn0/manage.py`, `DJANGO_SETTINGS_MODULE=hypn0.settings`, `PYTHONPATH=/home/app/web/hypn0` | `lpon_site/manage.py`, `DJANGO_SETTINGS_MODULE=lpon_site.settings`, `PYTHONPATH=/home/app/web/lpon_site`; рабочий каталог `/home/app/web/lpon_site`, команда `lpon_site.wsgi:application` (проверить имя) |
| База | `/home/app/web/database/hypn0-db.sqlite3` | `/home/app/web/database/lpon-db.sqlite3` (в `settings.py` путь `BASE_DIR.parent/database/`, схема каталогов совпадает) |
| Python | 3.14 | 3.12 (в `pyproject.toml` `^3.12`, локально 3.12.10); образ `python:3.12-slim`, пути `site-packages` поправить на `python3.12` |
| Зависимости | в `pyproject.toml` есть `gunicorn` и статика | в `pyproject.toml` **нет `gunicorn`**: добавить. Статику раздаёт nginx с хоста, `whitenoise` можно не добавлять |
| Порт | 8042 | оставить 8020 (его уже знает внешний nginx) |
| Имя контейнера, метка Watchtower | `hypn0-*`, `hypn0-scope` | `lpon-*`, `lpon-scope` (в текущем prod-файле уже так) |
| Команды запуска | `migrate`, `collectstatic`, `rehash` | `migrate`, `collectstatic`. Команды `rehash` в lpon нет. `regenerate_offer_codes` автоматически **не запускать** (меняет коды офферов, `OFFER-CODE-HASHIDS-SALT-GENERATION.md`) |
| Страницы ошибок | копируются из `templates/_error/` для автономной отдачи nginx | в lpon есть `lpon_site/templates/404.html` как Django-шаблон; отдельных статичных страниц ошибок нет. Шаг пока не переносить |
| Каталог `config/` в контейнере | `/nginx_configs_host` | оставить `/nginx_configs_host` (решение: nginx остаётся, рядом новая папка `metadata-toml`) |
| Проверка здоровья | `GET /` | `GET /` (маршрут `views.index` есть) |
| Внутренний nginx | нет | убрать: `config/nginx/lpon--internal-nginx.conf` и `docker-compose.yml` старого вида больше не нужны, статику раздаёт внешний nginx |

### Новое для lpon

1. **Каталог конфига метаданных на хосте.** В команду запуска добавить:
   - создать каталог `/nginx_configs_host/metadata-toml` (на хосте `./config/metadata-toml`);
   - скопировать в него базовый `default.toml` из образа, **не перезаписывая** существующий (`cp -n`), чтобы фабричный файл «прилетал» на хост в проде, а рабочие правки владельца не затирались.
   - В настройках `METADATA_CONFIG_DIR` = `/nginx_configs_host/metadata-toml` в контейнере (через `.env`), а при запуске без Docker `config/metadata-toml/` в корне проекта.
   - Это закрывает открытый вопрос 3 из `00_START_HERE.md` («как `default.toml` попадает на хост»).
2. **Внешний nginx должен раздавать `/static/` и `/media/`.** Сейчас `config/nginx/lpon--external-nginx.conf` проксирует всё на приложение. По образцу hypn0 `location /static/` и `location /media/` ведут на `public/static`, `public/staticfiles`, `public/media` хоста. В `settings.py`: `STATIC_URL='/static/'`, `MEDIA_URL='/media/'`, `STATIC_ROOT=public/staticfiles`, `MEDIA_ROOT=public/media`, `FILER_STORAGES` пишет в `public/media/flr` и `flrm` (проверено).
3. **Резервная копия SQLite.** Приложение при каждом запуске делает `migrate`, а Watchtower перезапускает контейнер без участия человека. Поэтому нужно: перед `migrate` копировать базу (например, `cp database/lpon-db.sqlite3 database/backup/lpon-db-<дата>.sqlite3`; для консистентности лучше команда `sqlite3 .backup`, если установлена) и отдельная запись в cron на хосте. По образцу `config/crontab.example`, который hypn0 генерирует при старте. Для lpon сюда же добавятся команды импорта и обслуживания (`DATA-SOURCES-PARSING.md`).
4. **Права.** Каталог `database/` должен быть доступен на запись процессу Django (SQLite создаёт рядом файлы журнала). При пользователе 1000 нужен `chown` на хосте или запуск `user: "0:0"` на первом старте, как в образце.
5. **Два воркера Gunicorn и SQLite.** Для магазина с единственным владельцем-редактором достаточно, но писать в SQLite могут несколько процессов сразу (вебсервер, cron-импорт). Стоит включить режим WAL (`PRAGMA journal_mode=WAL`) и увеличить таймаут блокировки. Не проверялось.
6. **Секреты.** В образ не попадают `.env`, `.env.*`, `database/`, `public/media/`, рабочие редакции `config/metadata-toml/*` (кроме `default.toml`). `.env.example` уже содержит `HOST_PROJECT_PATH`, `REPO_USER`, `REPO_PASS`. Для CI в Gitea нужен секрет репозитория `REGISTRY_PASSWORD`. В `.env` продакшена должны быть свои `DJANGO_SECRET_KEY` и `OFFER_HASHIDS_SALT` (иначе молча подставятся значения по умолчанию из `settings.py`).

## 5. Выпуск версии

```
правка кода -> коммит -> git tag v0.1.0 -> git push origin v0.1.0
   -> Gitea Actions собирает образ и публикует :v0.1.0 и :latest
   -> Watchtower на сервере (раз в 30 минут) видит новый :latest, перезапускает контейнер
   -> контейнер при старте делает migrate, collectstatic, копирует статику на хост
   -> healthcheck подтверждает, что приложение отвечает
```

Откат: в боевом compose указать конкретный тег (`image: ...:v0.1.0`) вместо `latest` и перезапустить; базу откатывать из резервной копии, если миграция была необратимой.

## 6. Риски и ограничения

- **Автоматический `migrate` с SQLite без бэкапа** опасен: ошибка в миграции портит единственную копию данных. Бэкап перед `migrate` обязателен.
- **Watchtower перезапускает контейнер без предупреждения.** Для магазина с загрузкой фото это терпимо, но нужно помнить, что в момент перезапуска сайт недоступен 20-60 секунд.
- **Образ собирается под `linux/amd64`.** Если сервер на другой архитектуре, нужно добавить платформу (как в комментарии в workflow).
- **Фронтенд-сборка зависит от `frontend-assembly/tailwind/package-lock.json`** и сети (npm). При недоступности npm сборка в CI упадёт.
- **Корень репозитория содержит лишнее** (`datasources/`, `_prj_blueprint/`, `docs/`): их нужно исключить в `.dockerignore`, иначе контекст сборки раздувается.
- **Gitea Actions и раннер.** Образец использует `runs-on: ubuntu-latest` и контейнер `catthehacker/ubuntu:act-latest`. В Gitea должен быть зарегистрирован раннер; это настройка сервера, в репозитории её нет. Не проверялось.

## 7. Порядок работ

1. Добавить `gunicorn` в `pyproject.toml` и `poetry.lock`.
2. Переписать `Dockerfile` (три стадии, Python 3.12, пути `lpon_site`).
3. Исправить `.dockerignore` (комментарии на отдельные строки, расширить список).
4. Создать `docker-compose.dev.yml`, переписать `docker-compose.prod.yml`, добавить `docker-compose.prod-test.yml`; старый `docker-compose.yml` убрать или заменить dev-файлом.
5. Дописать `config/nginx/lpon--external-nginx.conf` (статика и медиа напрямую, правильные пути).
6. Добавить `.gitea/workflows/docker-publish.yaml`, секрет `REGISTRY_PASSWORD`.
7. Добавить настройку `METADATA_CONFIG_DIR` в `settings.py` и шаг копирования `default.toml` в команду запуска.
8. Бэкап SQLite и `config/crontab.example`.
9. Проверка локально через `docker-compose.prod-test.yml`, затем пробный тег `v0.0.1`.

Пункты 2-6 не зависят от моделей и конфига метаданных и могут делаться параллельно с разработкой каталога.

## 8. Открытые вопросы

1. Python 3.12 или новее для образа (образец использует 3.14; локально 3.12.10).
2. Оставить ли одноразовый сервис `tailwind-builder` в боевом compose или собирать CSS только в образе (предложение: только в образе).
3. Порт 8020 оставить или перейти на новый.
4. Нужны ли статичные страницы ошибок для nginx (в lpon есть только Django-шаблон `404.html`).
5. Как делать резервные копии SQLite и куда их класть (в `database/backup/` на том же диске или вынести).
6. Где регистрируется раннер Gitea Actions и есть ли у него доступ к npm и к реестру.
7. Нужен ли `docker-compose.prod-test.yml` отдельным файлом или достаточно профиля.
