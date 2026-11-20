"""Several migrators starting at once on an empty database, as API instances do on scale-out."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from lineage_db.migrate import MIGRATIONS, migrate

URL = os.environ.get("DATABASE_URL", "")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="DATABASE_URL is not set"),
]


def test_concurrent_migrators_all_succeed_and_apply_each_file_once() -> None:
    name = f"migrate_{uuid.uuid4().hex[:8]}"
    parts = urlsplit(URL)
    fresh = urlunsplit(parts._replace(path=f"/{name}"))
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    try:
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda _: migrate(fresh), range(4)))
        applied = sorted(n for r in results for n in r)
        assert applied == sorted(p.name for p in MIGRATIONS.glob("*.sql"))
    finally:
        with psycopg.connect(URL, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
