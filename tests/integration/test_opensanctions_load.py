import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from lineage_db.migrate import migrate
from lineage_ingest.opensanctions import load

URL = os.environ.get("DATABASE_URL", "")
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "opensanctions"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="DATABASE_URL is not set"),
]


@pytest.fixture(scope="module")
def conn() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    migrate(URL)
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("DELETE FROM source_records WHERE source = 'opensanctions'")
        load(URL, FIXTURES / "sanctions.csv", FIXTURES / "peps.csv", "test-1")
        yield c


def jurisdictions(conn: psycopg.Connection[tuple[object, ...]], key: str) -> object:
    row = conn.execute(
        "SELECT record->'jurisdictions' FROM source_records WHERE id = %s", (key,)
    ).fetchone()
    return None if row is None else row[0]


def test_only_pack_records_are_loaded(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    ids = {
        r[0] for r in conn.execute("SELECT id FROM source_records WHERE source = 'opensanctions'")
    }
    assert ids == {
        "opensanctions:sanctions:NK-test-uk-1",
        "opensanctions:sanctions:NK-test-uae-1",
        "opensanctions:sanctions:NK-test-both-1",
        "opensanctions:pep:Q-test-gb-1",
        "opensanctions:pep:Q-test-ae-1",
    }


def test_records_are_tagged_with_their_packs(
    conn: psycopg.Connection[tuple[object, ...]],
) -> None:
    assert jurisdictions(conn, "opensanctions:sanctions:NK-test-both-1") == ["uae", "uk"]
    assert jurisdictions(conn, "opensanctions:pep:Q-test-gb-1") == ["uk"]


def test_aliases_keep_every_script(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    row = conn.execute(
        "SELECT record->'aliases' FROM source_records "
        "WHERE id = 'opensanctions:sanctions:NK-test-uk-1'"
    ).fetchone()
    assert row is not None
    assert "Иван Тестов" in row[0]  # type: ignore[operator]


def test_reloading_the_same_version_changes_nothing(
    conn: psycopg.Connection[tuple[object, ...]],
) -> None:
    counts = load(URL, FIXTURES / "sanctions.csv", FIXTURES / "peps.csv", "test-1")
    assert counts["written"] == 0
    assert counts["unchanged"] == 5
