"""Sign off a drafted file, or override its rating, with the rules from decision 0003.

The API checks each rule and says which one failed. The database checks the ones that matter most
again (migration 0005), so a file cannot become final by any other route.
"""

import json
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from lineage_api.auth import CurrentUser
from lineage_api.cases import CaseFile, _audit_row, _visible, case_file
from lineage_api.db import as_user

router = APIRouter(prefix="/cases", tags=["sign-off"])

Rating = Literal["low", "medium", "high"]


class SignOff(BaseModel):
    rating: Rating
    reason: str | None = Field(default=None, max_length=4000)
    # One note per weak screening alert, keyed by the alert as the file lists it.
    alert_notes: dict[str, str] = Field(default_factory=dict)


def _refuse(reason: str, code: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(code, reason)


@router.post("/{case_id}/sign-off")
def sign_off(case_id: uuid.UUID, body: SignOff, user: CurrentUser, request: Request) -> CaseFile:
    if user.role not in ("analyst", "mlro"):
        raise _refuse("this role cannot sign off", status.HTTP_403_FORBIDDEN)
    pool = request.app.state.db
    with as_user(pool, user) as conn:
        _visible(conn, case_id)
        row = conn.execute(
            "SELECT c.status, c.assigned_to, d.id, d.draft ->> 'risk_rating', d.alerts "
            "FROM cases c JOIN LATERAL (SELECT * FROM drafts WHERE case_id = c.id "
            "ORDER BY id DESC LIMIT 1) d ON true WHERE c.id = %s FOR UPDATE OF c",
            (case_id,),
        ).fetchone()
        if row is None:
            raise _refuse("the case has no draft to sign off")
        case_status, assigned_to, draft_id, drafted, alerts = row
        reason = (body.reason or "").strip() or None

        if case_status == "draft":
            stage = "first"
            if user.role == "analyst" and assigned_to != user.id:
                raise _refuse("only the assigned analyst can sign off", status.HTTP_403_FORBIDDEN)
            missing = [a for a in alerts if not body.alert_notes.get(a, "").strip()]
            if missing:
                raise _refuse(f"clear every alert with a note first: {missing}")
            basis = drafted
        elif case_status == "awaiting_mlro":
            stage = "second"
            first = conn.execute(
                "SELECT signer, rating FROM sign_offs WHERE case_id = %s AND draft_id = %s "
                "AND stage = 'first'",
                (case_id, draft_id),
            ).fetchone()
            if user.role != "mlro":
                raise _refuse("a high-rated file needs an MLRO", status.HTTP_403_FORBIDDEN)
            if first is None or first[0] == user.id:
                raise _refuse("the second sign-off must come from a different person")
            basis = first[1]
        else:
            raise _refuse(f"a {case_status} case cannot be signed off")

        if body.rating != basis and not reason:
            raise _refuse(
                "changing the rating needs a reason", status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        conn.execute(
            "INSERT INTO sign_offs (case_id, draft_id, signer, signer_role, stage, "
            "drafted_rating, rating, reason, alert_notes) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                case_id,
                draft_id,
                user.id,
                user.role,
                stage,
                basis,
                body.rating,
                reason,
                json.dumps(body.alert_notes),
            ),
        )
        outcome = "awaiting_mlro" if stage == "first" and body.rating == "high" else "final"
        conn.execute(
            "UPDATE cases SET status = %s, rating = %s, updated_at = now() WHERE id = %s",
            (outcome, body.rating, case_id),
        )
        _audit_row(
            conn,
            case_id,
            user.id,
            "sign_off",
            {
                "stage": stage,
                "role": user.role,
                "rating": body.rating,
                "changed_from": basis if body.rating != basis else None,
                "reason": reason,
                "alerts_cleared": sorted(body.alert_notes),
                "status": outcome,
            },
        )
    return case_file(case_id, user, request)
