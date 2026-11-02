"""Shared helpers for the API integration tests: signed test tokens and an app on Postgres."""

import os
import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from lineage_api.app import create_app
from lineage_api.auth import Verifier
from lineage_api.settings import Settings
from psycopg_pool import ConnectionPool

URL = os.environ.get("DATABASE_URL", "")
ISSUER = "http://localhost:8080/realms/lineage"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
RUN = uuid.uuid4().hex[:8]


def headers(user: str, role: str, packs: list[str]) -> dict[str, str]:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": "lineage-api",
        "sub": f"{user}-{RUN}",
        "preferred_username": user,
        "iat": now,
        "exp": now + 300,
        "roles": [role],
        "packs": packs,
    }
    return {"Authorization": f"Bearer {jwt.encode(claims, KEY, algorithm='RS256')}"}


ANALYST_1 = headers("analyst-uk-1", "analyst", ["uk"])
ANALYST_2 = headers("analyst-uk-2", "analyst", ["uk"])
MLRO = headers("mlro-uk-1", "mlro", ["uk"])
AUDITOR = headers("auditor-1", "auditor", ["uk", "uae"])


MLRO_2 = headers("mlro-uk-2", "mlro", ["uk"])


def app(runner: Any, asker: Any = None) -> TestClient:
    pool = ConnectionPool(URL, min_size=1, max_size=4, open=False)
    verifier = Verifier(ISSUER, "lineage-api", lambda _: KEY.public_key())
    return TestClient(create_app(Settings(database_url=URL), pool, verifier, runner, asker))
