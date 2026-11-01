"""Print the API's OpenAPI schema, which the console generates its typed client from.

python -m lineage_api.openapi > apps/console/openapi.json
"""

import json

from lineage_api.app import create_app
from lineage_api.auth import Verifier
from lineage_api.settings import Settings


def schema() -> dict[str, object]:
    app = create_app(
        Settings(database_url="postgresql://unused"),
        verifier=Verifier("unused", "lineage-api", lambda _: None),
        runner=lambda number, pack, audit: None,  # type: ignore[arg-type,return-value]
    )
    return app.openapi()


if __name__ == "__main__":
    print(json.dumps(schema(), indent=2, sort_keys=True))
