# Lab 2.1 — Приложение для анализа защищённости

Учебный проект в рамках лабораторной работы №2.1 «Оценка защищённости разработанного приложения». Представляет собой веб-приложение с HTML-интерфейсом и JSON API, реализующее регистрацию, аутентификацию, CRUD публичных и конфиденциальных записей, а также административные функции. Приложение специально спроектировано с учётом типовых мер защиты и предназначено для последующего анализа защищённости по методике лабораторной работы.

---

## Содержание

- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Технологии](#технологии)
- [Требования](#требования)
- [Быстрый старт](#быстрый-старт)
- [Проверка работоспособности](#проверка-работоспособности)
- [Использование](#использование)
- [Структура проекта](#структура-проекта)
- [Меры защиты](#меры-защиты)
- [Конфигурация](#конфигурация)
- [Разработка и отладка](#разработка-и-отладка)
- [Частые проблемы](#частые-проблемы)
- [Остановка и очистка](#остановка-и-очистка)

---

## Возможности

- Регистрация, вход, выход пользователя.
- Сессии на стороне сервера (в БД), cookie HttpOnly + Secure + SameSite.
- Роли: `user`, `admin`.
- Публичные записи — CRUD + поиск, доступны всем авторизованным и гостям.
- Конфиденциальные записи — CRUD + поиск, доступны только владельцу; содержимое шифруется в БД.
- Админка: список пользователей, блокировка/разблокировка.
- Аудит действий (вход, выход, CRUD, админские операции).
- CSRF-защита форм (synchronizer token).
- Rate limiting на уровне Nginx (`limit_req`).
- HTTPS через Nginx с самоподписанным сертификатом.
- Security headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy.
- WAL-режим SQLite, foreign keys, busy timeout.

---

## Архитектура

```
                 ┌──────────────────────────┐
   browser  ───► │  Nginx (TLS, headers,    │
                 │  limit_req, proxy)       │
                 └────────────┬─────────────┘
                              │ http (внутр. сеть)
                 ┌────────────▼─────────────┐
                 │  FastAPI (uvicorn)       │
                 │  ├─ /            HTML    │
                 │  ├─ /api/v1      JSON    │
                 │  ├─ services/    логика  │
                 │  ├─ security/    auth,   │
                 │  │               csrf,   │
                 │  │               crypto  │
                 │  └─ deps.py      RBAC    │
                 └────────────┬─────────────┘
                              │ SQLAlchemy (sync)
                 ┌────────────▼─────────────┐
                 │  SQLite (WAL)            │
                 │  ./data/app.db           │
                 └──────────────────────────┘
```

Оба контейнера (`app`, `nginx`) находятся в одной внутренней Docker-сети. Наружу публикуются только порты Nginx: `8443` (HTTPS) и `8080` (HTTP → редирект на HTTPS). Порты контейнера `app` доступны только внутри сети.

---

## Технологии

- Python 3.14
- FastAPI + Uvicorn
- Jinja2 (HTML-шаблоны)
- SQLAlchemy 2.0 (sync) + SQLite (WAL)
- Argon2 (хеширование паролей)
- Fernet (AES-128-CBC + HMAC-SHA256) для шифрования конфиденциальных полей
- Nginx 1.27 (TLS, security headers, rate limiting)
- Docker + docker compose

---

## Требования

- Docker Engine 24+ и `docker compose` v2
- `openssl` (для генерации самоподписанного сертификата)
- `python3` на хосте — только для генерации Fernet-ключа (либо можно сделать это внутри контейнера)
- Свободные порты `8080` и `8443` на хосте

Проверка окружения:

```bash
docker --version
docker compose version
openssl version
```

---

## Быстрый старт

### 1. Клонировать репозиторий и перейти в каталог

> [!IMPORTANT]
> на данный момент репозиторий с проектом не создан, код ниже просто как заглушка

```bash
git clone <repo-url> lw2_1
cd lw2_1
```

### 2. Создать `.env`

```bash
cp .env.example .env
```

Открыть `.env` и заменить `APP_SECRET_KEY` на длинную случайную строку:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 3. Сгенерировать Fernet-ключ

```bash
mkdir -p secrets
python3 -c "from cryptography.fernet import Fernet; open('secrets/fernet_key','wb').write(Fernet.generate_key())"
chmod 600 secrets/fernet_key
```

Если пакет `cryptography` не установлен на хосте — можно сгенерировать ключ внутри контейнера:

```bash
docker run --rm python:3.14-slim sh -c "pip install cryptography -q && python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"" > secrets/fernet_key
chmod 600 secrets/fernet_key
```

Ключ монтируется в контейнер read-only по пути `/run/secrets/fernet_key`.

### 4. Сгенерировать самоподписанный сертификат

```bash
mkdir -p nginx/certs
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout nginx/certs/server.key \
  -out nginx/certs/server.crt \
  -subj "/CN=localhost"
chmod 600 nginx/certs/server.key
chmod 644 nginx/certs/server.crt
```

### 5. Подготовить каталог для БД

```bash
mkdir -p data
```

Файл `data/app.db` создастся автоматически при первом запуске.

### 6. Собрать и запустить

```bash
docker compose up --build -d
```

### 7. Проверить, что оба контейнера поднялись

```bash
docker compose ps
```

Ожидаем:

```
NAME          STATUS
lab21_app     Up ... (healthy)
lab21_nginx   Up ...
```

### 8. Создать администратора

```bash
docker compose exec app python -m app.cli create-admin \
  --username admin \
  --email admin@local.test \
  --password 'Admin12345!'
```

### 9. Открыть приложение

В браузере: **https://localhost:8443**

Браузер покажет предупреждение о самоподписанном сертификате — принять исключение для `localhost` (в Firefox: «Дополнительно» → «Принять риск и продолжить»).

---

## Проверка работоспособности

Проверка health-эндпоинта:

```bash
curl -k https://localhost:8443/healthz
# {"status":"ok"}
```

Проверка WAL и foreign keys:

```bash
sqlite3 data/app.db "PRAGMA journal_mode;"
# wal
```

Проверка схемы сессий:

```bash
docker compose exec app python -c "
from sqlalchemy import inspect
from app.db import engine
for c in inspect(engine).get_columns('sessions'):
    print(c['name'], c['nullable'])
"
```

`user_id` должен быть `True` — это значит, что анонимные сессии работают.

---

## Использование

### Регистрация

1. Открыть https://localhost:8443/auth/register.
2. Заполнить форму: username (3–32 символа, только `A–Z a–z 0–9 _ . -`), email, пароль (минимум 10 символов, буквы и цифры).

### Вход

https://localhost:8443/auth/login — по username или email.

### Публичные записи

- `/public` — список с поиском.
- `/public/new` — создать.
- `/public/{id}` — просмотр.
- `/public/{id}/edit` — редактировать (только владелец).
- Удаление — кнопка на странице просмотра (только владелец).

### Конфиденциальные записи

- `/confidential` — список **своих** записей.
- `/confidential/new` — создать (содержимое шифруется перед записью в БД).
- `/confidential/{id}` — просмотр (только владелец, содержимое расшифровывается на лету).
- `/confidential/{id}/edit` — редактировать (только владелец).

### Админка

- `/admin/users` — список пользователей с поиском.
- Кнопка «Заблокировать/Разблокировать» для каждого пользователя (кроме себя).

### Аудит

Все значимые действия пишутся в таблицу `audit_log`. Просмотр:

```bash
sqlite3 data/app.db "SELECT id, ts, actor_id, action, target, result, ip FROM audit_log ORDER BY id DESC LIMIT 30;"
```

### Проверка шифрования конфиденциальных полей

```bash
sqlite3 data/app.db "SELECT id, owner_id, title, length(content_encrypted), substr(content_encrypted,1,12) FROM confidential_records;"
```

Поле `content_encrypted` содержит бинарный Fernet-шифротекст, а не открытый текст.

---

## Структура проекта

```
lw2_1/
├── app/
│   ├── main.py                # точка входа FastAPI, middleware, подключение роутеров
│   ├── config.py              # настройки через pydantic-settings
│   ├── db.py                  # engine, SessionLocal, PRAGMA для SQLite
│   ├── models.py              # ORM-модели
│   ├── schemas.py             # Pydantic-схемы для API
│   ├── deps.py                # зависимости FastAPI
│   ├── cli.py                 # CLI (создание администратора)
│   ├── security/
│   │   ├── passwords.py       # Argon2
│   │   ├── sessions.py        # серверные сессии
│   │   ├── csrf.py            # synchronizer token
│   │   └── crypto.py          # Fernet
│   ├── services/
│   │   ├── users.py           # регистрация, аутентификация, роли
│   │   ├── records.py         # CRUD публичных и конфиденциальных записей
│   │   └── audit.py           # запись в audit_log
│   ├── routers/
│   │   └── html/              # HTML-роутеры (Jinja2)
│   │       ├── _common.py     # общие помощники: render, csrf
│   │       ├── auth.py
│   │       ├── public.py
│   │       ├── confidential.py
│   │       └── admin.py
│   ├── templates/             # Jinja2-шаблоны
│   └── static/                # статика (CSS/JS)
├── nginx/
│   ├── nginx.conf
│   ├── proxy_params_inline.conf
│   └── certs/                 # server.crt, server.key (не в git)
├── secrets/
│   └── fernet_key             # ключ шифрования (не в git)
├── data/
│   └── app.db                 # SQLite (не в git)
├── tests/                     # pytest
├── .env.example
├── .dockerignore
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── poetry.lock
└── README.md
```

---

## Меры защиты

| Аспект | Реализация |
|---|---|
| Пароли | Argon2id, параметры `time=3, memory=64 MiB, parallelism=2` |
| Сессии | Серверные, ID = SHA-256 от токена (в cookie — сам токен) |
| Cookie | HttpOnly, Secure, SameSite=Lax |
| Session fixation | Регенерация ID при логине (`bind_user_and_rotate`) |
| CSRF | HMAC-токен на базе `csrf_secret` сессии, hidden-поле в форме |
| SQL-инъекции | Параметризованные запросы через SQLAlchemy ORM |
| XSS | Jinja2 autoescape, security headers (CSP) |
| Шифрование конфиденциальных данных | Fernet (AES-128-CBC + HMAC-SHA256) |
| Хранение ключа шифрования | Вне БД, read-only volume `/run/secrets/fernet_key` |
| Разграничение доступа | Проверка владельца на уровне сервисов (anti-IDOR) |
| Rate limiting | Nginx `limit_req` на `/auth/login` (5 r/m) и `/api/` |
| HTTPS | Nginx + самоподписанный сертификат, HSTS |
| Security headers | HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| Аудит | Таблица `audit_log` (без FK, чтобы не терять записи) |
| Docker hardening | Непривилегированный пользователь, `cap_drop: ALL`, `no-new-privileges` |
| SQLite | WAL, foreign keys ON, busy timeout, `synchronous=NORMAL` |

---

## Конфигурация

Все настройки — через переменные окружения (файл `.env`). Пример — в `.env.example`.

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `APP_ENV` | Окружение (`dev` включает `/docs`) | `dev` |
| `APP_SECRET_KEY` | Секрет для подписей | `change_me` |
| `DATABASE_URL` | Строка подключения SQLAlchemy | `sqlite:////data/app.db` |
| `SESSION_TTL_MINUTES` | Время жизни сессии | `60` |
| `COOKIE_SECURE` | Флаг Secure у cookie | `true` |
| `COOKIE_SAMESITE` | SameSite у cookie | `lax` |
| `COOKIE_NAME` | Имя cookie сессии | `sid` |
| `CSRF_COOKIE_NAME` | Имя cookie CSRF (для API) | `csrf_token` |
| `CSRF_HEADER_NAME` | Имя заголовка CSRF (для API) | `X-CSRF-Token` |
| `FERNET_KEY_FILE` | Путь к ключу шифрования | `/run/secrets/fernet_key` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

---

## Разработка и отладка

### Просмотр логов

```bash
docker compose logs app --tail=100
docker compose logs nginx --tail=100
docker compose logs -f app
```

### Перезапуск после изменений в коде

```bash
docker compose up --build -d
```

Изменения в `app/` подхватятся только после пересборки образа `app`. `nginx.conf` подхватывается после пересоздания контейнера nginx:

```bash
docker compose up -d --force-recreate nginx
```

### Интерактивная оболочка в контейнере

```bash
docker compose exec app bash
```

### Работа с SQLite из контейнера

```bash
docker compose exec app python -c "
from app.db import SessionLocal
from app.models import User
from sqlalchemy import select
with SessionLocal() as db:
    for u in db.execute(select(User)).scalars():
        print(u.id, u.username, u.email, u.role, u.is_active)
"
```

### Полный сброс состояния

```bash
docker compose down
rm -f data/app.db data/app.db-wal data/app.db-shm
docker compose up --build -d
```

### Проверка конфигурации nginx

```bash
docker compose exec nginx nginx -t
```

---

## Частые проблемы

### 502 Bad Gateway

**Причина:** nginx стартовал раньше, чем app успел открыть порт. Nginx резолвит `app` через Docker DNS `127.0.0.11` в рантайме (см. `nginx.conf`), но если первый запрос пришёл до готовности app — будет 502.

**Решение:** в `docker-compose.yml` у сервиса `nginx` должен быть `depends_on: app: condition: service_healthy`, а у `app` — рабочий `healthcheck` (по умолчанию присутствует). Если 502 всё-таки появился при старте, подождать 5–10 секунд и повторить запрос.

### `Permission denied` при генерации сертификата (Fedora/SELinux)

Если `nginx/certs/` принадлежит root (например, от прошлых запусков через `sudo`):

```bash
sudo rm -rf nginx/certs
mkdir -p nginx/certs
```

Если SELinux в `Enforcing`:

```bash
getenforce
sudo setenforce 0   # только для учебного стенда
```

Либо корректно пометить контекст:

```bash
sudo semanage fcontext -a -t container_file_t "$PWD/nginx(/.*)?"
sudo restorecon -R nginx
```

### `NOT NULL constraint failed: sessions.user_id`

Схема БД старая. Пересоздать:

```bash
docker compose down
rm -f data/app.db data/app.db-wal data/app.db-shm
docker compose up --build -d
```

Убедиться, что используется bind-mount `./data:/data`, а не named volume — иначе удаление файла на хосте не влияет на контейнер.

### `can't compare offset-naive and offset-aware datetimes`

SQLite возвращает naive-datetime. В проекте для всех временных колонок используется `UTCDateTime` (TypeDecorator), который нормализует значения. Если ошибка всё-таки возникла — проверить, что в `app/models.py` нет `DateTime(timezone=True)` вне класса `UTCDateTime`.

### Порт 8443 занят

Проверить, кто слушает:

```bash
sudo ss -ltnp | grep -E '8443|8080'
```

Изменить публикуемые порты в `docker-compose.yml`:

```yaml
    ports:
      - "9443:8443"
      - "9080:8080"
```

Тогда приложение будет на https://localhost:9443.

---

## Остановка и очистка

### Остановить, но сохранить данные

```bash
docker compose stop
```

### Остановить и удалить контейнеры и сеть

```bash
docker compose down
```

### Полная очистка (контейнеры, сеть, named volumes)

```bash
docker compose down -v
```

### Полная очистка вместе с БД и секретами (вручную)

```bash
docker compose down -v
rm -rf data/app.db data/app.db-wal data/app.db-shm
rm -f secrets/fernet_key
rm -f nginx/certs/server.crt nginx/certs/server.key
```

> ⚠️ Удаление `secrets/fernet_key` делает ранее зашифрованные записи нерасшифровываемыми. Сделать бэкап перед удалением, если данные нужны.

---

## Лицензия и назначение

Проект создан исключительно в учебных целях в рамках лабораторной работы №2.1 по дисциплине «Анализ защищённости программных систем». Не предназначен для использования в промышленной эксплуатации без дополнительного аудита.
