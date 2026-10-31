"""Load the OpenSanctions sanctions and PEP files for the UK and UAE packs.

    DATABASE_URL=... python -m lineage_ingest.opensanctions \\
        --sanctions sanctions.csv --peps peps.csv --version <dataset version>

The inputs are `targets.simple.csv` from the `sanctions` and `peps` datasets. A record is written
only when it belongs to at least one pack, and rewritten only when its content changes, so a reload
of the same version changes nothing.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import psycopg

from lineage_ingest.packs import PEP_COUNTRIES, SANCTIONS_LISTS, SCHEMAS

SOURCE = "opensanctions"
UPSERT = """
INSERT INTO source_records (id, source, dataset_version, record, checksum)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE
SET dataset_version = EXCLUDED.dataset_version, record = EXCLUDED.record,
    checksum = EXCLUDED.checksum, loaded_at = now()
WHERE source_records.checksum <> EXCLUDED.checksum
"""


def split(value: str) -> list[str]:
    return [v for v in value.split(";") if v]


def rows(path: Path) -> Iterator[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def to_record(row: dict[str, str], kind: str, packs: list[str]) -> dict[str, object]:
    return {
        "opensanctions_id": row["id"],
        "kind": kind,
        "schema": row["schema"],
        "name": row["name"],
        "aliases": split(row["aliases"]),
        "birth_date": row["birth_date"] or None,
        "countries": split(row["countries"]),
        "datasets": split(row["dataset"]),
        "jurisdictions": packs,
    }


def records(sanctions: Path, peps: Path) -> Iterator[dict[str, object]]:
    for row in rows(sanctions):
        listed = set(split(row["dataset"]))
        packs = sorted(p for p, lists in SANCTIONS_LISTS.items() if lists & listed)
        if row["schema"] in SCHEMAS and packs:
            yield to_record(row, "sanctions", packs)
    for row in rows(peps):
        countries = set(split(row["countries"]))
        packs = sorted(p for p, c in PEP_COUNTRIES.items() if c in countries)
        if row["schema"] == "Person" and packs:
            yield to_record(row, "pep", packs)


def load(url: str, sanctions: Path, peps: Path, version: str) -> Counter[str]:
    """Write the pack records and return how many were written and unchanged."""
    counts: Counter[str] = Counter()
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for record in records(sanctions, peps):
            body = json.dumps(record, ensure_ascii=False, sort_keys=True)
            checksum = hashlib.sha256(body.encode()).hexdigest()
            key = f"{SOURCE}:{record['kind']}:{record['opensanctions_id']}"
            cur.execute(UPSERT, (key, SOURCE, version, body, checksum))
            counts["written" if cur.rowcount else "unchanged"] += 1
            counts[str(record["kind"])] += 1
    return counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sanctions", type=Path, required=True)
    ap.add_argument("--peps", type=Path, required=True)
    ap.add_argument("--version", required=True)
    args = ap.parse_args()
    print(dict(load(os.environ["DATABASE_URL"], args.sanctions, args.peps, args.version)))


if __name__ == "__main__":
    main()
