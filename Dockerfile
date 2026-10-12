FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.2.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Добавляем poetry в системный PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

# Минимальный набор системных зависимостей и установка Poetry
RUN apt update \
 && apt install -y --no-install-recommends \
    ca-certificates curl \
 && curl -sSL https://install.python-poetry.org | python3 - \
 && rm -rf /var/lib/apt/lists/*

# Создание непривилегированного пользователя
RUN groupadd -g 1000 app && useradd -m -u 1000 -g app app

WORKDIR /app

# Сначала копируем только файлы зависимостей для кэширования слоев
COPY pyproject.toml poetry.lock ./

# Установка зависимостей проекта (без разработки, если не нужны тесты в продакшн-образе)
RUN poetry install --no-root --without dev

# Копируем остальной код приложения
COPY app ./app

# Создание каталогов данных и секретов с правильными правами
RUN mkdir -p /data /run/secrets \
 && chown -R app:app /app /data /run/secrets

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]