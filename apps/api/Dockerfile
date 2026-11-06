# syntax=docker/dockerfile:1
# Build from the repository root:
#   docker build -f apps/api/Dockerfile -t lineage-api .
# Base images are pinned by digest; Dependabot proposes updates.
FROM python:3.12-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54 AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

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
