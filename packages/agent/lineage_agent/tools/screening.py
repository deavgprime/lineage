"""Screen a name against the sanctions and PEP records loaded for a jurisdiction pack.

Matching runs on real names inside the bank, as decision 0001 sets out. A candidate comes from one
of three rules, strongest first: the normalised name is identical, the same words appear in a
different order, or the trigram similarity of the normalised names is at least the threshold.
"""

from dataclasses import dataclass

import psycopg

from lineage_agent.names import normalise

THRESHOLD = 0.6
LIMIT = 10

QUERY = """
SELECT record_id, name, kind,
       CASE WHEN name_norm = %(norm)s THEN 1.0
            WHEN name_tokens = %(tokens)s THEN 0.95
            ELSE similarity(name_norm, %(norm)s) END AS score,
       CASE WHEN name_norm = %(norm)s THEN 'exact'
            WHEN name_tokens = %(tokens)s THEN 'word_order'
            ELSE 'similar' END AS rule
FROM screening_names
WHERE %(pack)s = ANY (jurisdictions)
  AND (name_norm = %(norm)s OR name_tokens = %(tokens)s OR name_norm %% %(norm)s)
ORDER BY score DESC, record_id
LIMIT %(limit)s
"""


@dataclass(frozen=True)
class Candidate:
    record_id: str
    matched_name: str
    kind: str
    score: float
    rule: str


def tokens(name: str) -> str:
    return " ".join(sorted(normalise(name).split()))


def screen(
    conn: psycopg.Connection[tuple[object, ...]],
    name: str,
    pack: str,
    threshold: float = THRESHOLD,
    limit: int = LIMIT,
) -> list[Candidate]:
    """Return the best candidate per record for a name, best first."""
    norm = normalise(name)
    if not norm:
        return []
    conn.execute("SELECT set_config('pg_trgm.similarity_threshold', %s, false)", (str(threshold),))
    rows = conn.execute(
        QUERY, {"norm": norm, "tokens": tokens(name), "pack": pack, "limit": limit * 3}
    ).fetchall()
    best: dict[str, Candidate] = {}
    for record_id, matched, kind, score, rule in rows:
        candidate = Candidate(str(record_id), str(matched), str(kind), float(score), str(rule))  # type: ignore[arg-type]
        if candidate.record_id not in best or candidate.score > best[candidate.record_id].score:
            best[candidate.record_id] = candidate
    ranked = sorted(best.values(), key=lambda c: (-c.score, c.record_id))
    return [c for c in ranked if c.score >= threshold][:limit]
