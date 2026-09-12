# Pin the runtime image so rebuilds are reproducible and do not silently move
# to a different Debian/Python image. Refresh this digest with each base-image
# security update.
FROM python:3.14.7-slim-bookworm@sha256:416f0db2a2b561945630cef9877a7ea0581b27449eb9fd9df42f03e1b74b5b63

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv==0.9.8

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY packages ./packages
COPY bot ./bot
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "python", "-m", "bot"]
