"""LocalLogin·PasswordLogin: local 모드는 저장 해시로 인증한다.

없는 아이디·퇴사자·해시 없음·불일치는 모두 같은 LOGIN_FAILED이고 같은 비용(verify(None) 더미)을
쓰며, 실패는 기존 시도 제한(아이디 5회, IP 30회)에 센다. AD 어댑터는 한 번도 부르지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError, TooManyAttemptsError
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.fakes.auth_stack import LOCK, MAX_PER_ACCOUNT, SESSION_TTL
from tests.support.auth_seed import (
    account_key,
    seed_auth_mode,
    seed_directory,
    seed_local_user,
    seed_user,
)

if TYPE_CHECKING:
    from app.application.auth.directory_login import LoginOutcome
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

IP = "10.0.0.1"
PW = "pw-kim-1234"  # 가짜 값


@pytest.fixture(autouse=True)
async def _local_mode(uow_factory: UnitOfWorkFactory) -> None:
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)


async def _login(auth: AuthStack, login_id: str = "kim", password: str = PW) -> LoginOutcome:
    return await auth.password_login.execute(
        login_id=login_id, password=Password(password), client_ip=IP
    )


# ---- LocalLogin ----


async def test_local_login_with_right_password_returns_the_principal_and_records_login(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """local 사용자가 자기 비밀번호로 로그인하면 주체를 받고 로그인 시각이 남는다.

    테스트 코드: AU-035
    """
    # given: local 모드이고 sales kim에게 비밀번호 해시가 있다
    user = await seed_local_user(uow_factory, "kim", PW, Role.SALES, display_name="김영업")

    # when: kim이 올바른 비밀번호로 로그인한다
    principal = await auth.local_login.execute(LoginId("kim"), Password(PW))

    # then: users 행의 id·역할을 가진 주체이고 로그인 시각이 갱신된다
    assert (principal.user_id, principal.subject, principal.role) == (user.id, "kim", Role.SALES)
    assert (await uow.users.get(user.id)).last_login_at == NOW


async def test_local_login_keeps_the_stored_profile(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """local 로그인은 이름·이메일·전화를 덮어쓰지 않는다.

    테스트 코드: AU-035
    """
    # given: 이름·이메일·전화가 저장된 local 사용자 kim
    user = await seed_local_user(
        uow_factory, "kim", PW, display_name="김영업", email="kim@corp.test", phone="010-1234-5678"
    )

    # when: kim이 로그인한다
    await auth.local_login.execute(LoginId("kim"), Password(PW))

    # then: 프로필이 그대로다
    stored = await uow.users.get(user.id)
    assert (stored.display_name, stored.email, stored.phone) == (
        "김영업",
        "kim@corp.test",
        "010-1234-5678",
    )


async def test_local_login_wrong_password_is_login_failed_and_does_not_record_login(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """local 모드의 틀린 비밀번호는 공통 실패이고 로그인 시각이 남지 않는다.

    테스트 코드: AU-036
    """
    # given: local 사용자 kim
    user = await seed_local_user(uow_factory, "kim", PW)

    # when: 틀린 비밀번호로 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.local_login.execute(LoginId("kim"), Password("wrong-password"))

    # then: 공통 실패 문구이고 로그인 시각이 비어 있다
    assert str(caught.value) == LOGIN_FAILED
    assert (await uow.users.get(user.id)).last_login_at is None


async def test_local_login_unknown_id_verifies_dummy_and_fails_alike(auth: AuthStack) -> None:
    """local 모드의 없는 아이디는 더미 검증 뒤 같은 공통 실패다.

    테스트 코드: AU-036
    """
    # when: 없는 아이디로 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.local_login.execute(LoginId("ghost"), Password(PW))

    # then: 공통 실패 문구이고 더미 해시 검증을 했다
    assert str(caught.value) == LOGIN_FAILED
    assert auth.hasher.verify_calls == [None]


async def test_local_login_resigned_user_fails_with_the_same_cost(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드의 퇴사자는 올바른 비밀번호로도 같은 비용의 공통 실패다.

    테스트 코드: AU-037
    """
    # given: 퇴사 처리된 local 사용자
    await seed_local_user(uow_factory, "gone", PW, resigned=True)

    # when: 올바른 비밀번호로 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.local_login.execute(LoginId("gone"), Password(PW))

    # then: 공통 실패 문구이고 더미 해시 검증을 했다
    assert str(caught.value) == LOGIN_FAILED
    assert auth.hasher.verify_calls == [None]


async def test_local_login_without_hash_fails_with_the_same_cost(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드에서 해시가 없는 사용자는 같은 비용의 공통 실패다.

    테스트 코드: AU-036
    """
    # given: 비밀번호 해시가 없는 사용자
    await seed_local_user(uow_factory, "kim", PW, with_hash=False)

    # when: 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.local_login.execute(LoginId("kim"), Password(PW))

    # then: 공통 실패 문구이고 더미 해시 검증을 했다
    assert str(caught.value) == LOGIN_FAILED
    assert auth.hasher.verify_calls == [None]


async def test_local_login_ambiguous_login_id_fails(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드에서 같은 아이디의 재직 행이 둘이면 공통 실패다.

    테스트 코드: AU-038
    """
    # given: kim의 재직 행이 둘이다
    await seed_local_user(uow_factory, "kim", PW)
    await seed_user(uow_factory, "kim", Role.SALES)  # 재직 행이 둘이 된 정합 위반

    # when: 올바른 비밀번호로 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.local_login.execute(LoginId("kim"), Password(PW))

    # then: 공통 실패 문구다
    assert str(caught.value) == LOGIN_FAILED


async def test_local_login_verifies_outside_any_transaction(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """local 로그인도 해시 검증 동안 트랜잭션을 잡지 않는다."""
    # given: local 사용자 kim, 검증 시점의 열린 UoW 수를 센다
    await seed_local_user(uow_factory, "kim", PW)
    auth.hasher.open_units_probe = lambda: uow.open_units

    # when: 로그인한다
    await auth.local_login.execute(LoginId("kim"), Password(PW))

    # then: 검증할 때 열린 UoW가 없다
    assert auth.hasher.open_units_at_verify == [0]


# ---- PasswordLogin ----


async def test_password_login_in_local_mode_issues_a_session_without_a_warning(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드 로그인은 경고 없이 세션을 발급한다.

    테스트 코드: AU-035
    """
    # given: local 모드의 admin kim
    await seed_local_user(uow_factory, "kim", PW, Role.ADMIN, display_name="김관리")

    # when: kim이 로그인한다
    outcome = await _login(auth)

    # then: 경고가 없고 세션이 만료 시각과 함께 발급되어 인증된다
    assert outcome.directory_warning is None
    assert outcome.session.expires_at == NOW + SESSION_TTL
    assert (await auth.authenticate.execute(outcome.session.token)).subject == "kim"


async def test_password_login_in_local_mode_never_calls_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드 로그인은 성공이든 실패든 AD를 부르지 않는다.

    테스트 코드: AU-039
    """
    # given: 남아 있는 AD 설정이 있어도 local 모드
    await seed_directory(uow_factory)  # 남아 있는 AD 설정이 있어도 쓰지 않는다
    await seed_local_user(uow_factory, "kim", PW)

    # when: 올바른 비밀번호와 틀린 비밀번호로 로그인한다
    await _login(auth)
    with pytest.raises(AuthenticationError):
        await _login(auth, password="wrong-password")  # noqa: S106

    # then: AD 호출이 한 번도 없다
    assert auth.directory.authenticate_calls == []
    assert auth.directory.discover_calls == []


async def test_password_login_wrong_password_counts_one_failure(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """local 모드의 틀린 비밀번호는 실패 1회로 센다.

    테스트 코드: AU-036
    """
    # given: local 사용자 kim
    await seed_local_user(uow_factory, "kim", PW)

    # when: 틀린 비밀번호로 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await _login(auth, password="wrong-password")  # noqa: S106

    # then: 공통 실패이고 실패가 1회 센다
    assert str(caught.value) == LOGIN_FAILED
    assert uow.login_failures._items[account_key("kim")].failures == 1


async def test_password_login_unknown_id_counts_and_fails_alike(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """local 모드의 없는 아이디도 같은 실패이고 실패로 센다.

    테스트 코드: AU-036, AU-049
    """
    # when: 없는 아이디로 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await _login(auth, "ghost")

    # then: 공통 실패이고 그 아이디의 실패가 1회 센다
    assert str(caught.value) == LOGIN_FAILED
    assert uow.login_failures._items[account_key("ghost")].failures == 1


async def test_password_login_success_clears_the_account_counter(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """local 로그인에 성공하면 아이디 실패 횟수가 지워진다.

    테스트 코드: AU-047
    """
    # given: local 사용자 kim이 한 번 실패했다
    await seed_local_user(uow_factory, "kim", PW)
    with pytest.raises(AuthenticationError):
        await _login(auth, password="wrong-password")  # noqa: S106

    # when: 올바른 비밀번호로 로그인한다
    await _login(auth)

    # then: kim의 실패 카운터가 없다
    assert account_key("kim") not in uow.login_failures._items


async def test_password_login_locked_account_is_429_without_verifying(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """local 모드도 잠긴 아이디는 올바른 비밀번호에도 429이고 검증하지 않는다.

    테스트 코드: AU-042
    """
    # given: local 사용자 kim이 한도만큼 실패했다
    await seed_local_user(uow_factory, "kim", PW)
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(AuthenticationError):
            await _login(auth, password="wrong-password")  # noqa: S106
    verified = len(auth.hasher.verify_calls)

    # when: 올바른 비밀번호로 로그인한다
    with pytest.raises(TooManyAttemptsError):
        await _login(auth)  # 올바른 비밀번호여도 잠겨 있다

    # then: 해시 검증을 더 하지 않았다
    assert len(auth.hasher.verify_calls) == verified


async def test_password_login_lock_ends_after_the_lock_duration(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """잠금 시간이 지나면 local 로그인이 다시 된다.

    테스트 코드: AU-045
    """
    # given: local 사용자 kim이 한도만큼 실패해 잠겼다
    await seed_local_user(uow_factory, "kim", PW)
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(AuthenticationError):
            await _login(auth, password="wrong-password")  # noqa: S106
    clock.advance(LOCK.total_seconds())

    # when: 잠금 시간이 지난 뒤 올바른 비밀번호로 로그인한다
    outcome = await _login(auth)

    # then: 로그인된다
    assert outcome.session.principal.subject == "kim"


# ---- 방식에 따른 분기 ----


async def test_password_login_without_mode_row_and_admin_uses_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """인증 방식 행이 없고 admin이 있는 시스템은 AD 로그인으로 처리한다.

    테스트 코드: AU-040
    """
    # given: 인증 방식 행이 없고 admin kim이 있으며 AD 설정이 있다
    uow.auth_settings._items.clear()
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.ADMIN)

    # when: kim이 로그인한다
    outcome = await _login(auth, "kim", "pw-kim")

    # then: AD 로그인으로 처리되어 AD를 한 번 부른다
    assert outcome.session.principal.subject == "kim"
    assert len(auth.directory.authenticate_calls) == 1


async def test_password_login_in_ad_mode_still_uses_the_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """ad 모드는 AD로 로그인한다."""
    # given: ad 모드, AD 설정과 sales kim
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)

    # when: kim이 로그인한다
    await _login(auth, "kim", "pw-kim")

    # then: AD를 한 번 부른다
    assert len(auth.directory.authenticate_calls) == 1


async def test_password_login_in_ad_mode_rejects_a_local_style_hash_when_the_directory_answers(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """ad 모드에서 AD가 응답하면 저장 해시가 맞아도 AD 판정을 따른다.

    테스트 코드: AU-041
    """
    # given: ad 모드, 해시가 있는 kim이지만 AD에는 그 비밀번호의 계정이 없다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    await seed_local_user(uow_factory, "kim", "stored-pass-1")

    # when·then: 해시와 같은 비밀번호로 로그인한다 → AD가 거절해 로그인에 실패한다
    with pytest.raises(AuthenticationError):
        await _login(auth, "kim", "stored-pass-1")
