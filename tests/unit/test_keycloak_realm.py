import json
from collections import Counter
from pathlib import Path

import pytest

REALM = json.loads(
    (Path(__file__).resolve().parents[2] / "infra" / "keycloak" / "lineage-realm.json").read_text()
)


@pytest.mark.unit
def test_every_role_and_pack_has_test_users() -> None:
    users = REALM["users"]
    roles = Counter(u["realmRoles"][0] for u in users)
    assert set(roles) == {"analyst", "mlro", "auditor"}
    # Two analysts and two MLROs in one pack, to test isolation and four-eyes sign-off.
    uk = [u for u in users if "/uk" in u["groups"]]
    assert sum(u["realmRoles"] == ["analyst"] for u in uk) >= 2
    assert sum(u["realmRoles"] == ["mlro"] for u in uk) >= 2


@pytest.mark.unit
def test_passwords_are_local_test_values_only() -> None:
    for user in REALM["users"]:
        (credential,) = user["credentials"]
        assert credential["value"] == f"{user['username']}-local-test"
        assert user["email"].endswith("@lineage.test")


@pytest.mark.unit
def test_console_only_redirects_to_localhost_with_pkce() -> None:
    console = next(c for c in REALM["clients"] if c["clientId"] == "lineage-console")
    assert console["publicClient"]
    assert all(u.startswith("http://localhost:") for u in console["redirectUris"])
    assert console["attributes"]["pkce.code.challenge.method"] == "S256"
