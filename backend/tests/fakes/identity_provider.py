"""IdentityProvider Port의 Fake. 실제 IdP 없이 로그인 흐름을 재현한다."""

from typing import TYPE_CHECKING

from app.application.auth.identity import Identity
from app.application.ports.identity_provider import AuthorizationRequest

if TYPE_CHECKING:
    from app.domain.auth.errors import AuthenticationError

DEFAULT_IDENTITY = Identity(
    subject="S-1-5-21-1",
    email="kim@neoine.example",
    name="김영업",
    groups=frozenset({"Sales-Team"}),
)


class FakeIdentityProvider:
    def __init__(self) -> None:
        self.identity = DEFAULT_IDENTITY
        self.fail_with: AuthenticationError | None = None
        self.completed: list[tuple[str, str, str]] = []

    async def authorization_request(self) -> AuthorizationRequest:
        return AuthorizationRequest(
            url="https://idp.example/authorize?state=fake-state",
            state="fake-state",
            nonce="fake-nonce",
            code_verifier="fake-verifier",
        )

    async def complete(self, *, code: str, code_verifier: str, nonce: str) -> Identity:
        self.completed.append((code, code_verifier, nonce))
        if self.fail_with is not None:
            raise self.fail_with
        return self.identity
