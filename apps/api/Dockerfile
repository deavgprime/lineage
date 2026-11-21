# syntax=docker/dockerfile:1
# Build from the repository root:
#   docker build -f apps/api/Dockerfile -t lineage-api .
# Base images are pinned by digest; Dependabot proposes updates.
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# Security updates published after the base image digest.
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY packages packages
COPY ingest ingest
COPY policies policies
COPY apps/api apps/api
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

RUN useradd --system --uid 10001 lineage
# A numeric user, so Kubernetes can check runAsNonRoot.
USER 10001
ENV PATH=/app/.venv/bin:$PATH
EXPOSE 8000
CMD ["sh", "-c", "python -m lineage_db.migrate && uvicorn --factory lineage_api.app:create_app --host 0.0.0.0 --port 8000 --no-access-log"]
