"""Build the FastAPI app.

uvicorn --factory lineage_api.app:create_app
"""

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Protocol

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from psycopg_pool import ConnectionPool

from lineage_api.logs import configure
from lineage_api.settings import Settings

log = logging.getLogger("lineage_api")


class Pool(Protocol):
    def connection(self, timeout: float | None = None) -> Any: ...
    def open(self, wait: bool = False, timeout: float = 30.0) -> None: ...
    def close(self, timeout: float = 5.0) -> None: ...


def create_app(settings: Settings | None = None, pool: Pool | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure(settings.log_level)
    db: Pool = pool or ConnectionPool(settings.database_url, min_size=1, max_size=10, open=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db.open()
        yield
        db.close()

    app = FastAPI(title="Lineage API", version="0.4.0", lifespan=lifespan)
    app.state.db = db

    @app.middleware("http")
    async def access_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.monotonic()
        response = await call_next(request)
        fields = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": round((time.monotonic() - started) * 1000, 1),
        }
        log.info("request", extra={"fields": fields})
        return response

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", response_model=None)
    def ready() -> dict[str, str] | JSONResponse:
        try:
            with db.connection(timeout=2) as conn:
                conn.execute("SELECT 1")
        except Exception:
            log.exception("database not ready")
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ok"}

    return app
