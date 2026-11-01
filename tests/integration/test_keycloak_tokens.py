"""Tokens from the local Keycloak realm, checked by the API's verifier.

Needs Keycloak from compose.yaml: docker compose up -d --wait keycloak
"""

import json
import os
import urllib.parse
import urllib.request

import pytest
from lineage_api.auth import Refused, Verifier

BASE = os.environ.get("KEYCLOAK_URL", "")
ISSUER = "http://localhost:8080/realms/lineage"
pytestmark = pytest.mark.skipif(not BASE, reason="KEYCLOAK_URL is not set")


def password_token(username: str) -> str:
    body = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": "lineage-console",
            "username": username,
            "password": f"{username}-local-test",
            "scope": "openid",
        }
    ).encode()
    url = f"{BASE}/realms/lineage/protocol/openid-connect/token"
    with urllib.request.urlopen(url, body, timeout=10) as response:  # noqa: S310
        return str(json.load(response)["access_token"])


@pytest.fixture(scope="module")
def verifier() -> Verifier:
    return Verifier.from_jwks(
        ISSUER, "lineage-api", f"{BASE}/realms/lineage/protocol/openid-connect/certs"
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("username", "role", "packs"),
    [
        ("analyst-uk-1", "analyst", {"uk"}),
        ("mlro-uae-1", "mlro", {"uae"}),
        ("auditor-1", "auditor", {"uk", "uae"}),
    ],
)
def test_realm_tokens_verify_with_role_and_packs(
    verifier: Verifier, username: str, role: str, packs: set[str]
) -> None:
    user = verifier.verify(password_token(username))
    assert (user.username, user.role, set(user.packs)) == (username, role, packs)
    assert user.id


@pytest.mark.integration
def test_a_tampered_realm_token_is_refused(verifier: Verifier) -> None:
    head, body, signature = password_token("analyst-uk-1").split(".")
    with pytest.raises(Refused):
        verifier.verify(f"{head}.{body}.{signature[:-4]}AAAA")
