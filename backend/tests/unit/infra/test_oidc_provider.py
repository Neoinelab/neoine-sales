"""OIDC 어댑터: 실제 IdP 대신 httpx MockTransport와 테스트용 RSA 키로 검증한다."""

import base64
import hashlib
import json
import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.domain.auth.errors import AuthenticationError
from app.infra.auth.oidc import OidcConfig, OidcIdentityProvider

if TYPE_CHECKING:
    from app.application.auth.identity import Identity

ISSUER = "https://adfs.example.com/adfs"
CLIENT_ID = "neoine-sales"
REDIRECT = "https://sales.example.com/api/v1/auth/callback"
ONE_HOUR = 3600
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk(key: rsa.RSAPrivateKey, kid: str) -> dict[str, object]:
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    return {**jwk, "kid": kid, "use": "sig", "alg": "RS256"}


def _token(
    claims: dict[str, object] | None = None,
    *,
    key: rsa.RSAPrivateKey = KEY,
    kid: str = "k1",
) -> str:
    now = int(time.time())
    base = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "sub": "S-1-5-21-1",
        "iat": now,
        "exp": now + ONE_HOUR,
        "nonce": "n1",
        "email": "Kim@Neoine.Example",
        "name": "김영업",
        "groups": ["Sales-Team", "All"],
    }
    return jwt.encode({**base, **(claims or {})}, key, algorithm="RS256", headers={"kid": kid})


class Idp:
    """토큰 엔드포인트와 JWKS를 흉내 내는 가짜 IdP. 요청을 기록한다."""

    def __init__(self) -> None:
        self.id_token: str | None = _token()
        self.token_status = 200
        self.keys = [_jwk(KEY, "k1")]
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/oauth2/authorize",
                    "token_endpoint": f"{ISSUER}/oauth2/token",
                    "jwks_uri": f"{ISSUER}/discovery/keys",
                },
            )
        if path.endswith("/discovery/keys"):
            return httpx.Response(200, json={"keys": self.keys})
        if path.endswith("/oauth2/token"):
            body = {"id_token": self.id_token, "access_token": "unused"}
            return httpx.Response(self.token_status, json=body)
        return httpx.Response(404)

    def count(self, suffix: str) -> int:
        return sum(1 for r in self.requests if r.url.path.endswith(suffix))


@pytest.fixture
def idp() -> Idp:
    return Idp()


def _provider(idp: Idp, **overrides: object) -> OidcIdentityProvider:
    values: dict[str, object] = {
        "issuer": ISSUER,
        "client_id": CLIENT_ID,
        "client_secret": "secret",
        "redirect_uri": REDIRECT,
        "scopes": ["openid", "profile", "email"],
        "groups_claim": "groups",
    }
    client = httpx.AsyncClient(transport=httpx.MockTransport(idp))
    return OidcIdentityProvider(OidcConfig(**{**values, **overrides}), client)  # type: ignore[arg-type]


async def _complete(provider: OidcIdentityProvider) -> Identity:
    return await provider.complete(code="the-code", code_verifier="the-verifier", nonce="n1")


async def test_authorization_request_carries_pkce_state_and_nonce(idp: Idp) -> None:
    request = await _provider(idp).authorization_request()

    url = urlparse(request.url)
    query = {k: v[0] for k, v in parse_qs(url.query).items()}
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(request.code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISSUER}/oauth2/authorize"
    assert query["response_type"] == "code"
    assert query["client_id"] == CLIENT_ID
    assert query["redirect_uri"] == REDIRECT
    assert query["scope"] == "openid profile email"
    assert query["state"] == request.state
    assert query["nonce"] == request.nonce
    assert query["code_challenge"] == challenge
    assert query["code_challenge_method"] == "S256"


async def test_each_authorization_request_is_unique(idp: Idp) -> None:
    provider = _provider(idp)

    first, second = await provider.authorization_request(), await provider.authorization_request()

    assert (first.state, first.nonce, first.code_verifier) != (
        second.state,
        second.nonce,
        second.code_verifier,
    )


async def test_complete_exchanges_the_code_and_reads_the_claims(idp: Idp) -> None:
    identity = await _complete(_provider(idp))

    token_request = next(r for r in idp.requests if r.url.path.endswith("/oauth2/token"))
    sent = parse_qs(token_request.content.decode())
    assert sent["grant_type"] == ["authorization_code"]
    assert sent["code"] == ["the-code"]
    assert sent["code_verifier"] == ["the-verifier"]
    assert sent["redirect_uri"] == [REDIRECT]
    assert sent["client_id"] == [CLIENT_ID]
    assert sent["client_secret"] == ["secret"]
    assert identity.subject == "S-1-5-21-1"
    assert identity.email == "Kim@Neoine.Example"
    assert identity.name == "김영업"
    assert identity.groups == frozenset({"Sales-Team", "All"})


async def test_adfs_style_claims_are_supported(idp: Idp) -> None:
    idp.id_token = _token(
        {
            "email": None,
            "upn": "kim@corp.example",
            "name": None,
            "unique_name": "CORP\\kim",
            "groups": "Sales-Team",
        }
    )

    identity = await _complete(_provider(idp))

    assert identity.email == "kim@corp.example"
    assert identity.name == "CORP\\kim"
    assert identity.groups == frozenset({"Sales-Team"})


async def test_groups_claim_name_is_configurable(idp: Idp) -> None:
    idp.id_token = _token({"roles": ["Sales-Admins"], "groups": None})

    identity = await _complete(_provider(idp, groups_claim="roles"))

    assert identity.groups == frozenset({"Sales-Admins"})


@pytest.mark.parametrize(
    "bad_claims",
    [
        {"aud": "someone-else"},
        {"iss": "https://evil.example"},
        {"exp": int(time.time()) - ONE_HOUR},
        {"nonce": "different"},
        {"nonce": None},
        {"sub": None},
    ],
    ids=["audience", "issuer", "expired", "nonce", "no-nonce", "no-subject"],
)
async def test_invalid_id_token_is_rejected(idp: Idp, bad_claims: dict[str, object]) -> None:
    idp.id_token = _token(bad_claims)

    with pytest.raises(AuthenticationError):
        await _complete(_provider(idp))


async def test_token_signed_with_an_unknown_key_is_rejected(idp: Idp) -> None:
    idp.id_token = _token(key=OTHER_KEY, kid="k1")

    with pytest.raises(AuthenticationError):
        await _complete(_provider(idp))


async def test_unsigned_token_is_rejected(idp: Idp) -> None:
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": CLIENT_ID, "sub": "x", "exp": now + 60, "nonce": "n1"}
    idp.id_token = jwt.encode(claims, key=None, algorithm="none")  # type: ignore[arg-type]

    with pytest.raises(AuthenticationError):
        await _complete(_provider(idp))


@pytest.mark.parametrize("mutate", ["status", "no-id-token"])
async def test_token_endpoint_failures_are_rejected(idp: Idp, mutate: str) -> None:
    if mutate == "status":
        idp.token_status = 400
    else:
        idp.id_token = None

    with pytest.raises(AuthenticationError):
        await _complete(_provider(idp))


async def test_unreachable_idp_is_an_authentication_error() -> None:
    def refuse(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = httpx.AsyncClient(transport=httpx.MockTransport(refuse))
    provider = OidcIdentityProvider(
        OidcConfig(ISSUER, CLIENT_ID, "secret", REDIRECT, ["openid"], "groups"), client
    )

    with pytest.raises(AuthenticationError):
        await provider.authorization_request()


async def test_discovery_and_keys_are_cached_between_logins(idp: Idp) -> None:
    provider = _provider(idp)

    await _complete(provider)
    await _complete(provider)

    assert idp.count("openid-configuration") == 1
    assert idp.count("/discovery/keys") == 1


async def test_key_rotation_refetches_the_key_set_once(idp: Idp) -> None:
    provider = _provider(idp)
    await _complete(provider)
    idp.keys = [_jwk(OTHER_KEY, "k2")]
    idp.id_token = _token(key=OTHER_KEY, kid="k2")

    identity = await _complete(provider)

    assert identity.subject == "S-1-5-21-1"
    assert idp.count("/discovery/keys") == 2


async def test_issuer_mismatch_in_discovery_is_rejected(idp: Idp) -> None:
    provider = _provider(idp, issuer="https://other.example/adfs")

    with pytest.raises(AuthenticationError):
        await provider.authorization_request()
