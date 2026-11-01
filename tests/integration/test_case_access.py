"""Row-level security on cases and the audit log, queried directly as the API's role."""

import os
import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from lineage_api.auth import User
from lineage_api.db import as_user
from lineage_db.migrate import migrate
from psycopg_pool import ConnectionPool

URL = os.environ.get("DATABASE_URL", "")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="DATABASE_URL is not set"),
]

RUN = uuid.uuid4().hex[:8]
ANALYST_1 = User(f"a1-{RUN}", "analyst-uk-1", "analyst", frozenset({"uk"}))
ANALYST_2 = User(f"a2-{RUN}", "analyst-uk-2", "analyst", frozenset({"uk"}))
UAE_ANALYST = User(f"a3-{RUN}", "analyst-uae-1", "analyst", frozenset({"uae"}))
MLRO = User(f"m1-{RUN}", "mlro-uk-1", "mlro", frozenset({"uk"}))
AUDITOR = User(f"x1-{RUN}", "auditor-1", "auditor", frozenset({"uk", "uae"}))


@pytest.fixture(scope="module")
def pool() -> Iterator[ConnectionPool[Any]]:
    migrate(URL)
    with ConnectionPool(URL, min_size=1, max_size=2) as p:
        yield p


@pytest.fixture(scope="module")
def cases(pool: ConnectionPool[Any]) -> dict[str, uuid.UUID]:
    opened = {}
    for user, subject in [(ANALYST_1, "One Ltd"), (ANALYST_2, "Two Ltd")]:
        with as_user(pool, user) as conn:
            row = conn.execute(
                "INSERT INTO cases (jurisdiction, subject, assigned_to, opened_by) "
                "VALUES ('uk', %s, %s, %s) RETURNING id",
                (subject, user.id, user.id),
            ).fetchone()
            assert row is not None
            conn.execute(
                "INSERT INTO audit_log (case_id, actor, action, payload, prev_hash, row_hash) "
                "VALUES (%s, %s, 'opened', '{}', '', '')",
                (row[0], user.id),
            )
            opened[user.id] = row[0]
    return opened


def visible(pool: ConnectionPool[Any], user: User, table: str = "cases") -> set[uuid.UUID]:
    column = "id" if table == "cases" else "case_id"
    with as_user(pool, user) as conn:
        return {r[0] for r in conn.execute(f"SELECT {column} FROM {table}")}


def test_an_analyst_sees_only_their_own_cases(
    pool: ConnectionPool[Any], cases: dict[str, uuid.UUID]
) -> None:
    mine, theirs = cases[ANALYST_1.id], cases[ANALYST_2.id]
    assert mine in visible(pool, ANALYST_1)
    assert theirs not in visible(pool, ANALYST_1)
    assert theirs not in visible(pool, ANALYST_1, "audit_log")
    with as_user(pool, ANALYST_1) as conn:
        assert conn.execute("SELECT 1 FROM cases WHERE id = %s", (theirs,)).fetchone() is None


def test_an_analyst_cannot_change_or_log_against_another_case(
    pool: ConnectionPool[Any], cases: dict[str, uuid.UUID]
) -> None:
    theirs = cases[ANALYST_2.id]
    with as_user(pool, ANALYST_1) as conn:
        changed = conn.execute(
            "UPDATE cases SET status = 'final' WHERE id = %s", (theirs,)
        ).rowcount
        assert changed == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege), as_user(pool, ANALYST_1) as conn:
        conn.execute(
            "INSERT INTO audit_log (case_id, actor, action, payload, prev_hash, row_hash) "
            "VALUES (%s, 'x', 'sign_off', '{}', '', '')",
            (theirs,),
        )


def test_an_analyst_cannot_open_a_case_for_someone_else_or_another_pack(
    pool: ConnectionPool[Any],
) -> None:
    for jurisdiction, assignee in [("uk", ANALYST_2.id), ("uae", ANALYST_1.id)]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), as_user(pool, ANALYST_1) as conn:
            conn.execute(
                "INSERT INTO cases (jurisdiction, subject, assigned_to, opened_by) "
                "VALUES (%s, 'X Ltd', %s, %s)",
                (jurisdiction, assignee, ANALYST_1.id),
            )


def test_other_packs_are_invisible(pool: ConnectionPool[Any], cases: dict[str, uuid.UUID]) -> None:
    assert not set(cases.values()) & visible(pool, UAE_ANALYST)


def test_an_mlro_sees_every_case_in_their_pack(
    pool: ConnectionPool[Any], cases: dict[str, uuid.UUID]
) -> None:
    assert set(cases.values()) <= visible(pool, MLRO)
    assert set(cases.values()) <= visible(pool, MLRO, "audit_log")


def test_an_auditor_reads_everything_and_changes_nothing(
    pool: ConnectionPool[Any], cases: dict[str, uuid.UUID]
) -> None:
    assert set(cases.values()) <= visible(pool, AUDITOR)
    with as_user(pool, AUDITOR) as conn:
        changed = conn.execute(
            "UPDATE cases SET status = 'final' WHERE id = ANY(%s)", (list(cases.values()),)
        ).rowcount
        assert changed == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege), as_user(pool, AUDITOR) as conn:
        conn.execute(
            "INSERT INTO audit_log (case_id, actor, action, payload, prev_hash, row_hash) "
            "VALUES (%s, 'x', 'note', '{}', '', '')",
            (cases[ANALYST_1.id],),
        )


def test_without_a_user_nothing_is_visible(
    pool: ConnectionPool[Any], cases: dict[str, uuid.UUID]
) -> None:
    with pool.connection() as conn, conn.transaction():
        conn.execute("SET LOCAL ROLE lineage_app")
        assert conn.execute("SELECT count(*) FROM cases").fetchone() == (0,)


def test_settings_do_not_leak_to_the_next_transaction(
    pool: ConnectionPool[Any], cases: dict[str, uuid.UUID]
) -> None:
    visible(pool, MLRO)
    with pool.connection() as conn:
        row = conn.execute("SELECT current_user, lineage_user_id()").fetchone()
        assert row is not None and row[1] is None and row[0] != "lineage_app"


def test_the_audit_chain_links_across_cases_a_user_cannot_see(
    pool: ConnectionPool[Any], cases: dict[str, uuid.UUID]
) -> None:
    with as_user(pool, ANALYST_1) as conn:
        conn.execute(
            "INSERT INTO audit_log (case_id, actor, action, payload, prev_hash, row_hash) "
            "VALUES (%s, %s, 'note', '{}', '', '')",
            (cases[ANALYST_1.id], ANALYST_1.id),
        )
    with psycopg.connect(URL) as owner:
        rows = owner.execute(
            "SELECT prev_hash, row_hash FROM audit_log ORDER BY seq DESC LIMIT 2"
        ).fetchall()
    newest, previous = rows
    assert newest[0] == previous[1]
