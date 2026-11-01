import os
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from lineage_db.migrate import migrate

URL = os.environ.get("DATABASE_URL", "")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="DATABASE_URL is not set"),
]


@pytest.fixture(scope="module")
def conn() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    migrate(URL)
    with psycopg.connect(URL, autocommit=True) as c:
        yield c


def add_case(conn: psycopg.Connection[tuple[object, ...]]) -> uuid.UUID:
    row = conn.execute(
        "INSERT INTO cases (jurisdiction, subject, assigned_to) VALUES ('uk', 'Test Ltd', 'a1') "
        "RETURNING id"
    ).fetchone()
    assert row is not None
    case_id = row[0]
    assert isinstance(case_id, uuid.UUID)
    return case_id


def log(conn: psycopg.Connection[tuple[object, ...]], case_id: uuid.UUID, action: str) -> None:
    conn.execute(
        "INSERT INTO audit_log (case_id, actor, action, payload, prev_hash, row_hash) "
        "VALUES (%s, 'agent', %s, '{}', '', '')",
        (case_id, action),
    )


def test_migrations_are_idempotent() -> None:
    migrate(URL)
    assert migrate(URL) == []


def test_pgvector_is_installed(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    assert conn.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'").fetchone()


def test_audit_rows_chain_to_their_predecessor(
    conn: psycopg.Connection[tuple[object, ...]],
) -> None:
    case_id = add_case(conn)
    log(conn, case_id, "tool_call")
    log(conn, case_id, "model_call")
    rows = conn.execute(
        "SELECT prev_hash, row_hash FROM audit_log ORDER BY seq DESC LIMIT 2"
    ).fetchall()
    newest, previous = rows
    assert newest[0] == previous[1]
    assert len(str(newest[1])) == 64


@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_log SET actor = 'someone'", "DELETE FROM audit_log", "TRUNCATE audit_log"],
)
def test_audit_log_rejects_changes(
    conn: psycopg.Connection[tuple[object, ...]], statement: str
) -> None:
    log(conn, add_case(conn), "decision")
    with pytest.raises(psycopg.errors.RaiseException, match="append only"):
        conn.execute(statement)


def test_case_status_is_restricted(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    case_id = add_case(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("UPDATE cases SET status = 'approved' WHERE id = %s", (case_id,))
