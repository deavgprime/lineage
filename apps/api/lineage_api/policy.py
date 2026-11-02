"""Policy questions: ask in your pack, read your history.

Answers come from the pack's corpus only, through lineage_agent.policy_qa. Every question, the
passages found, each model call and the answer are written to the audit log, and the full record is
kept in policy_questions.
"""

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from lineage_agent.policy_qa import Answer
from pydantic import BaseModel, Field

from lineage_api.auth import CurrentUser, User
from lineage_api.db import as_user

router = APIRouter(prefix="/policy", tags=["policy"])

# Answers a question for (question, pack, connection carrying the user, audit callback).
Asker = Callable[[str, str, Any, Callable[[str, dict[str, Any]], None]], Answer]


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    pack: Literal["uk", "uae"]


class PassageOut(BaseModel):
    id: str
    ref: str
    heading: str
    text: str
    document: str


class Statement(BaseModel):
    text: str
    source_id: str
    quote: str


class PolicyReply(BaseModel):
    id: uuid.UUID
    at: datetime
    asked_by_name: str
    pack: str
    question: str
    answered: bool
    statements: list[Statement]
    note: str
    passages: list[PassageOut]
    citation_failures: list[str]


def _audit(conn: Any, user: User) -> Callable[[str, dict[str, Any]], None]:
    def write(action: str, payload: dict[str, Any]) -> None:
        actor = user.id if action == "policy_question" else "agent"
        conn.execute(
            "INSERT INTO audit_log (case_id, actor, action, payload, prev_hash, row_hash) "
            "VALUES (NULL, %s, %s, %s, '', '')",
            (actor, action, json.dumps(payload)),
        )

    return write


SELECT = (
    "SELECT id, at, asked_by_name, pack, question, answer, passages, citation_failures "
    "FROM policy_questions"
)


def _reply(row: tuple[Any, ...]) -> PolicyReply:
    id_, at, name, pack, question, answer, passages, problems = row
    answer = answer or {"answered": False, "statements": [], "note": "No answer was produced."}
    return PolicyReply(
        id=id_,
        at=at,
        asked_by_name=name,
        pack=pack,
        question=question,
        answered=answer["answered"] and not problems,
        statements=answer["statements"],
        note=answer.get("note", ""),
        passages=passages,
        citation_failures=problems,
    )


@router.post("/questions")
def ask_question(body: Ask, user: CurrentUser, request: Request) -> PolicyReply:
    if body.pack not in user.packs:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your pack")
    asker: Asker = request.app.state.asker
    with as_user(request.app.state.db, user) as conn:
        audit = _audit(conn, user)
        audit("policy_question", {"pack": body.pack, "length": len(body.question)})
        result = asker(body.question, body.pack, conn, audit)
        row = conn.execute(
            "INSERT INTO policy_questions (asked_by, asked_by_name, pack, question, answer, "
            "passages, attempts, citation_failures) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id, at, asked_by_name, pack, question, answer, passages, "
            "citation_failures",
            (
                user.id,
                user.username,
                body.pack,
                body.question,
                result.answer.model_dump_json() if result.answer else None,
                json.dumps([p.__dict__ for p in result.passages]),
                result.attempts,
                json.dumps(result.citation_failures),
            ),
        ).fetchone()
    if row is None:
        raise RuntimeError("the question was not stored")
    return _reply(tuple(row))


@router.get("/questions")
def history(user: CurrentUser, request: Request) -> list[PolicyReply]:
    with as_user(request.app.state.db, user) as conn:
        rows = conn.execute(SELECT + " ORDER BY at DESC LIMIT 50").fetchall()
    return [_reply(tuple(r)) for r in rows]


@router.get("/questions/{question_id}")
def one(question_id: uuid.UUID, user: CurrentUser, request: Request) -> PolicyReply:
    with as_user(request.app.state.db, user) as conn:
        row = conn.execute(SELECT + " WHERE id = %s", (question_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such question")
    return _reply(tuple(row))
