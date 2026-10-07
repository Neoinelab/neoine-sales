from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from app.application.auth.authenticate import Authenticate
from app.application.auth.begin_login import BeginLogin
from app.application.auth.complete_login import CompleteLogin
from app.application.auth.dev_login import DevLogin
from app.application.auth.issue_session import IssueSession
from app.application.auth.login_state import LoginStateCodec, PendingLogin
from app.application.auth.logout import Logout
from app.application.auth.role_mapping import RoleMapper
from app.application.auth.tokens import hash_token
from app.domain.auth.errors import AccessDeniedError, AuthenticationError
from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.fakes.identity_provider import DEFAULT_IDENTITY, FakeIdentityProvider

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

SECRET = "s" * 40
TTL = timedelta(hours=8)


@pytest.fixture
def idp() -> FakeIdentityProvider:
    return FakeIdentityProvider()


@pytest.fixture
def codec(clock: FixedClock) -> LoginStateCodec:
    return LoginStateCodec(SECRET, clock)


@pytest.fixture
def issue(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> IssueSession:
    return IssueSession(uow_factory, clock, TTL)


@pytest.fixture
def complete(
    idp: FakeIdentityProvider, codec: LoginStateCodec, issue: IssueSession
) -> CompleteLogin:
    mapper = RoleMapper(admin_groups=["Sales-Admins"], sales_groups=["Sales-Team"])
    return CompleteLogin(idp, codec, mapper, issue)


class TestRoleMapper:
    def test_admin_wins_over_sales(self) -> None:
        mapper = RoleMapper(["Admins"], ["Team"])

        assert mapper.map(frozenset({"Team", "Admins"})) is Role.ADMIN
        assert mapper.map(frozenset({"Team"})) is Role.SALES

    def test_groups_are_compared_ignoring_case_and_unknown_groups_give_no_role(self) -> None:
        mapper = RoleMapper(["Admins"], ["Team"])

        assert mapper.map(frozenset({"ADMINS"})) is Role.ADMIN
        assert mapper.map(frozenset({"Other"})) is None
        assert mapper.map(frozenset()) is None


class TestLoginStateCodec:
    PENDING = PendingLogin(state="st", nonce="no", code_verifier="cv")

    def test_round_trip(self, codec: LoginStateCodec) -> None:
        assert codec.decode(codec.encode(self.PENDING)) == self.PENDING

    def test_tampered_token_is_rejected(self, codec: LoginStateCodec) -> None:
        payload, signature = codec.encode(self.PENDING).split(".")

        with pytest.raises(AuthenticationError):
            codec.decode(f"{payload}x.{signature}")

    def test_token_signed_with_another_secret_is_rejected(self, clock: FixedClock) -> None:
        token = LoginStateCodec("o" * 40, clock).encode(self.PENDING)

        with pytest.raises(AuthenticationError):
            LoginStateCodec(SECRET, clock).decode(token)

    def test_expired_token_is_rejected(self, codec: LoginStateCodec, clock: FixedClock) -> None:
        token = codec.encode(self.PENDING)
        clock.advance(601)

        with pytest.raises(AuthenticationError):
            codec.decode(token)

    @pytest.mark.parametrize("garbage", ["", "abc", "a.b", "....", "e30.e30"])
    def test_garbage_is_rejected(self, codec: LoginStateCodec, garbage: str) -> None:
        with pytest.raises(AuthenticationError):
            codec.decode(garbage)


class TestBeginLogin:
    async def test_returns_the_idp_url_and_a_signed_pending_token(
        self, idp: FakeIdentityProvider, codec: LoginStateCodec
    ) -> None:
        start = await BeginLogin(idp, codec).execute()

        assert start.redirect_url == "https://idp.example/authorize?state=fake-state"
        assert codec.decode(start.pending_token) == PendingLogin(
            "fake-state", "fake-nonce", "fake-verifier"
        )


class TestCompleteLogin:
    async def _pending(self, codec: LoginStateCodec) -> str:
        return codec.encode(PendingLogin("fake-state", "fake-nonce", "fake-verifier"))

    async def test_issues_a_session_with_the_mapped_role(
        self, complete: CompleteLogin, codec: LoginStateCodec, idp: FakeIdentityProvider
    ) -> None:
        issued = await complete.execute(
            code="c1", state="fake-state", pending_token=await self._pending(codec)
        )

        assert issued.principal.role is Role.SALES
        assert issued.principal.email == DEFAULT_IDENTITY.email
        assert issued.token
        assert idp.completed == [("c1", "fake-verifier", "fake-nonce")]

    async def test_state_mismatch_is_rejected_before_calling_the_idp(
        self, complete: CompleteLogin, codec: LoginStateCodec, idp: FakeIdentityProvider
    ) -> None:
        with pytest.raises(AuthenticationError):
            await complete.execute(
                code="c1", state="other", pending_token=await self._pending(codec)
            )

        assert idp.completed == []

    async def test_missing_pending_token_is_rejected(self, complete: CompleteLogin) -> None:
        with pytest.raises(AuthenticationError):
            await complete.execute(code="c1", state="fake-state", pending_token=None)

    async def test_idp_failure_is_propagated(
        self, complete: CompleteLogin, codec: LoginStateCodec, idp: FakeIdentityProvider
    ) -> None:
        idp.fail_with = AuthenticationError("id_token 검증 실패")

        with pytest.raises(AuthenticationError):
            await complete.execute(
                code="c1", state="fake-state", pending_token=await self._pending(codec)
            )

    async def test_user_without_a_mapped_group_is_denied_and_gets_no_session(
        self,
        complete: CompleteLogin,
        codec: LoginStateCodec,
        idp: FakeIdentityProvider,
        uow: FakeUnitOfWork,
    ) -> None:
        idp.identity = DEFAULT_IDENTITY.__class__(
            subject="x", email=None, name="외부인", groups=frozenset({"Marketing"})
        )

        with pytest.raises(AccessDeniedError):
            await complete.execute(
                code="c1", state="fake-state", pending_token=await self._pending(codec)
            )

        assert uow.commits == 0


class TestIssueAndAuthenticate:
    async def test_a_token_authenticates_until_it_expires(
        self, issue: IssueSession, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        issued = await DevLogin(issue).execute(Role.ADMIN)
        authenticate = Authenticate(uow_factory, clock)

        principal = await authenticate.execute(issued.token)
        clock.advance(int(TTL.total_seconds()))

        assert principal.role is Role.ADMIN
        assert issued.expires_at == NOW + TTL
        with pytest.raises(AuthenticationError):
            await authenticate.execute(issued.token)

    async def test_only_the_hash_of_the_token_is_stored(
        self, issue: IssueSession, uow: FakeUnitOfWork
    ) -> None:
        issued = await DevLogin(issue).execute(Role.SALES)

        assert await uow.sessions.get_by_token_hash(issued.token) is None
        assert await uow.sessions.get_by_token_hash(hash_token(issued.token)) is not None

    @pytest.mark.parametrize("token", [None, "", "unknown-token"])
    async def test_missing_or_unknown_token_is_unauthenticated(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, token: str | None
    ) -> None:
        with pytest.raises(AuthenticationError):
            await Authenticate(uow_factory, clock).execute(token)

    async def test_tokens_are_unique(self, issue: IssueSession) -> None:
        first = await DevLogin(issue).execute(Role.SALES)
        second = await DevLogin(issue).execute(Role.SALES)

        assert first.token != second.token


class TestLogout:
    async def test_revokes_the_session(
        self, issue: IssueSession, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        issued = await DevLogin(issue).execute(Role.SALES)

        await Logout(uow_factory, clock).execute(issued.token)

        with pytest.raises(AuthenticationError):
            await Authenticate(uow_factory, clock).execute(issued.token)

    @pytest.mark.parametrize("token", [None, "unknown"])
    async def test_is_idempotent_for_missing_sessions(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock, token: str | None
    ) -> None:
        await Logout(uow_factory, clock).execute(token)

    async def test_revoking_twice_is_harmless(
        self, issue: IssueSession, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        issued = await DevLogin(issue).execute(Role.SALES)
        logout = Logout(uow_factory, clock)

        await logout.execute(issued.token)
        await logout.execute(issued.token)
