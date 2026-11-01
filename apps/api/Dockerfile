# Build from the repository root:
#   docker build -f apps/api/Dockerfile -t lineage-api .
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY packages packages
COPY ingest ingest
COPY apps/api apps/api
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 lineage
USER lineage
ENV PATH=/app/.venv/bin:$PATH
EXPOSE 8000
CMD ["sh", "-c", "python -m lineage_db.migrate && uvicorn --factory lineage_api.app:create_app --host 0.0.0.0 --port 8000 --no-access-log"]
