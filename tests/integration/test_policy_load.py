"""Loading the policy corpus into Postgres, with a stand-in embedder."""

import os
import uuid
from collections.abc import Iterator, Sequence
from typing import Any

import psycopg
import pytest
from lineage_api.auth import User
from lineage_api.db import as_user
from lineage_db.migrate import migrate
from lineage_ingest.policy import DIMENSIONS, Document, Section, load
from psycopg_pool import ConnectionPool

URL = os.environ.get("DATABASE_URL", "")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="DATABASE_URL is not set"),
]
RUN = uuid.uuid4().hex[:8]


class Counting:
    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += len(texts)
        return [[float(len(t) % 7 + 1)] + [0.0] * (DIMENSIONS - 1) for t in texts]


def document(pack: str, text: str = "Verify every beneficial owner.") -> Document:
    return Document(
        id=f"test-{pack}-{RUN}",
        pack=pack,
        title=f"Test policy {pack}",
        source="test",
        version="1",
        licence="test",
        url=None,
        sections=(
            Section("T 1.1", "Scope", "Applies to companies."),
            Section("T 1.2", "Owners", text),
        ),
    )


@pytest.fixture(scope="module")
def conn() -> Iterator[psycopg.Connection[Any]]:
    migrate(URL)
    with psycopg.connect(URL, autocommit=True) as c:
        yield c
        c.execute("DELETE FROM policy_documents WHERE id LIKE %s", (f"test-%-{RUN}",))


def test_reloading_changes_nothing_and_an_edit_reembeds_one_section(
    conn: psycopg.Connection[Any],
) -> None:
    embedder = Counting()
    assert load(conn, document("uk"), embedder)["written"] == 2
    assert load(conn, document("uk"), embedder) == {"written": 0, "unchanged": 2, "removed": 0}
    assert load(conn, document("uk", "Verify owners."), embedder)["written"] == 1
    assert embedder.calls == 3


def test_full_text_search_finds_a_section(conn: psycopg.Connection[Any]) -> None:
    load(conn, document("uk"), Counting())
    row = conn.execute(
        "SELECT ref FROM policy_sections WHERE document_id = %s "
        "AND search @@ websearch_to_tsquery('english', 'beneficial owners')",
        (f"test-uk-{RUN}",),
    ).fetchone()
    assert row == ("T 1.2",)


def test_users_see_only_their_packs_corpus(conn: psycopg.Connection[Any]) -> None:
    load(conn, document("uk"), Counting())
    load(conn, document("uae"), Counting())
    with ConnectionPool(URL, min_size=1, max_size=1) as pool:
        for packs, visible in [
            ({"uk"}, {"uk"}),
            ({"uae"}, {"uae"}),
            ({"uk", "uae"}, {"uk", "uae"}),
        ]:
            user = User(f"u-{RUN}", "tester", "analyst", frozenset(packs))
            with as_user(pool, user) as c:
                rows = c.execute(
                    "SELECT DISTINCT pack FROM policy_sections WHERE document_id LIKE %s",
                    (f"test-%-{RUN}",),
                ).fetchall()
            assert {r[0] for r in rows} == visible
