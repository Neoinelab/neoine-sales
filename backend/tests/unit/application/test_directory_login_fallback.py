"""DirectoryLogin의 대체 로그인: AD가 답할 수 없을 때만 저장된 해시로 인증한다(AC10·AC14·AC15).

대체 로그인 판정 대상 단계는 설정 없음·연결·TLS·서비스 계정 바인드·Base DN·검색 2건 이상·
저장된 바인드 비밀번호 복호화 실패·단계 없는 통신 실패다. AD가 응답해 비밀번호가 틀렸거나 사용자가
없으면 해시가 맞아도 거부한다(test_directory_login.py). 실패는 모두 원래 AD 불가 응답으로 같게
돌려주고 실패 1회로 센다.
"""

import hashlib
import logging
import re
from typing import TYPE_CHECKING

import pytest

from app.application.auth.fallback_login import DirectoryWarningStage
from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED, FALLBACK_MESSAGES
from app.application.directory.errors import DirectoryCredentialUnreadableError
from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import TooManyAttemptsError
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories import NOW
from tests.factories_auth import BIND_PASSWORD
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.support.auth_seed import account_key, seed_directory, seed_password_hash, seed_user

if TYPE_CHECKING:
    from app.application.auth.directory_login import LoginOutcome
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

IP = "10.0.0.1"
LOGIN_HASH_LENGTH = 12


class Down:
    """AD가 답할 수 없는 상황 하나. arrange가 Fake/저장소를 그 상태로 만든다."""

    def __init__(self, stage: DirectoryWarningStage) -> None:
        self.stage = stage

    async def arrange(self, auth: AuthStack, uow_factory: UnitOfWorkFactory) -> None:
        if self.stage is DirectoryWarningStage.NOT_CONFIGURED:
            return  # 설정 행이 없다
        await seed_directory(uow_factory)
        if self.stage is DirectoryWarningStage.CREDENTIAL_UNREADABLE:
            auth.cipher.fail_unseal = True
            return
        auth.directory.authenticate_fails_with = _FAULTS[self.stage]


_FAULTS: dict[DirectoryWarningStage, DirectoryUnavailableError] = {
    DirectoryWarningStage.CONNECT: DirectoryUnavailableError(stage=VerificationStage.CONNECT),
    DirectoryWarningStage.TLS: DirectoryUnavailableError(stage=VerificationStage.TLS),
    DirectoryWarningStage.SERVICE_BIND: DirectoryMisconfiguredError(
        stage=VerificationStage.SERVICE_BIND
    ),
    DirectoryWarningStage.BASE_DN: DirectoryMisconfiguredError(stage=VerificationStage.BASE_DN),
    DirectoryWarningStage.SEARCH: DirectoryMisconfiguredError(stage=VerificationStage.SEARCH),
    DirectoryWarningStage.UNKNOWN: DirectoryUnavailableError("통신 실패"),
}
DOWN_STAGES = list(DirectoryWarningStage)


@pytest.fixture
async def people(uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork) -> dict[str, User]:
    """AD 로그인 성공 이력(해시)이 있는 sales kim, admin boss, user viewer. 프로필도 채워 둔다."""
    users: dict[str, User] = {}
    for login_id, role in (("kim", Role.SALES), ("boss", Role.ADMIN), ("viewer", Role.USER)):
        user = await seed_user(uow_factory, login_id, role)
        user.record_login(NOW, display_name=f"{login_id} 이름", email=f"{login_id}@corp.test")
        async with uow_factory() as active:
            await active.users.update(user)
            await active.commit()
        await seed_password_hash(uow_factory, user, f"pw-{login_id}")
        users[login_id] = user
    return users


async def _login(
    auth: AuthStack, login_id: str = "kim", password: str | None = None
) -> LoginOutcome:
    return await auth.login.execute(
        login_id=login_id, password=Password(password or f"pw-{login_id}"), client_ip=IP
    )


@pytest.mark.parametrize("stage", DOWN_STAGES, ids=lambda s: s.value)
async def test_fallback_login_succeeds_for_each_unavailable_stage(  # noqa: PLR0913, PLR0917
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    clock: FixedClock,
    people: dict[str, User],
    stage: DirectoryWarningStage,
) -> None:
    await Down(stage).arrange(auth, uow_factory)
    clock.advance(3600)
    saved = dict(uow.password_hashes._items)

    outcome = await _login(auth)

    assert outcome.session.principal.subject == "kim"
    assert outcome.session.principal.role is Role.SALES
    assert (await auth.authenticate.execute(outcome.session.token)).subject == "kim"
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.last_login_at == clock.now()
    assert (user.display_name, user.email) == ("kim 이름", "kim@corp.test")  # 디렉터리 값이 없다
    assert uow.password_hashes._items == saved  # 해시는 그대로
    assert auth.hasher.hash_calls == 0
    assert account_key("kim") not in uow.login_failures._items  # 실패 카운터 초기화


async def test_fallback_login_clears_failures_counted_before(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, people: dict[str, User]
) -> None:
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)
    with pytest.raises(DirectoryUnavailableError):
        await _login(auth, "kim", "wrong-pw")
    assert uow.login_failures._items[account_key("kim")].failures == 1

    await _login(auth)

    assert account_key("kim") not in uow.login_failures._items


async def test_fallback_login_logs_a_warning_with_stage_and_hashed_login_id_only(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    people: dict[str, User],
    caplog: pytest.LogCaptureFixture,
) -> None:
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)
    caplog.set_level(logging.DEBUG)

    await _login(auth)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    texts = [r.getMessage() for r in warnings if "AD 대체 로그인" in r.getMessage()]
    assert len(texts) == 1
    expected = hashlib.sha256(b"kim").hexdigest()[:LOGIN_HASH_LENGTH]
    assert re.search(rf"stage=connect login_id_hash={expected}\b", texts[0])
    assert "pw-kim" not in caplog.text
    assert "fake$" not in caplog.text  # 해시 값도 없다
    assert not re.search(r"\bkim\b", texts[0])  # 아이디 원문 없음


@pytest.mark.parametrize("stage", DOWN_STAGES, ids=lambda s: s.value)
async def test_admin_fallback_login_returns_directory_warning(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    people: dict[str, User],
    stage: DirectoryWarningStage,
) -> None:
    await Down(stage).arrange(auth, uow_factory)

    outcome = await _login(auth, "boss")

    assert outcome.directory_warning is not None
    assert outcome.directory_warning.stage is stage
    assert outcome.directory_warning.message == FALLBACK_MESSAGES[stage]
    assert outcome.session.principal.role is Role.ADMIN


@pytest.mark.parametrize("login_id", ["kim", "viewer"])
@pytest.mark.parametrize("stage", DOWN_STAGES, ids=lambda s: s.value)
async def test_non_admin_fallback_login_has_no_warning(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    people: dict[str, User],
    stage: DirectoryWarningStage,
    login_id: str,
) -> None:
    await Down(stage).arrange(auth, uow_factory)

    outcome = await _login(auth, login_id)

    assert outcome.directory_warning is None


async def test_fallback_login_of_an_unreadable_credential_logs_the_key_hint_without_values(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    people: dict[str, User],
    caplog: pytest.LogCaptureFixture,
) -> None:
    stored = await seed_directory(uow_factory)
    auth.cipher.fail_unseal = True
    caplog.set_level(logging.DEBUG)

    await _login(auth, "boss")

    assert "AD 바인드 비밀번호를 복호화하지 못했습니다(암호화 키 변경 여부 확인)" in caplog.text
    assert BIND_PASSWORD not in caplog.text
    assert stored.sealed_bind_password.token not in caplog.text
    assert auth.directory.authenticate_calls == []  # 복호화하지 못하면 AD를 부르지 않는다


async def test_a_wrong_password_never_falls_back_when_the_directory_is_down(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, people: dict[str, User]
) -> None:
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)

    with pytest.raises(DirectoryUnavailableError):
        await _login(auth, "kim", "not-the-password")

    assert uow.sessions._items == {}
    assert uow.login_failures._items[account_key("kim")].failures == 1


async def test_fallback_without_a_configuration_fails_with_the_not_configured_message(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    with pytest.raises(InvalidStateError) as caught:
        await _login(auth)  # 사용자도 해시도 없다

    assert str(caught.value) == DIRECTORY_NOT_CONFIGURED
    assert uow.login_failures._items[account_key("kim")].failures == 1


async def test_fallback_failure_with_an_unreadable_credential_is_the_unreadable_error(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory, unreadable=True)
    await seed_user(uow_factory, "kim", Role.SALES)  # 해시가 없다

    with pytest.raises(DirectoryCredentialUnreadableError) as caught:
        await _login(auth)

    assert isinstance(caught.value, DirectoryUnavailableError)
    assert BIND_PASSWORD not in f"{caught.value!s}{caught.value!r}"


@pytest.mark.parametrize("case", ["unregistered", "resigned", "no-hash", "mismatch", "duplicate"])
async def test_fallback_failure_returns_original_error_and_counts_failure(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    people: dict[str, User],
    case: str,
) -> None:
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)
    login_id, password = "kim", "pw-kim"
    if case == "unregistered":
        login_id, password = "newbie", "pw-newbie"
    elif case == "resigned":
        gone = await seed_user(uow_factory, "gone", Role.SALES, resigned=True)
        await seed_password_hash(uow_factory, gone, "pw-gone")  # 해시가 남아 있어도 거부
        login_id, password = "gone", "pw-gone"
    elif case == "no-hash":
        await seed_user(uow_factory, "nohash", Role.SALES)
        login_id, password = "nohash", "pw-nohash"
    elif case == "mismatch":
        password = "pw-boss"  # noqa: S105 - 다른 사람의 가짜 비밀번호
    else:
        await seed_user(uow_factory, "kim", Role.USER)  # 재직 행이 둘이 된다

    with pytest.raises(DirectoryUnavailableError) as caught:
        await _login(auth, login_id, password)

    assert caught.value is _FAULTS[DirectoryWarningStage.CONNECT]  # 원인을 바꾸거나 숨기지 않는다
    assert uow.sessions._items == {}
    assert uow.login_failures._items[account_key(login_id)].failures == 1


@pytest.mark.parametrize("case", ["unregistered", "no-hash"])
async def test_fallback_without_hash_still_runs_verify(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, people: dict[str, User], case: str
) -> None:
    """해시가 없어도 같은 비용의 더미 계산을 해 응답 시간으로 해시 유무가 드러나지 않는다."""
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)
    login_id = "newbie"
    if case == "no-hash":
        await seed_user(uow_factory, "nohash", Role.SALES)
        login_id = "nohash"

    with pytest.raises(DirectoryUnavailableError):
        await _login(auth, login_id, "pw-anything")

    assert auth.hasher.verify_calls == [None]


async def test_fallback_login_is_blocked_while_locked(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, people: dict[str, User]
) -> None:
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(DirectoryUnavailableError):
            await _login(auth, "kim", "wrong-pw")
    verified = len(auth.hasher.verify_calls)

    with pytest.raises(TooManyAttemptsError):
        await _login(auth)  # 올바른 비밀번호도 잠금 중에는 거부

    assert len(auth.hasher.verify_calls) == verified


async def test_fallback_login_of_a_user_deleted_during_the_login_fails_like_any_other(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, people: dict[str, User]
) -> None:
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)
    original_get = uow.users.get_active_by_login_id

    async def get_then_delete(login_id: LoginId) -> User | None:
        found = await original_get(login_id)
        assert found is not None
        await uow.users.delete(found.id)  # 다른 요청이 사용자를 삭제하고 커밋했다
        return found

    uow.users.get_active_by_login_id = get_then_delete  # type: ignore[method-assign]

    with pytest.raises(DirectoryUnavailableError):
        await _login(auth)

    assert uow.sessions._items == {}
    assert uow.login_failures._items[account_key("kim")].failures == 1


async def test_fallback_never_runs_when_the_directory_answers(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, people: dict[str, User]
) -> None:
    """AD가 정상 응답하면(성공) 대체 경로의 verify를 거치지 않는다."""
    await seed_directory(uow_factory)
    auth.directory.add_account("kim", "pw-kim")

    outcome = await _login(auth)

    assert outcome.directory_warning is None
    assert auth.hasher.verify_calls == []


async def test_verify_runs_without_an_open_unit_of_work(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, people: dict[str, User]
) -> None:
    """scrypt 검증(오래 걸림) 동안 DB 트랜잭션을 잡지 않는다: 읽기, 닫기, verify, 다시 열기."""
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)
    auth.hasher.open_units_probe = lambda: uow.open_units

    await _login(auth)
    with pytest.raises(DirectoryUnavailableError):
        await _login(auth, "kim", "wrong-pw")
    with pytest.raises(DirectoryUnavailableError):
        await _login(auth, "ghost", "pw-ghost")  # 사용자가 없을 때도 같다

    assert auth.hasher.open_units_at_verify == [0, 0, 0]


async def _resign_kim(uow: FakeUnitOfWork, clock: FixedClock) -> None:
    kim = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert kim is not None
    kim.resign(clock.now())
    await uow.users.update(kim)


async def test_a_user_resigned_during_verify_gets_the_original_error(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    clock: FixedClock,
    people: dict[str, User],
) -> None:
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)
    auth.hasher.during_verify = lambda: _resign_kim(uow, clock)

    with pytest.raises(DirectoryUnavailableError) as caught:
        await _login(auth)

    assert caught.value is _FAULTS[DirectoryWarningStage.CONNECT]
    assert uow.sessions._items == {}
    assert uow.login_failures._items[account_key("kim")].failures == 1


async def test_a_hash_changed_during_verify_gets_the_original_error(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    people: dict[str, User],
) -> None:
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)

    async def change_hash() -> None:
        await seed_password_hash(uow_factory, people["kim"], "changed-elsewhere")

    auth.hasher.during_verify = change_hash

    with pytest.raises(DirectoryUnavailableError):
        await _login(auth)

    assert uow.sessions._items == {}
    assert uow.login_failures._items[account_key("kim")].failures == 1


async def test_a_user_replaced_during_verify_gets_the_original_error(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    clock: FixedClock,
    people: dict[str, User],
) -> None:
    """검증 중 퇴사 후 같은 아이디로 다시 등록돼도(새 행) 예전 행의 해시로 들어오지 못한다."""
    await Down(DirectoryWarningStage.CONNECT).arrange(auth, uow_factory)

    async def resign_and_reregister() -> None:
        await _resign_kim(uow, clock)
        await seed_user(uow_factory, "kim", Role.SALES)

    auth.hasher.during_verify = resign_and_reregister

    with pytest.raises(DirectoryUnavailableError):
        await _login(auth)

    assert uow.sessions._items == {}
