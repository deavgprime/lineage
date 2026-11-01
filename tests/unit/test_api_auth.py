import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from lineage_api.app import create_app
from lineage_api.auth import Refused, User, Verifier
from lineage_api.settings import Settings

ISSUER = "http://localhost:8080/realms/lineage"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(key: Any = KEY, **overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": "lineage-api",
        "sub": "user-1",
        "preferred_username": "analyst-uk-1",
        "iat": now,
        "exp": now + 300,
        "roles": ["analyst", "default-roles-lineage"],
        "packs": ["uk"],
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256")


class Pool:
    def connection(self, timeout: float | None = None) -> Any:
        raise OSError("not used")

    def open(self, wait: bool = False, timeout: float = 30.0) -> None:
        pass

    def close(self, timeout: float = 5.0) -> None:
        pass


VERIFIER = Verifier(ISSUER, "lineage-api", lambda _: KEY.public_key())


@pytest.mark.unit
def test_a_valid_token_becomes_a_user() -> None:
    assert VERIFIER.verify(token()) == User("user-1", "analyst-uk-1", "analyst", frozenset({"uk"}))


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad",
    [
        {"exp": int(time.time()) - 120},
        {"aud": "account"},
        {"iss": "http://evil.example/realms/lineage"},
        {"sub": None},
    ],
    ids=["expired", "wrong audience", "wrong issuer", "no subject"],
)
def test_bad_claims_are_unauthorised(bad: dict[str, Any]) -> None:
    with pytest.raises(Refused) as refused:
        VERIFIER.verify(token(**bad))
    assert refused.value.status_code == 401


@pytest.mark.unit
def test_a_token_signed_by_another_key_is_unauthorised() -> None:
    with pytest.raises(Refused) as refused:
        VERIFIER.verify(token(key=OTHER))
    assert refused.value.status_code == 401


@pytest.mark.unit
def test_an_unsigned_token_is_unauthorised() -> None:
    unsigned = jwt.encode({"iss": ISSUER, "aud": "lineage-api", "sub": "x"}, "", algorithm="none")
    with pytest.raises(Refused) as refused:
        VERIFIER.verify(unsigned)
    assert refused.value.status_code == 401


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad",
    [{"roles": ["default-roles-lineage"]}, {"roles": ["analyst", "mlro"]}, {"packs": ["fr"]}],
    ids=["no role", "two roles", "no known pack"],
)
def test_missing_role_or_pack_is_forbidden(bad: dict[str, Any]) -> None:
    with pytest.raises(Refused) as refused:
        VERIFIER.verify(token(**bad))
    assert refused.value.status_code == 403


@pytest.mark.unit
def test_me_needs_a_valid_token() -> None:
    app = create_app(Settings(database_url="postgresql://unused"), Pool(), VERIFIER)
    with TestClient(app) as c:
        missing = c.get("/me")
        assert missing.status_code == 401
        assert missing.headers["www-authenticate"] == "Bearer"
        assert c.get("/me", headers={"Authorization": "Bearer junk"}).status_code == 401
        ok = c.get("/me", headers={"Authorization": f"Bearer {token(packs=['uk', 'uae'])}"})
        assert ok.json() == {
            "id": "user-1",
            "username": "analyst-uk-1",
            "role": "analyst",
            "packs": ["uae", "uk"],
        }
