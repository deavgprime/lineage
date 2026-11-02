"""Check the whole audit log against its hash chain.

    DATABASE_URL=... python -m lineage_db.audit

Every row's hash is recomputed in Postgres exactly as the chain trigger computed it, so the text
forms of times and JSON match. Every row must link back to a row that exists, or to the start of the
chain, and no two rows may link back to the same row, which would mean the chain was forked. Exits
with 1 and names the first broken row if anything fails.
"""

import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import psycopg

GENESIS = "0" * 64

ROWS = """
SELECT seq, prev_hash, row_hash,
       encode(digest(prev_hash || coalesce(case_id::text, '') || at::text || actor || action
                     || payload::text, 'sha256'), 'hex') = row_hash
FROM audit_log ORDER BY seq
"""


@dataclass
class Report:
    rows: int = 0
    bad_hash: list[int] = field(default_factory=list)
    bad_link: list[int] = field(default_factory=list)
    forked: list[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.bad_hash or self.bad_link or self.forked)

    def first_break(self) -> int | None:
        broken = self.bad_hash + self.bad_link + self.forked
        return min(broken) if broken else None


def verify(conn: psycopg.Connection[Any]) -> Report:
    rows = conn.execute(ROWS).fetchall()
    report = Report(rows=len(rows))
    hashes = {row_hash for _, _, row_hash, _ in rows}
    links = Counter(prev for _, prev, _, _ in rows)
    for seq, prev, _, hash_ok in rows:
        if not hash_ok:
            report.bad_hash.append(seq)
        if prev != GENESIS and prev not in hashes:
            report.bad_link.append(seq)
        if links[prev] > 1:
            report.forked.append(seq)
    return report


def main() -> None:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        report = verify(conn)
    if report.ok:
        print(f"audit chain verified: {report.rows} rows")
        return
    print(
        f"audit chain broken at row {report.first_break()}: "
        f"{len(report.bad_hash)} hash, {len(report.bad_link)} link and "
        f"{len(report.forked)} fork failures in {report.rows} rows",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
