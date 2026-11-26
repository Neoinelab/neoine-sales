"""최초 설정 3단계 첫 admin 등록, AD 연동 흐름(SetupAdmin → SetupFirstAdmin).

SU-023~SU-031, SU-038.

local 흐름은 `test_setup_local_admin_cases.py`,
모든 경로가 닫히는 경우는 `test_setup_closed_cases.py`다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_FIRST, LOGIN_FAILED, STORAGE_FIRST
from app.application.directory.errors import DirectoryCredentialUnreadableError
from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError, TooManyAttemptsError
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidStateError, InvalidValueError
from tests.factories import NOW
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.support.auth_seed import (
    account_key,
    active_admin_logins,
    seed_auth_mode,
    seed_directory,
    seed_setup_prerequisites,
    seed_storage,
    seed_user,
)

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"
LEAK = "internal-ldap-server-banner"
PROFILE_FORBIDDEN = "AD 연동에서는 이름·이메일·전화번호를 입력하지 않습니다(AD 값을 씁니다)."


async def _register(
    auth: AuthStack,
    login_id: str = "kim",
    password: str = "pw-kim",  # noqa: S107 - 가짜 값
    **profile: str,
) -> IssuedSession:
    return await auth.setup.execute(
        login_id=login_id, password=Password(password), client_ip=IP, **profile
    )


async def test_an_ad_verified_account_becomes_the_first_admin_and_is_signed_in(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """AD 계정으로 확인된 사람이 첫 admin이 되어 로그인된다.

    테스트 코드: SU-023
    """
    # given: AD 서버·저장 위치가 등록되었고 AD 계정 kim(김관리, kim@corp.test)이 있다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    stored = await seed_directory(uow_factory)
    await seed_storage(uow_factory)
    auth.directory.add_account("kim", "pw-kim", display_name="김관리", email="kim@corp.test")

    # when: 맞는 비밀번호로 첫 admin을 등록한다
    issued = await _register(auth)

    # then: AD 값으로 admin 주체가 만들어지고 세션으로 인증된다
    principal = issued.principal
    assert (principal.subject, principal.name, principal.email, principal.role) == (
        "kim",
        "김관리",
        "kim@corp.test",
        Role.ADMIN,
    )
    assert (await auth.authenticate.execute(issued.token)).user_id == principal.user_id
    # then: kim은 admin이고 등록자 필드 없이 마지막 로그인 시각이 있으며 해시가 저장되었다
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert (user.role, user.last_login_at) == (Role.ADMIN, NOW)
    assert not hasattr(user, "created_by_user_id")
    saved_hash = await uow.password_hashes.get(user.id)
    assert saved_hash is not None
    assert await auth.hasher.verify(Password("pw-kim"), saved_hash)
    # then: AD 인증은 저장된 설정(복호화한 비밀번호·Base DN)으로 1회
    assert len(auth.directory.authenticate_calls) == 1
    call = auth.directory.authenticate_calls[0]
    assert (call.settings.connection, call.base_dn) == (stored.connection, stored.base_dn)
    assert call.password == "pw-kim"  # noqa: S105 - 가짜 값
    assert call.settings.credentials is None
    # then: 진행 상태는 모두 끝났고 AD 설정이 있으며 실패 횟수는 없다
    status = await auth.status.execute()
    assert (status.needs_directory_setup, status.needs_storage_setup, status.needs_admin_setup) == (
        False,
        False,
        False,
    )
    assert status.directory_configured is True
    assert account_key("kim") not in uow.login_failures._items


@pytest.mark.parametrize("login_id", ["kim", "ghost"], ids=["wrong-password", "unknown-id"])
async def test_a_wrong_password_is_a_401_that_registers_nobody_and_counts_one_failure(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, login_id: str
) -> None:
    """AD 비밀번호가 틀리면 401이고 아무도 등록되지 않으며 실패 1회가 남는다.

    테스트 코드: SU-024
    """
    # given: AD 서버·저장 위치가 등록되었고 AD 계정 kim이 있다
    await seed_setup_prerequisites(uow_factory)

    # when: 틀린 비밀번호로(또는 AD에 없는 아이디로) 첫 admin을 등록한다
    with pytest.raises(AuthenticationError) as caught:
        await _register(auth, login_id, "wrong")

    # then: 로그인 실패 문구이고 세션·사용자·해시가 없으며 admin 단계는 그대로, 실패 1회
    assert str(caught.value) == LOGIN_FAILED
    assert uow.sessions._items == {}
    assert uow.password_hashes._items == {}
    assert await active_admin_logins(uow_factory) == []
    assert (await auth.status.execute()).needs_admin_setup is True
    assert uow.login_failures._items[account_key(login_id)].failures == 1


async def test_a_malformed_login_id_is_a_401_that_never_reaches_the_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """AD 방식에서 형식이 틀린 아이디는 AD에 보내지 않고 401이다.

    테스트 코드: SU-025
    """
    # given: AD 서버·저장 위치가 등록되었다
    await seed_setup_prerequisites(uow_factory)

    # when: 아이디 "bad id!"로 첫 admin을 등록한다
    with pytest.raises(AuthenticationError) as caught:
        await _register(auth, "bad id!")

    # then: 로그인 실패 문구이고 AD 호출은 0회다
    assert str(caught.value) == LOGIN_FAILED
    assert auth.directory.authenticate_calls == []


@pytest.mark.parametrize(
    "failure",
    [
        DirectoryUnavailableError(LEAK, stage=VerificationStage.TLS),
        DirectoryCredentialUnreadableError(),
    ],
    ids=["tls-outage", "unreadable-bind-password"],
)
async def test_a_directory_outage_is_raised_without_fallback_and_not_counted(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    failure: DirectoryUnavailableError,
) -> None:
    """AD 장애·바인드 비밀번호 복호화 불가는 장애 오류이며 해시로 대신하지 않고 실패로 세지 않는다.

    테스트 코드: SU-026
    """
    # given: AD 서버·저장 위치가 등록되었고, AD 인증이 TLS 단계 장애로 실패하거나 저장된 바인드
    # 비밀번호를 복호화할 수 없다
    if isinstance(failure, DirectoryCredentialUnreadableError):
        await seed_auth_mode(uow_factory, AuthMode.AD)
        await seed_directory(uow_factory)
        auth.directory.authenticate_fails_with = failure
        await seed_storage(uow_factory)
    else:
        await seed_setup_prerequisites(uow_factory)
        auth.directory.authenticate_fails_with = failure

    # when: 첫 admin을 등록한다
    with pytest.raises(DirectoryUnavailableError):
        await _register(auth)

    # then: 해시 대체 인증이 없고 사용자는 등록되지 않으며 실패 횟수는 늘지 않는다
    assert auth.hasher.verify_calls == []
    assert await active_admin_logins(uow_factory) == []
    assert uow.login_failures._items == {}
    assert uow.sessions._items == {}


async def test_after_five_failures_even_the_right_password_is_throttled_without_a_directory_call(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """첫 admin 등록이 5번 실패하면 올바른 비밀번호도 429이고 AD를 부르지 않는다.

    테스트 코드: SU-027
    """
    # given: AD 서버·저장 위치가 등록되었고 kim으로 틀린 비밀번호 등록이 5번 실패했다
    await seed_setup_prerequisites(uow_factory)
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(AuthenticationError):
            await _register(auth, "kim", "wrong")
    calls_before = len(auth.directory.authenticate_calls)

    # when: 맞는 비밀번호로 kim 첫 admin을 등록한다
    with pytest.raises(TooManyAttemptsError):
        await _register(auth)

    # then: 제한 오류이고 AD 호출은 늘지 않는다
    assert len(auth.directory.authenticate_calls) == calls_before


@pytest.mark.parametrize(
    ("has_directory", "has_storage", "message"),
    [
        (False, False, DIRECTORY_FIRST),
        (False, True, DIRECTORY_FIRST),
        (True, False, STORAGE_FIRST),
    ],
    ids=["nothing", "storage-only", "directory-only"],
)
async def test_a_missing_prerequisite_is_a_409_that_skips_the_directory_and_the_counter(  # noqa: PLR0913
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    *,
    has_directory: bool,
    has_storage: bool,
    message: str,
) -> None:
    """AD 서버나 저장 위치가 없으면 첫 admin 등록은 409이고 AD를 부르지 않으며 실패로 세지 않는다.

    테스트 코드: SU-028
    """
    # given: (가) 방식·AD 설정이 없다 / (나) 저장 위치만 있다 / (다) AD 설정만 있고 저장 위치가 없다
    if has_directory:
        await seed_auth_mode(uow_factory, AuthMode.AD)
        await seed_directory(uow_factory)
    if has_storage:
        await seed_storage(uow_factory)

    # when: AD 계정 kim으로 첫 admin을 등록한다
    with pytest.raises(InvalidStateError) as caught:
        await _register(auth)

    # then: 해당 선행 단계 문구이고 AD 호출 0회, 사용자 없음, 실패 횟수 0
    assert str(caught.value) == message
    assert auth.directory.authenticate_calls == []
    assert await active_admin_logins(uow_factory) == []
    assert uow.login_failures._items == {}


async def test_an_existing_active_login_id_is_already_exists_and_is_not_promoted(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """같은 아이디의 재직 사용자가 있으면 AD 첫 admin 등록은 already-exists이고 승격하지 않는다.

    테스트 코드: SU-029
    """
    # given: 재직 sales 사용자 kim이 있고(admin 없음) AD 서버·저장 위치와 AD 계정 kim이 있다
    await seed_setup_prerequisites(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)

    # when: kim으로 첫 admin을 등록한다
    with pytest.raises(AlreadyExistsError) as caught:
        await _register(auth)

    # then: "이미 존재하는 사용자입니다: kim"이고 kim의 역할은 sales 그대로, 설정은 열린 채
    assert str(caught.value) == "이미 존재하는 사용자입니다: kim"
    existing = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert existing is not None
    assert existing.role is Role.SALES
    assert (await auth.status.execute()).needs_admin_setup is True


@pytest.mark.parametrize(
    "profile",
    [{"display_name": "x"}, {"email": "a@b.co"}, {"phone": "010-1234-5678"}],
    ids=["display_name", "email", "phone"],
)
async def test_profile_fields_in_ad_mode_are_invalid_and_never_reach_the_directory(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, profile: dict[str, str]
) -> None:
    """AD 방식에 이름·이메일·전화를 보내면 422이고 AD를 부르지 않는다.

    테스트 코드: SU-030
    """
    # given: AD 서버·저장 위치가 등록되었다
    await seed_setup_prerequisites(uow_factory)

    # when: display_name·email·phone 중 하나를 넣어 첫 admin을 등록한다
    with pytest.raises(InvalidValueError) as caught:
        await _register(auth, **profile)

    # then: 고정 문구이고 AD 호출 0회, 사용자 없음
    assert str(caught.value) == PROFILE_FORBIDDEN
    assert auth.directory.authenticate_calls == []
    assert await active_admin_logins(uow_factory) == []


async def test_a_mode_switched_to_local_during_the_directory_check_is_a_409(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """AD 인증 뒤 인증 방식이 local로 바뀌었으면 AD 첫 admin 등록은 409이고 아무도 등록되지 않는다.

    테스트 코드: SU-031
    """
    # given: AD 방식 등록에서 AD 인증 뒤 방식이 local로 바뀌어 있다
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_setup_prerequisites(uow_factory)
    original = auth.directory.authenticate

    async def switch_after_check(*args, **kwargs):  # type: ignore[no-untyped-def]  # noqa: ANN002, ANN003, ANN202
        found = await original(*args, **kwargs)
        await seed_auth_mode(uow_factory, AuthMode.LOCAL)
        return found

    auth.directory.authenticate = switch_after_check  # type: ignore[method-assign]

    # when: 등록이 저장 단계에 이른다
    with pytest.raises(InvalidStateError) as caught:
        await auth.setup_admin.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: "AD 연동 모드에서만 쓸 수 있습니다."이고 사용자·해시가 생기지 않는다
    assert str(caught.value) == "AD 연동 모드에서만 쓸 수 있습니다."
    assert await uow.users.get_active_by_login_id(LoginId("kim")) is None
    assert uow.password_hashes._items == {}


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [("dev-admin", "dev-admin"), ("DEV-SALES", "dev-sales"), ("dev-user", "dev-user")],
)
async def test_reserved_ids_are_rejected_in_ad_mode_and_a_normal_account_still_works(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, raw: str, normalized: str
) -> None:
    """AD 방식에서 예약 아이디로는 첫 admin을 만들 수 없고 이후 일반 계정으로는 된다.

    테스트 코드: SU-038
    """
    # given: AD 방식(AD 서버·저장 위치 등록)이고 예약 아이디도 AD 계정으로는 있다
    await seed_setup_prerequisites(uow_factory)
    auth.directory.add_account(normalized, "pw-reserved")

    # when: 예약 아이디로 등록하고, 이어서 일반 계정 kim으로 등록한다
    with pytest.raises(InvalidValueError) as caught:
        await _register(auth, raw, "pw-reserved")
    assert uow.login_failures._items == {}
    assert auth.directory.authenticate_calls == []
    issued = await _register(auth)

    # then: 예약 아이디는 정규화한 아이디가 담긴 문구의 422이고 AD 호출 0회·실패 0회였다
    assert str(caught.value) == f"개발 로그인 전용 아이디는 등록할 수 없습니다: {normalized}"
    # then: kim 등록은 성공한다
    assert issued.principal.subject == "kim"
    assert await active_admin_logins(uow_factory) == ["kim"]


async def test_a_dev_prefixed_id_that_is_not_reserved_is_an_ordinary_account(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """dev-qa 같은 다른 dev- 아이디는 예약 아이디가 아니라 일반 아이디다.

    테스트 코드: SU-038
    """
    # given: AD 서버·저장 위치가 등록되었고 AD 계정 dev-qa가 있다
    await seed_setup_prerequisites(uow_factory)
    auth.directory.add_account("dev-qa", "pw-qa")

    # when: dev-qa로 첫 admin을 등록한다
    issued = await _register(auth, "dev-qa", "pw-qa")

    # then: 등록된다
    assert issued.principal.subject == "dev-qa"


@pytest.mark.parametrize(
    ("login_id", "directory_phone", "stored"),
    [("kim", "02-123-4567", "02-123-4567"), ("lee", None, None)],
    ids=["with-directory-phone", "without-directory-phone"],
)
async def test_the_first_ad_admin_gets_the_directory_phone(  # noqa: PLR0913, PLR0917
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    login_id: str,
    directory_phone: str | None,
    stored: str | None,
) -> None:
    """AD 계정으로 확인된 첫 admin에는 AD의 전화번호가 있으면 저장되고 없으면 비어 있다.

    테스트 코드: SU-079
    """
    # given: AD 서버·저장 위치가 등록된 새 시스템, 경우마다 전화가 있거나 없는 AD 계정
    await seed_auth_mode(uow_factory, AuthMode.AD)
    await seed_directory(uow_factory)
    await seed_storage(uow_factory)
    auth.directory.add_account(
        login_id,
        "pw-kim",
        display_name="김관리",
        email=f"{login_id}@corp.test",
        phone=directory_phone,
    )

    # when: 맞는 비밀번호로 첫 admin을 등록한다
    issued = await _register(auth, login_id)

    # then: 등록되고 admin 행의 전화는 AD 값(없으면 null)이다
    assert issued.principal.subject == login_id
    user = await uow.users.get_active_by_login_id(LoginId(login_id))
    assert user is not None
    assert (user.role, user.phone) == (Role.ADMIN, stored)
