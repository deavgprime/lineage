"""Apply SQL migrations in order. Each file runs once, inside its own transaction.

DATABASE_URL=postgresql://... python -m lineage_db.migrate
"""

import os
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).parent / "migrations"


def migrate(url: str) -> list[str]:
    """Apply pending migrations and return the names of those applied."""
    applied: list[str] = []
    with psycopg.connect(url) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
        conn.commit()
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in done:
                continue
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
            applied.append(path.name)
    return applied


if __name__ == "__main__":
    for name in migrate(os.environ["DATABASE_URL"]):
        print(f"applied {name}")
