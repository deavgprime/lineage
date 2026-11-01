import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from lineage_agent.tools.screening import screen
from lineage_db.migrate import migrate
from lineage_ingest.opensanctions import load

URL = os.environ.get("DATABASE_URL", "")
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "opensanctions"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="DATABASE_URL is not set"),
]
UK_PERSON = "opensanctions:sanctions:NK-test-uk-1"


@pytest.fixture(scope="module")
def conn() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    migrate(URL)
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("DELETE FROM source_records WHERE source = 'opensanctions'")
        load(URL, FIXTURES / "sanctions.csv", FIXTURES / "peps.csv", "test-1")
        yield c


def ids(conn: psycopg.Connection[tuple[object, ...]], name: str, pack: str) -> list[str]:
    return [c.record_id for c in screen(conn, name, pack)]


def test_exact_name_matches(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    [hit] = screen(conn, "Ivan Testov", "uk")
    assert (hit.record_id, hit.rule, hit.score) == (UK_PERSON, "exact", 1.0)


def test_word_order_and_punctuation_do_not_matter(
    conn: psycopg.Connection[tuple[object, ...]],
) -> None:
    [hit] = screen(conn, "Testov, Ivan", "uk")
    assert hit.record_id == UK_PERSON
    assert hit.rule in {"exact", "word_order"}


def test_cyrillic_alias_matches(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    assert ids(conn, "Иван Тестов", "uk") == [UK_PERSON]


def test_close_spelling_matches(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    [hit] = screen(conn, "Ivan Testoff", "uk")
    assert hit.record_id == UK_PERSON
    assert hit.rule == "similar"


def test_results_are_limited_to_the_pack(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    assert ids(conn, "Ivan Testov", "uae") == []
    assert ids(conn, "Sample Trading LLC", "uae") == ["opensanctions:sanctions:NK-test-uae-1"]


def test_unrelated_and_empty_names_return_nothing(
    conn: psycopg.Connection[tuple[object, ...]],
) -> None:
    assert ids(conn, "Harbourline Logistics Ltd", "uk") == []
    assert ids(conn, " , ", "uk") == []
