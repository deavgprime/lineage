"""Settings read from the environment once, at start-up."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    oidc_issuer: str = "http://localhost:8080/realms/lineage"
    oidc_audience: str = "lineage-api"
    # Where the API fetches signing keys. It differs from the issuer when Keycloak is reached on
    # an internal address, as it is inside compose.
    oidc_jwks_url: str = ""
    log_level: str = "INFO"

    @property
    def jwks_url(self) -> str:
        return self.oidc_jwks_url or f"{self.oidc_issuer}/protocol/openid-connect/certs"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ["DATABASE_URL"],
            oidc_issuer=os.environ.get("OIDC_ISSUER", cls.oidc_issuer),
            oidc_audience=os.environ.get("OIDC_AUDIENCE", cls.oidc_audience),
            oidc_jwks_url=os.environ.get("OIDC_JWKS_URL", ""),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
