#!/usr/bin/env python3
"""Check an exported audit trail without Lineage, its database or any library outside Python.

    python3 verify_audit_export.py export.json

For every row, the SHA-256 of `hashed_text` must equal `row_hash`, and `hashed_text` must start with
the row's `prev_hash`, so each row is bound to the one before it in the bank's whole log. Rows from
other cases sit between a case's rows, so one export shows every row is intact and where it links,
and the bank's full chain check (`python -m lineage_db.audit`) shows the links are unbroken.
"""

import hashlib
import json
import sys


def check(export: dict) -> list[str]:
    problems = []
    if export.get("format") != "lineage-audit-export/1":
        problems.append(f"unknown format {export.get('format')!r}")
    for row in export.get("rows", []):
        text = row["hashed_text"]
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != row["row_hash"]:
            problems.append(f"row {row['seq']}: hash does not match its text")
        if not text.startswith(row["prev_hash"]):
            problems.append(f"row {row['seq']}: text does not start with its previous hash")
        if row["action"] not in text or row["actor"] not in text:
            problems.append(f"row {row['seq']}: actor or action missing from its text")
    return problems


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as f:
        export = json.load(f)
    problems = check(export)
    for p in problems:
        print(p)
    rows = len(export.get("rows", []))
    print(f"{rows} rows, {'all verified' if not problems else f'{len(problems)} problems'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
