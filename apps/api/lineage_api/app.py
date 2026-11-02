"""Build the FastAPI app.

uvicorn --factory lineage_api.app:create_app
"""

import logging
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Protocol

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from lineage_api.auth import CurrentUser, Role, Verifier
from lineage_api.cases import Runner, router
from lineage_api.logs import configure
from lineage_api.policy import Asker
from lineage_api.policy import router as policy_router
from lineage_api.settings import Settings
from lineage_api.sign_off import router as sign_off_router

log = logging.getLogger("lineage_api")


class Me(BaseModel):
    id: str
    username: str
    role: Role
    packs: list[str]


class Pool(Protocol):
    def connection(self, timeout: float | None = None) -> Any: ...
    def open(self, wait: bool = False, timeout: float = 30.0) -> None: ...
    def close(self, timeout: float = 5.0) -> None: ...


def create_app(
    settings: Settings | None = None,
    pool: Pool | None = None,
    verifier: Verifier | None = None,
    runner: Runner | None = None,
    asker: Asker | None = None,
) -> FastAPI:
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
    app.state.log = log
    if runner is None:
        from lineage_api.runner import FixtureRunner, LiveRunner

        runner = (
            FixtureRunner()
            if os.environ.get("LINEAGE_RUNNER") == "fixture"
            else LiveRunner(settings.database_url)
        )
        if isinstance(runner, FixtureRunner):
            log.warning("drafting with fixtures: LINEAGE_RUNNER=fixture is for end-to-end tests")
    app.state.runner = runner
    if asker is None:
        from lineage_api.runner import FixtureAsker, LiveAsker

        fixture = os.environ.get("LINEAGE_RUNNER") == "fixture"
        asker = FixtureAsker() if fixture else LiveAsker()
    app.state.asker = asker
    app.state.verifier = verifier or Verifier.from_jwks(
        settings.oidc_issuer, settings.oidc_audience, settings.jwks_url
    )

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

    @app.get("/me")
    def me(user: CurrentUser) -> Me:
        return Me(id=user.id, username=user.username, role=user.role, packs=sorted(user.packs))

    app.include_router(router)
    app.include_router(sign_off_router)
    app.include_router(policy_router)
    return app
