# Multi-stage: uv installs deps into /app/.venv, then runtime image copies them in.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

FROM python:3.14-slim-bookworm

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 5005
CMD ["python", "app.py"]

# build:  docker buildx build --platform linux/amd64 -t fallsmap .
# tag:    docker tag fallsmap hants/fallsmap
# push:   docker push hants/fallsmap
# run:    docker run -p 5005:5005 --env-file .env fallsmap
