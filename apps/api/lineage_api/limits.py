"""Limits on work that costs money or holds a worker: drafting a case and answering a question.

Counts come from the database, so the limits hold across every API instance. Exceeding one returns
429 with Retry-After, and the refusal is logged without anything the user sent.
"""

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status

log = logging.getLogger("lineage_api")
WINDOW_SECONDS = 3600
# A draft takes seconds, or a few minutes with retries. Longer than this, the process running it
# has stopped, so the case is failed and its capacity freed (#149).
STALE_DRAFT_SECONDS = 900


def fail_stale_drafts(conn: Any) -> int:
    (n,) = conn.execute("SELECT lineage_fail_stale_drafts(%s)", (STALE_DRAFT_SECONDS,)).fetchone()
    if n:
        log.warning("failed stale drafting cases", extra={"fields": {"cases": n}})
    return int(n)


@dataclass(frozen=True)
class Limits:
    cases_per_hour: int = 20
    drafting_per_user: int = 3
    drafting_total: int = 10
    questions_per_hour: int = 30


def _serialise(conn: Any) -> None:
    """One check at a time per user, held until the transaction ends, so two requests sent together
    cannot both pass a limit before either is counted."""
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('lineage-limit:' || lineage_user_id()))")


def _refuse(what: str, retry_after: int) -> HTTPException:
    log.info("limit reached", extra={"fields": {"limit": what}})
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        f"limit reached: {what}",
        {"Retry-After": str(retry_after)},
    )


def check_open_case(conn: Any, limits: Limits, counting_new_case: bool = True) -> None:
    """Refuse a new case if the user, or everyone together, already has too much running."""
    _serialise(conn)
    fail_stale_drafts(conn)
    opened, drafting, _ = conn.execute(
        "SELECT * FROM lineage_user_usage(%s)", (WINDOW_SECONDS,)
    ).fetchone()
    if counting_new_case and opened >= limits.cases_per_hour:
        raise _refuse(f"{limits.cases_per_hour} cases an hour", WINDOW_SECONDS)
    if drafting >= limits.drafting_per_user:
        raise _refuse(f"{limits.drafting_per_user} cases drafting at once", 60)
    (total,) = conn.execute("SELECT lineage_drafting_now()").fetchone()
    if total >= limits.drafting_total:
        raise _refuse("drafting capacity, try again shortly", 60)


def check_question(conn: Any, limits: Limits) -> None:
    _serialise(conn)
    _, _, asked = conn.execute("SELECT * FROM lineage_user_usage(%s)", (WINDOW_SECONDS,)).fetchone()
    if asked >= limits.questions_per_hour:
        raise _refuse(f"{limits.questions_per_hour} policy questions an hour", WINDOW_SECONDS)
