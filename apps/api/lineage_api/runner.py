"""The agent as the API runs it: live registers, screening on the database, Claude for drafting."""

import os
from pathlib import Path
from typing import Any, Literal

import psycopg
from lineage_agent.agent import Agent, Result
from lineage_agent.claims import Claim, Draft
from lineage_agent.cli import model
from lineage_agent.pii import PresidioScanner
from lineage_agent.policy_qa import KEYWORD_SEARCH, Answer, Passage, PolicyAnswer, ask
from lineage_agent.tools.screening import screen
from lineage_ingest.companies_house import CompaniesHouse
from lineage_ingest.gleif import Gleif

from lineage_api.cases import Audit

CACHE = (
    Path(os.environ.get("LINEAGE_CACHE", Path.home() / ".cache" / "lineage")) / "companies-house"
)


# One scanner per process: loading its language model takes a second.
SCANNER = PresidioScanner()


class LiveRunner:
    def __init__(self, database_url: str) -> None:
        self._url = database_url

    def __call__(self, company_number: str, pack: str, audit: Audit) -> Result:
        # Screening reads public list data only, so it runs on its own connection as the owner.
        with psycopg.connect(self._url) as conn:
            agent = Agent(
                register=CompaniesHouse(cache=CACHE),
                lei=Gleif(),
                screen=lambda name, p: screen(conn, name, p),
                model=model(),
                audit=audit,
                scanner=SCANNER,
            )
            return agent.run(company_number, pack)


class FixtureRunner:
    """Canned, fully cited drafts with no network or model access, for end-to-end tests only.

    Selected with LINEAGE_RUNNER=fixture. Company numbers starting 99 draft as high risk; all
    others draft as low risk with one weak screening alert to clear.
    """

    def __call__(self, company_number: str, pack: str, audit: Audit) -> Result:
        audit("plan", {"steps": ["registry_chain", "screen_chain", "draft", "check_citations"]})
        name = f"FIXTURE COMPANY {company_number} LIMITED"
        record_id = f"companies-house:company:{company_number}"
        record = f"Company {name}, number {company_number}. Controlled by individual [redacted]."
        screening_id = f"screening:{record_id}"
        candidate = "opensanctions:sanctions:FIXTURE-1"
        screening = (
            f"Screening of {name} against the {pack.upper()} sanctions and PEP lists. "
            f"Candidate {candidate} (sanctions, weak): matched name FIXTURE HOLDINGS, score 0.62."
        )
        audit("tool_call", {"tool": "registry"})
        audit("tool_call", {"tool": "screening", "hits": 1})
        high = company_number.startswith("99")
        rating: Literal["low", "high"] = "high" if high else "low"
        registered = Claim(
            text=f"{name} is registered.", source_id=record_id, quote=f"Company {name}"
        )
        weak = Claim(
            text="Screening found one weak sanctions candidate for the analyst to clear.",
            source_id=screening_id,
            quote=f"Candidate {candidate} (sanctions, weak)",
        )
        audit("model_call", {"attempt": 1})
        draft = Draft(
            summary=[registered],
            ownership=[
                Claim(
                    text="The company is controlled by one individual.",
                    source_id=record_id,
                    quote="Controlled by individual",
                )
            ],
            screening=[weak],
            risk_rating=rating,
            risk_reasons=[weak if high else registered],
        )
        audit("draft", {"attempts": 1, "citation_failures": 0})
        return Result(
            company_number=company_number,
            pack=pack,
            plan=["registry_chain", "screen_chain", "draft", "check_citations"],
            draft=draft,
            attempts=1,
            citation_failures=[],
            evidence=[
                {
                    "source_id": record_id,
                    "title": f"Companies House record {company_number}",
                    "text": record,
                },
                {"source_id": screening_id, "title": f"Screening of {name}", "text": screening},
            ],
            minimum_rating="low",
            alerts=[f"{candidate} for {record_id}"],
        )


class LiveAsker:
    """Policy questions with the local embedding model and rerankers, and Claude to answer.
    The models load on first use, so the API starts fast."""

    def __init__(self) -> None:
        self._embedder: Any = None
        self._reranker: Any = None

    def __call__(self, question: str, pack: str, conn: Any, audit: Audit) -> Answer:
        from lineage_agent.policy_qa import LocalReranker, PgRetriever
        from lineage_ingest.policy import MODELS, LocalEmbedder

        if self._embedder is None:
            self._embedder = LocalEmbedder()
            self._reranker = LocalReranker(str(MODELS))
        retriever = PgRetriever(conn, lambda q: self._embedder.embed([q])[0], self._reranker)
        return ask(question, pack, retriever, model(), SCANNER, audit)


class FixtureAsker:
    """Keyword search only and a canned answer quoting the top passage, for end-to-end tests."""

    def __call__(self, question: str, pack: str, conn: Any, audit: Audit) -> Answer:
        rows = conn.execute(KEYWORD_SEARCH, {"pack": pack, "question": question, "limit": 3})
        passages = [Passage(*r) for r in rows.fetchall()]
        audit("policy_search", {"pack": pack, "passages": [p.id for p in passages]})
        if not passages:
            answer = PolicyAnswer(answered=False, statements=[], note="Nothing in the corpus.")
        else:
            top = passages[0]
            quote = top.text.split(". ")[0]
            answer = PolicyAnswer(
                answered=True,
                statements=[Claim(text=f"{top.ref} applies.", source_id=top.id, quote=quote)],
            )
        audit("policy_answer", {"attempts": 1, "citation_failures": 0})
        return Answer(question, pack, answer, passages, 1, [])
