from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from lineage_api.app import create_app
from lineage_api.auth import Verifier
from lineage_api.settings import Settings


class Pool:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy, self.opened, self.closed = healthy, False, False

    @contextmanager
    def connection(self, timeout: float | None = None) -> Any:
        if not self.healthy:
            raise OSError("connection refused")

        class Conn:
            def execute(self, sql: str) -> None:
                pass

        yield Conn()

    def open(self, wait: bool = False, timeout: float = 30.0) -> None:
        self.opened = True

    def close(self, timeout: float = 5.0) -> None:
        self.closed = True


def client(pool: Pool) -> TestClient:
    verifier = Verifier("issuer", "lineage-api", lambda _: None)
    return TestClient(create_app(Settings(database_url="postgresql://unused"), pool, verifier))


@pytest.mark.unit
def test_live_needs_nothing() -> None:
    with client(Pool(healthy=False)) as c:
        assert c.get("/health/live").json() == {"status": "ok"}


@pytest.mark.unit
def test_ready_checks_the_database() -> None:
    with client(Pool()) as c:
        assert c.get("/health/ready").status_code == 200
    with client(Pool(healthy=False)) as c:
        response = c.get("/health/ready")
        assert (response.status_code, response.json()) == (503, {"status": "unavailable"})


@pytest.mark.unit
def test_pool_opens_and_closes_with_the_app() -> None:
    pool = Pool()
    with client(pool):
        assert pool.opened
    assert pool.closed


@pytest.mark.unit
def test_settings_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("OIDC_ISSUER", raising=False)
    settings = Settings.from_env()
    assert settings.database_url == "postgresql://x"
    assert settings.jwks_url.endswith("/realms/lineage/protocol/openid-connect/certs")
