"""The ownership ground truth for UK companies and its validation rules."""

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

CATEGORIES = {
    "individual_direct": 10,
    "two_layers": 8,
    "three_or_more_layers": 6,
    "ends_in_statement": 3,
    "ends_overseas": 3,
}
COMPANY_NUMBER = re.compile(r"[A-Z0-9]{8}")
PSC_LINK = re.compile(r"/company/[A-Z0-9]{8}/persons-with-significant-control/individual/[\w-]+")
ENDPOINT_TYPES = {"individual", "overseas_company", "uk_company_without_controllers"}


@dataclass(frozen=True)
class OwnershipCase:
    id: str
    company_number: str
    company_name: str
    category: str
    depth: int
    ultimate_controllers: tuple[dict[str, str], ...]
    chain: dict[str, object]


def load(path: Path) -> list[OwnershipCase]:
    cases = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                raw = json.loads(line)
                cases.append(
                    OwnershipCase(
                        id=raw["id"],
                        company_number=raw["company_number"],
                        company_name=raw["company_name"],
                        category=raw["category"],
                        depth=int(raw["depth"]),
                        ultimate_controllers=tuple(raw["ultimate_controllers"]),
                        chain=raw["chain"],
                    )
                )
    return cases


def _names_individuals(node: object) -> bool:
    if isinstance(node, dict):
        if node.get("type") == "individual" and "name" in node:
            return True
        return any(_names_individuals(v) for v in node.values())
    if isinstance(node, list):
        return any(_names_individuals(v) for v in node)
    return False


def problems(cases: list[OwnershipCase]) -> list[str]:
    """Return every rule the dataset breaks. An empty list means it is valid."""
    found: list[str] = []
    counts = Counter(c.category for c in cases)
    for category, want in CATEGORIES.items():
        if counts[category] != want:
            found.append(f"category {category}: expected {want}, found {counts[category]}")
    numbers = Counter(c.company_number for c in cases)
    found += [f"duplicate company {n}" for n, k in numbers.items() if k > 1]
    for c in cases:
        if not COMPANY_NUMBER.fullmatch(c.company_number):
            found.append(f"{c.id}: bad company number {c.company_number}")
        if _names_individuals(c.chain) or _names_individuals(list(c.ultimate_controllers)):
            found.append(f"{c.id}: an individual is stored by name")
        for u in c.ultimate_controllers:
            if u.get("type") not in ENDPOINT_TYPES:
                found.append(f"{c.id}: unexpected controller type {u.get('type')}")
            if u.get("type") == "individual" and not PSC_LINK.fullmatch(u.get("psc", "")):
                found.append(f"{c.id}: an individual needs a register link")
        layered = {"two_layers": 2, "individual_direct": 1}
        if c.category in layered and c.depth != layered[c.category]:
            found.append(f"{c.id}: depth {c.depth} does not fit {c.category}")
        if c.category == "three_or_more_layers" and c.depth < 3:
            found.append(f"{c.id}: depth {c.depth} is under three")
    return found
