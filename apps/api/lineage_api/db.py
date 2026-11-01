"""Database access on behalf of a signed-in user.

Every query the API makes for a user runs inside `as_user`, which switches to the lineage_app role
and records the user for the row-level security policies in migration 0003. Settings are local to
the transaction, so nothing leaks to the next request on the same pooled connection.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg

from lineage_api.auth import User


@contextmanager
def as_user(pool: Any, user: User) -> Iterator[psycopg.Connection[Any]]:
    with pool.connection() as conn, conn.transaction():
        conn.execute("SET LOCAL ROLE lineage_app")
        conn.execute(
            "SELECT set_config('lineage.user_id', %s, true), "
            "set_config('lineage.role', %s, true), set_config('lineage.packs', %s, true)",
            (user.id, user.role, ",".join(sorted(user.packs))),
        )
        yield conn
