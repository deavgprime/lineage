"""Rebuild the screening name index from the loaded OpenSanctions records."""

import psycopg
from lineage_agent.names import normalise
from lineage_agent.tools.screening import tokens


def rebuild(conn: psycopg.Connection[tuple[object, ...]]) -> int:
    """Replace the index in one transaction and return the number of names written."""
    rows = conn.execute(
        "SELECT id, record FROM source_records WHERE source = 'opensanctions'"
    ).fetchall()
    names: list[tuple[str, str, str, str, str, list[str]]] = []
    for record_id, record in rows:
        assert isinstance(record, dict)
        seen: set[str] = set()
        for name in [record["name"], *record["aliases"]]:
            if name in seen or not normalise(name):
                continue
            seen.add(name)
            names.append(
                (
                    str(record_id),
                    name,
                    normalise(name),
                    tokens(name),
                    record["kind"],
                    record["jurisdictions"],
                )
            )
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM screening_names")
        cur.executemany(
            "INSERT INTO screening_names "
            "(record_id, name, name_norm, name_tokens, kind, jurisdictions) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            names,
        )
    return len(names)
