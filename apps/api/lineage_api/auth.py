"""Check the Keycloak access token on every request and turn it into a user.

A token must be signed by the realm, issued by it, meant for the API, and unexpired. The user must
hold exactly one Lineage role and at least one jurisdiction pack. Anything else is refused, so a
mistake in the realm cannot grant access by default (decision 0003).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal, cast

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

Role = Literal["analyst", "mlro", "auditor"]
ROLES: tuple[Role, ...] = ("analyst", "mlro", "auditor")
PACKS = frozenset({"uk", "uae"})
ALGORITHMS = ["RS256"]
LEEWAY_SECONDS = 30


@dataclass(frozen=True)
class User:
    id: str
    username: str
    role: Role
    packs: frozenset[str]


class Refused(Exception):
    def __init__(self, status_code: int, reason: str) -> None:
        super().__init__(reason)
        self.status_code = status_code
        self.reason = reason


KeyFor = Callable[[str], Any]


class Verifier:
    def __init__(self, issuer: str, audience: str, key_for: KeyFor) -> None:
        self._issuer = issuer
        self._audience = audience
        self._key_for = key_for

    @classmethod
    def from_jwks(cls, issuer: str, audience: str, jwks_url: str) -> "Verifier":
        client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300)
        return cls(issuer, audience, lambda token: client.get_signing_key_from_jwt(token).key)

    def verify(self, token: str) -> User:
        try:
            claims = jwt.decode(
                token,
                self._key_for(token),
                algorithms=ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except (jwt.PyJWTError, KeyError, ValueError) as error:
            raise Refused(status.HTTP_401_UNAUTHORIZED, f"invalid token: {error}") from error
        roles = [r for r in claims.get("roles", []) if r in ROLES]
        if len(roles) != 1:
            raise Refused(status.HTTP_403_FORBIDDEN, "the user must hold exactly one Lineage role")
        packs = frozenset(claims.get("packs", [])) & PACKS
        if not packs:
            raise Refused(status.HTTP_403_FORBIDDEN, "the user has no jurisdiction pack")
        return User(
            id=claims["sub"],
            username=claims.get("preferred_username", claims["sub"]),
            role=cast(Role, roles[0]),
            packs=packs,
        )


bearer = HTTPBearer(auto_error=False)


def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "sign-in required", {"WWW-Authenticate": "Bearer"}
        )
    verifier: Verifier = request.app.state.verifier
    try:
        return verifier.verify(credentials.credentials)
    except Refused as refused:
        headers = (
            {"WWW-Authenticate": 'Bearer error="invalid_token"'}
            if refused.status_code == status.HTTP_401_UNAUTHORIZED
            else None
        )
        # The reason goes to the log, not the caller.
        request.app.state.log.info("refused", extra={"fields": {"reason": refused.reason}})
        raise HTTPException(refused.status_code, "not allowed", headers) from refused


CurrentUser = Annotated[User, Depends(current_user)]
