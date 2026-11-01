"""Check that every claim quotes a passage that exists in the record it cites."""

import re

from lineage_agent.claims import Claim
from lineage_agent.evidence import EvidenceStore

_SPACE = re.compile(r"\s+")


def _squash(text: str) -> str:
    return _SPACE.sub(" ", text).strip().casefold()


def failures(claims: list[Claim], evidence: EvidenceStore) -> list[str]:
    """Return a reason for every claim that fails. An empty list means all claims are cited."""
    found: list[str] = []
    for claim in claims:
        record = evidence.get(claim.source_id)
        if record is None:
            found.append(f"{claim.source_id!r} is not an evidence id: {claim.text}")
        elif not claim.quote.strip():
            found.append(f"no quote given for: {claim.text}")
        elif _squash(claim.quote) not in _squash(record.text):
            found.append(f"quote not found in {claim.source_id}: {claim.quote!r}")
    return found
