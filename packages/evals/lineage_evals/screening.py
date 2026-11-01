"""The labelled sanctions and PEP screening dataset and its validation rules."""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from lineage_agent.names import normalise, script_of

EXPECTED_SIZE = 240
JURISDICTIONS = ("uk", "uae")
# Positive cases per jurisdiction pack.
PACK_CATEGORIES = {"exact_name": 25, "latin_variant": 15, "native_script": 15, "pep": 15}
# Spellings that appear on no list, per pack. Reported apart from the recall gate.
UNLISTED_PER_PACK = 20
# Negative cases, which apply to both packs.
SHARED_CATEGORIES = {"token_collision": 30, "common_name": 15, "invented_company": 15}
NATIVE_SCRIPT = {"uk": "cyrillic", "uae": "arabic"}
LISTS = {"sanctions", "pep"}
ENTITY_TYPES = {"person", "organization"}


@dataclass(frozen=True)
class ScreeningCase:
    id: str
    query: str
    script: str
    entity_type: str
    jurisdiction: str
    category: str
    expected: str
    expected_list: str | None
    expected_entity_ids: tuple[str, ...]

    @classmethod
    def from_json(cls, raw: dict[str, object]) -> "ScreeningCase":
        ids = raw["expected_entity_ids"]
        if not isinstance(ids, list):
            raise TypeError("expected_entity_ids must be a list")
        expected_list = raw["expected_list"]
        return cls(
            id=str(raw["id"]),
            query=str(raw["query"]),
            script=str(raw["script"]),
            entity_type=str(raw["entity_type"]),
            jurisdiction=str(raw["jurisdiction"]),
            category=str(raw["category"]),
            expected=str(raw["expected"]),
            expected_list=None if expected_list is None else str(expected_list),
            expected_entity_ids=tuple(str(i) for i in ids),
        )


def load(path: Path) -> list[ScreeningCase]:
    with path.open(encoding="utf-8") as f:
        return [ScreeningCase.from_json(json.loads(line)) for line in f if line.strip()]


def problems(cases: list[ScreeningCase]) -> list[str]:
    """Return every rule the dataset breaks. An empty list means it is valid."""
    found: list[str] = []
    if len(cases) != EXPECTED_SIZE:
        found.append(f"expected {EXPECTED_SIZE} cases, found {len(cases)}")
    ids = Counter(c.id for c in cases)
    found += [f"duplicate id {i}" for i, n in ids.items() if n > 1]
    queries = Counter(normalise(c.query) for c in cases)
    found += [f"duplicate query {q!r}" for q, n in queries.items() if n > 1]
    counts = Counter((c.jurisdiction, c.category) for c in cases)
    for pack in JURISDICTIONS:
        for category, want in PACK_CATEGORIES.items():
            if counts[(pack, category)] != want:
                found.append(
                    f"{pack} {category}: expected {want}, found {counts[(pack, category)]}"
                )
        if counts[(pack, "unlisted_variant")] != UNLISTED_PER_PACK:
            found.append(
                f"{pack} unlisted_variant: expected {UNLISTED_PER_PACK}, "
                f"found {counts[(pack, 'unlisted_variant')]}"
            )
    for category, want in SHARED_CATEGORIES.items():
        if counts[("both", category)] != want:
            found.append(f"{category}: expected {want}, found {counts[('both', category)]}")
    for c in cases:
        if c.entity_type not in ENTITY_TYPES:
            found.append(f"{c.id}: unknown entity type {c.entity_type}")
        if c.script != script_of(c.query):
            found.append(f"{c.id}: script {c.script} does not match the query text")
        if c.category == "native_script" and c.script != NATIVE_SCRIPT.get(c.jurisdiction):
            found.append(f"{c.id}: native script case is not in the {c.jurisdiction} script")
        positive = c.category in PACK_CATEGORIES or c.category == "unlisted_variant"
        if positive and c.jurisdiction not in JURISDICTIONS:
            found.append(f"{c.id}: a positive case needs a jurisdiction")
        if positive and (c.expected != "match" or not c.expected_entity_ids):
            found.append(f"{c.id}: a positive case needs expected=match and entity ids")
        if positive and c.expected_list not in LISTS:
            found.append(f"{c.id}: a positive case needs a list")
        if not positive and (c.expected != "no_match" or c.expected_entity_ids or c.expected_list):
            found.append(f"{c.id}: a negative case must expect no_match with no ids or list")
    return found
