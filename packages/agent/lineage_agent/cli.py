"""Command-line entry point.

    lineage draft 00519500 --pack uk

Needs DATABASE_URL, COMPANIES_HOUSE_API_KEY and Anthropic credentials. Opens a case,
records every step in the audit log, and prints the draft as JSON. The file stays a draft
until an analyst signs it off in the console.
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import psycopg
from lineage_ingest.companies_house import CompaniesHouse
from lineage_ingest.gleif import Gleif

from lineage_agent.agent import Agent
from lineage_agent.model import Claude
from lineage_agent.tools.screening import screen

CACHE = Path.home() / ".cache" / "lineage" / "companies-house"


def draft(company_number: str, pack: str) -> dict[str, Any]:
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        row = conn.execute(
            "INSERT INTO cases (jurisdiction, subject, company_number, assigned_to) "
            "VALUES (%s, %s, %s, 'cli') RETURNING id",
            (pack, company_number, company_number),
        ).fetchone()
        assert row is not None
        case_id = row[0]

        def audit(action: str, payload: dict[str, Any]) -> None:
            conn.execute(
                "INSERT INTO audit_log (case_id, actor, action, payload, prev_hash, row_hash) "
                "VALUES (%s, 'agent', %s, %s, '', '')",
                (case_id, action, json.dumps(payload)),
            )

        agent = Agent(
            register=CompaniesHouse(cache=CACHE),
            lei=Gleif(),
            screen=lambda name, p: screen(conn, name, p),
            model=Claude(),
            audit=audit,
        )
        result = agent.run(company_number, pack)
        out = asdict(result)
        out["draft"] = result.draft.model_dump() if result.draft else None
        out["case_id"] = str(case_id)
        out["status"] = "draft"
        return out


def main() -> None:
    ap = argparse.ArgumentParser(prog="lineage")
    sub = ap.add_subparsers(dest="command", required=True)
    d = sub.add_parser("draft", help="draft a cited file for a company")
    d.add_argument("company_number")
    d.add_argument("--pack", choices=["uk", "uae"], default="uk")
    args = ap.parse_args()
    out = draft(args.company_number, args.pack)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if out["citation_failures"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
