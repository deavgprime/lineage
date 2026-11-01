"""Open cases, run the agent in the background, and serve the queue and the drafted file.

Every query runs as the signed-in user (see db.as_user), so row-level security decides what each
user sees. The API also checks role and pack itself, so either layer alone stops a leak.
"""

import json
import logging
import re
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from lineage_agent.agent import Result
from pydantic import BaseModel, Field

from lineage_api.auth import CurrentUser, User
from lineage_api.db import as_user

log = logging.getLogger("lineage_api")
router = APIRouter(prefix="/cases", tags=["cases"])

Status = Literal["drafting", "draft", "awaiting_mlro", "final", "failed"]
Audit = Callable[[str, dict[str, Any]], None]
# Runs the agent for (company number, pack), writing each step through the audit callback.
Runner = Callable[[str, str, Audit], Result]

COMPANY_NUMBER = re.compile(r"^[A-Z0-9]{8}$")


class OpenCase(BaseModel):
    company_number: str = Field(pattern=COMPANY_NUMBER.pattern)
    jurisdiction: Literal["uk", "uae"]


class CaseSummary(BaseModel):
    id: uuid.UUID
    jurisdiction: str
    subject: str
    company_number: str | None
    status: Status
    assigned_to: str
    rating: str | None
    created_at: datetime
    updated_at: datetime


class CaseFile(CaseSummary):
    draft: dict[str, Any] | None
    evidence: list[dict[str, str]]
    alerts: list[str]
    minimum_rating: str | None
    attempts: int | None
    citation_failures: list[str]
    sign_offs: list["SignOffRecord"]


class SignOffRecord(BaseModel):
    stage: Literal["first", "second"]
    signer: str
    signer_name: str
    role: Literal["analyst", "mlro"]
    at: datetime
    drafted_rating: str
    rating: str
    reason: str | None
    alert_notes: dict[str, str]


CaseFile.model_rebuild()


class AuditRow(BaseModel):
    seq: int
    at: datetime
    actor: str
    action: str
    payload: dict[str, Any]
    prev_hash: str
    row_hash: str


SUMMARY = """
SELECT c.id, c.jurisdiction, c.subject, c.company_number, c.status, c.assigned_to,
       coalesce(c.rating, d.draft ->> 'risk_rating'), c.created_at, c.updated_at
FROM cases c
LEFT JOIN LATERAL (
    SELECT draft FROM drafts WHERE case_id = c.id ORDER BY id DESC LIMIT 1
) d ON true
"""


def _summary(row: tuple[Any, ...]) -> CaseSummary:
    keys = CaseSummary.model_fields.keys()
    return CaseSummary(**dict(zip(keys, row, strict=True)))


def _audit_row(conn: Any, case_id: uuid.UUID, actor: str, action: str, payload: object) -> None:
    conn.execute(
        "INSERT INTO audit_log (case_id, actor, action, payload, prev_hash, row_hash) "
        "VALUES (%s, %s, %s, %s, '', '')",
        (case_id, actor, action, json.dumps(payload)),
    )


def subject_of(result: Result, number: str) -> str:
    """The company's own name from its register record. Parents in the chain have records too, so
    match on the case's number. Falls back to the LEI name, then to the number itself."""
    for record in result.evidence:
        if record["source_id"] == f"companies-house:company:{number}":
            return record["text"].removeprefix("Company ").split(", number")[0]
    for record in result.evidence:
        if record["source_id"].startswith("gleif:") and record["source_id"].count(":") == 1:
            return record["text"].split("Legal name: ", 1)[-1].split(". Registered", 1)[0]
    return number


def run_case(
    pool: Any, runner: Runner, user: User, case_id: uuid.UUID, number: str, pack: str
) -> None:
    """Run the agent for a case and store the draft. Each audit row commits on its own, so the
    log keeps every step even if the run fails part way."""

    def audit(action: str, payload: dict[str, Any]) -> None:
        with as_user(pool, user) as conn:
            _audit_row(conn, case_id, "agent", action, payload)

    try:
        result = runner(number, pack, audit)
    except Exception as error:
        log.exception("agent run failed", extra={"fields": {"case_id": str(case_id)}})
        with as_user(pool, user) as conn:
            _audit_row(conn, case_id, "agent", "failed", {"error": type(error).__name__})
            conn.execute(
                "UPDATE cases SET status = 'failed', updated_at = now() WHERE id = %s", (case_id,)
            )
        return
    with as_user(pool, user) as conn:
        subject = subject_of(result, number)
        conn.execute(
            "INSERT INTO drafts (case_id, draft, evidence, alerts, minimum_rating, attempts, "
            "citation_failures) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                case_id,
                result.draft.model_dump_json() if result.draft else None,
                json.dumps(result.evidence),
                json.dumps(result.alerts),
                result.minimum_rating,
                result.attempts,
                json.dumps(result.citation_failures),
            ),
        )
        outcome = "draft" if result.draft and not result.citation_failures else "failed"
        conn.execute(
            "UPDATE cases SET status = %s, subject = %s, updated_at = now() WHERE id = %s",
            (outcome, subject, case_id),
        )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def open_case(
    body: OpenCase, user: CurrentUser, request: Request, background: BackgroundTasks
) -> CaseSummary:
    if user.role not in ("analyst", "mlro"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this role cannot open cases")
    if body.jurisdiction not in user.packs:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your pack")
    pool = request.app.state.db
    with as_user(pool, user) as conn:
        row = conn.execute(
            "INSERT INTO cases (jurisdiction, subject, company_number, status, assigned_to, "
            "opened_by) VALUES (%s, %s, %s, 'drafting', %s, %s) RETURNING id",
            (body.jurisdiction, body.company_number, body.company_number, user.id, user.id),
        ).fetchone()
        if row is None:
            raise RuntimeError("the case was not created")
        case_id = row[0]
        _audit_row(conn, case_id, user.id, "case_opened", body.model_dump())
        summary = _summary(_visible(conn, case_id))
    background.add_task(
        run_case,
        pool,
        request.app.state.runner,
        user,
        case_id,
        body.company_number,
        body.jurisdiction,
    )
    return summary


@router.get("")
def queue(
    user: CurrentUser,
    request: Request,
    status_filter: Annotated[Status | None, Query(alias="status")] = None,
) -> list[CaseSummary]:
    with as_user(request.app.state.db, user) as conn:
        if status_filter:
            rows = conn.execute(
                SUMMARY + " WHERE c.status = %s ORDER BY c.created_at DESC", (status_filter,)
            )
        else:
            rows = conn.execute(SUMMARY + " ORDER BY c.created_at DESC")
        return [_summary(r) for r in rows]


def _visible(conn: Any, case_id: uuid.UUID) -> tuple[Any, ...]:
    row = conn.execute(SUMMARY + " WHERE c.id = %s", (case_id,)).fetchone()
    if row is None:
        # Not found and not allowed look the same, so ids cannot be probed.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such case")
    return tuple(row)


@router.get("/{case_id}")
def case_file(case_id: uuid.UUID, user: CurrentUser, request: Request) -> CaseFile:
    with as_user(request.app.state.db, user) as conn:
        summary = _summary(_visible(conn, case_id))
        row = conn.execute(
            "SELECT draft, evidence, alerts, minimum_rating, attempts, citation_failures "
            "FROM drafts WHERE case_id = %s ORDER BY id DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        signed = conn.execute(
            "SELECT stage, signer, coalesce(signer_name, signer), signer_role, at, drafted_rating, "
            "rating, reason, alert_notes "
            "FROM sign_offs WHERE case_id = %s ORDER BY id",
            (case_id,),
        )
        sign_offs = [
            SignOffRecord(**dict(zip(SignOffRecord.model_fields, r, strict=True))) for r in signed
        ]
    draft, evidence, alerts, floor, attempts, failures = row or (None, [], [], None, None, [])
    return CaseFile(
        **summary.model_dump(),
        draft=draft,
        evidence=evidence,
        alerts=alerts,
        minimum_rating=floor,
        attempts=attempts,
        citation_failures=failures,
        sign_offs=sign_offs,
    )


@router.get("/{case_id}/audit")
def audit_trail(case_id: uuid.UUID, user: CurrentUser, request: Request) -> list[AuditRow]:
    with as_user(request.app.state.db, user) as conn:
        _visible(conn, case_id)
        rows = conn.execute(
            "SELECT seq, at, actor, action, payload, prev_hash, row_hash FROM audit_log "
            "WHERE case_id = %s ORDER BY seq",
            (case_id,),
        )
        keys = AuditRow.model_fields.keys()
        return [AuditRow(**dict(zip(keys, r, strict=True))) for r in rows]
