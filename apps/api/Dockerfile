FROM ghcr.io/astral-sh/uv:0.13.7 AS uv
FROM python:3.12.14-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /srv/apps/api
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev && apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./
COPY data /srv/data
COPY media /srv/media
RUN useradd --uid 10001 --create-home xiaoban
USER 10001
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
