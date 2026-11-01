"""The agent as the API runs it: live registers, screening on the database, Claude for drafting."""

import os
from pathlib import Path

import psycopg
from lineage_agent.agent import Agent, Result
from lineage_agent.cli import model
from lineage_agent.tools.screening import screen
from lineage_ingest.companies_house import CompaniesHouse
from lineage_ingest.gleif import Gleif

from lineage_api.cases import Audit

CACHE = (
    Path(os.environ.get("LINEAGE_CACHE", Path.home() / ".cache" / "lineage")) / "companies-house"
)


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
            )
            return agent.run(company_number, pack)
