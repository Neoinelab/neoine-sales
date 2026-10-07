"""IdentityProvider Port의 OIDC 구현(Authorization Code + PKCE, client_secret_post).

표준 discovery 문서를 쓰므로 AD FS, Entra ID, Keycloak 등 OIDC IdP에 쓸 수 있다.
IdP 통신·토큰 검증 실패는 모두 AuthenticationError로 바꾸고 원인 상세는 노출하지 않는다.
"""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
import jwt

from app.application.auth.identity import Identity
from app.application.ports.identity_provider import AuthorizationRequest
from app.domain.auth.errors import AuthenticationError

if TYPE_CHECKING:
    from collections.abc import Sequence

LEEWAY_SECONDS = 60
HTTP_OK = 200
_UNAVAILABLE = "로그인 서버(IdP)와 통신하거나 응답을 확인하지 못했습니다"


@dataclass(frozen=True, slots=True)
class OidcConfig:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: Sequence[str]
    groups_claim: str


def _with_query(url: str, params: dict[str, str]) -> str:
    parts = urlsplit(url)
    query = f"{parts.query}&{urlencode(params)}" if parts.query else urlencode(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _first_text(claims: dict[str, Any], *names: str) -> str | None:
    for name in names:
        value = claims.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _groups(claims: dict[str, Any], claim: str) -> frozenset[str]:
    value = claims.get(claim)
    if isinstance(value, str):
        return frozenset({value})
    if isinstance(value, list):
        return frozenset(item for item in value if isinstance(item, str))
    return frozenset()


class OidcIdentityProvider:
    def __init__(self, config: OidcConfig, http: httpx.AsyncClient) -> None:
        self._config = config
        self._http = http
        self._metadata: dict[str, Any] | None = None
        self._keys: list[dict[str, Any]] | None = None

    async def authorization_request(self) -> AuthorizationRequest:
        metadata = await self._discovery()
        state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        params = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "scope": " ".join(self._config.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": _pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }
        url = _with_query(metadata["authorization_endpoint"], params)
        return AuthorizationRequest(url, state, nonce, verifier)

    async def complete(self, *, code: str, code_verifier: str, nonce: str) -> Identity:
        metadata = await self._discovery()
        id_token = await self._exchange(metadata["token_endpoint"], code, code_verifier)
        claims = await self._verify(id_token, metadata)
        received = claims.get("nonce")
        if not isinstance(received, str) or not hmac.compare_digest(received, nonce):
            raise AuthenticationError(_UNAVAILABLE)
        email = _first_text(claims, "email", "upn", "preferred_username")
        name = _first_text(claims, "name", "unique_name", "preferred_username") or ""
        return Identity(
            subject=str(claims["sub"]),
            email=email,
            name=name,
            groups=_groups(claims, self._config.groups_claim),
        )

    async def _discovery(self) -> dict[str, Any]:
        if self._metadata is not None:
            return self._metadata
        issuer = self._config.issuer.rstrip("/")
        try:
            response = await self._http.get(f"{issuer}/.well-known/openid-configuration")
            metadata: dict[str, Any] = response.json()
            if response.status_code != HTTP_OK or metadata["issuer"].rstrip("/") != issuer:
                raise AuthenticationError(_UNAVAILABLE)
            for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                if not isinstance(metadata[key], str):
                    raise AuthenticationError(_UNAVAILABLE)
        except (httpx.HTTPError, ValueError, KeyError, AttributeError) as error:
            raise AuthenticationError(_UNAVAILABLE) from error
        self._metadata = metadata
        return metadata

    async def _exchange(self, token_endpoint: str, code: str, verifier: str) -> str:
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": self._config.redirect_uri,
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
        }
        try:
            response = await self._http.post(token_endpoint, data=form)
            id_token = response.json().get("id_token")
        except (httpx.HTTPError, ValueError, AttributeError) as error:
            raise AuthenticationError(_UNAVAILABLE) from error
        if response.status_code != HTTP_OK or not isinstance(id_token, str):
            raise AuthenticationError(_UNAVAILABLE)
        return id_token

    async def _verify(self, id_token: str, metadata: dict[str, Any]) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(id_token)
            if header.get("alg") != "RS256":
                raise AuthenticationError(_UNAVAILABLE)
            jwk = await self._find_key(header, metadata["jwks_uri"])
            claims: dict[str, Any] = jwt.decode(
                id_token,
                jwt.PyJWK.from_dict(jwk, algorithm="RS256"),
                algorithms=["RS256"],
                audience=self._config.client_id,
                issuer=metadata["issuer"],
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except (jwt.PyJWTError, ValueError, KeyError) as error:
            raise AuthenticationError(_UNAVAILABLE) from error
        return claims

    async def _find_key(self, header: dict[str, Any], jwks_uri: str) -> dict[str, Any]:
        """헤더의 kid(AD FS는 x5t)로 서명 키를 찾는다. 모르는 키면 키 목록을 한 번 다시 받는다."""
        identifier = header.get("kid") or header.get("x5t")
        for refresh in (False, True):
            if refresh or self._keys is None:
                self._keys = await self._fetch_keys(jwks_uri)
            for key in self._keys:
                if identifier in (key.get("kid"), key.get("x5t")):
                    return key
        raise AuthenticationError(_UNAVAILABLE)

    async def _fetch_keys(self, jwks_uri: str) -> list[dict[str, Any]]:
        try:
            response = await self._http.get(jwks_uri)
            keys = response.json()["keys"]
        except (httpx.HTTPError, ValueError, KeyError) as error:
            raise AuthenticationError(_UNAVAILABLE) from error
        if response.status_code != HTTP_OK or not isinstance(keys, list):
            raise AuthenticationError(_UNAVAILABLE)
        return [key for key in keys if isinstance(key, dict)]
