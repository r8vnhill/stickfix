# Stickfix runtime image: the locked, runtime-only environment for `bot` and `migrate`
# (docker-compose.yml). Contracts: tests/architecture/test_container_contract.py (static) and the
# `container` job in .github/workflows/ci.yml (build + offline smoke probe).

# Pin the base image by digest so rebuilds do not silently move to another Debian/Python image.
# Refresh the digest with each base-image security update.
ARG PYTHON_IMAGE=python:3.14.7-slim-bookworm
ARG PYTHON_DIGEST=sha256:416f0db2a2b561945630cef9877a7ea0581b27449eb9fd9df42f03e1b74b5b63
FROM ${PYTHON_IMAGE}@${PYTHON_DIGEST}

# Security updates make rebuilds differ over time: dependency selection is reproducible through
# uv.lock, but the image is not byte-for-byte reproducible.
RUN apt-get update \
  && apt-get upgrade -y \
  && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

# Must equal setup-uv in ci.yml and UV_VERSION in tests/architecture/package_contract_support.py.
RUN pip install --no-cache-dir uv==0.12.7

# Copy every source the root distribution builds from. imghdr.py is a [tool.setuptools]
# py-module: PTB 13 imports imghdr, which Python 3.14 no longer ships.
WORKDIR /app
COPY pyproject.toml uv.lock README.md imghdr.py alembic.ini ./
COPY packages ./packages
COPY bot ./bot
COPY alembic ./alembic

# --locked fails the build if uv.lock is stale; --no-dev keeps test and lint tools out.
RUN uv sync --locked --no-dev

# The environment is now complete. Stop `uv run` (bot CMD and compose `migrate`) from re-syncing
# it at startup, which would install the default dev group and need network access.
ENV UV_NO_SYNC=1

# Unchanged until Milestone 4.6 deliberately replaces the `bot.*` entrypoint.
CMD ["uv", "run", "python", "-m", "bot"]
