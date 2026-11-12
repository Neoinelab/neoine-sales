"""AD 설정 조회·연결 테스트 GetDirectorySettings, TestDirectorySettings (AC3~AC6·AC10).

연결 테스트는 서비스 계정으로 Base DN을 찾고, 요청 admin이 새 설정으로 검색·바인드되는지 본다.
저장하지 않으며 실패는 예외 대신 결과(단계·안내)로 돌려준다. 비밀번호 입력 규칙 위반은 예외다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.directory.verify_settings import PASSWORD_REQUIRED
from app.application.ports.directory import (
    DirectoryMisconfiguredError,
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import Password
from app.domain.auth.errors import TooManyAttemptsError
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError, NotFoundError
from app.domain.directory.settings import DirectorySettingsDraft
from tests.factories_auth import BASE_DN, BIND_PASSWORD, WRONG_PASSWORD, make_principal
from tests.factories_directory import make_directory_connection
from tests.fakes.admin_stack import ADMIN_ACTOR, ADMIN_PASSWORD
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.support.auth_seed import account_key, seed_directory

if TYPE_CHECKING:
    from app.application.directory.test_settings import TestResult
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator

IP = "10.0.0.1"
NEW_CONNECTION = make_directory_connection(host="dc2.corp.test")
NEW_PASSWORD = "New-bind-pw-2!"  # noqa: S105 - 가짜 값


def _draft(
    connection: object = NEW_CONNECTION, bind_password: str | None = NEW_PASSWORD
) -> DirectorySettingsDraft:
    return DirectorySettingsDraft(
        connection=connection,  # type: ignore[arg-type]
        bind_password=None if bind_password is None else Password(bind_password),
    )


async def _test(
    admin: AdminStack,
    password: str | None = ADMIN_PASSWORD,
    draft: DirectorySettingsDraft | None = None,
) -> TestResult:
    return await admin.test_settings.execute(
        actor=ADMIN_ACTOR,
        draft=draft or _draft(),
        password=None if password is None else Password(password),
        client_ip=IP,
    )


async def test_get_settings_returns_the_stored_row_and_a_readable_credential(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """저장된 AD 설정을 조회하면 저장 행과 읽을 수 있는 비밀번호 상태가 나오고 비밀번호는 없다.

    테스트 코드: IN-001
    """
    # given: 예시 AD 설정이 저장되어 있다
    stored = await seed_directory(uow_factory)

    # when: AD 설정을 조회한다
    view = await admin.get_settings.execute()

    # then: 저장 행이 그대로 나오고 비밀번호 상태는 읽을 수 있음이며 표현에 비밀번호가 없다
    assert view.stored == stored
    assert view.credential_readable is True
    assert BIND_PASSWORD not in repr(view)


async def test_get_settings_reports_unreadable_credential(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """저장된 바인드 비밀번호를 풀 수 없어도 조회는 성공하고 상태만 알린다.

    테스트 코드: IN-002
    """
    # given: Fake 암호기가 풀 수 없는 암호문이 저장되어 있다(키 변경)
    stored = await seed_directory(uow_factory, unreadable=True)

    # when: AD 설정을 조회한다
    view = await admin.get_settings.execute()

    # then: 저장 행은 그대로이고 비밀번호 상태는 읽을 수 없음이다
    assert view.stored == stored
    assert view.credential_readable is False


async def test_get_settings_without_a_row_is_not_found(admin: AdminStack) -> None:
    """AD 설정 행이 없으면 조회는 NotFoundError다.

    테스트 코드: IN-003
    """
    # when·then: AD 설정을 조회한다 → NotFoundError가 난다 (전제: AD 설정 행이 없다)
    with pytest.raises(NotFoundError):
        await admin.get_settings.execute()


async def test_test_settings_discovers_base_dn_then_authenticates_the_admin(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """연결 테스트는 Base DN을 찾은 뒤 요청 admin을 그 Base DN으로 인증하고 찾은 값을 돌려준다.

    테스트 코드: IN-004
    """
    # given: 예시 AD 설정과, Base DN dc=found,dc=test를 찾아 주는 Fake AD
    await seed_directory(uow_factory)
    directory.base_dn = "dc=found,dc=test"

    result = await _test(admin)

    (discovered,) = directory.discover_calls
    assert discovered.connection == NEW_CONNECTION
    assert discovered.bind_password.reveal() == NEW_PASSWORD
    # when: 새 호스트와 새 바인드 비밀번호로 연결 테스트한다
    (call,) = directory.authenticate_calls
    # then: Base DN 탐색 뒤 admin 인증 순서로 AD를 불렀고 성공 결과에 찾은 Base DN이 있다
    assert (call.base_dn, call.login_id.value, call.password) == (
        "dc=found,dc=test",
        "root",
        ADMIN_PASSWORD,
    )
    assert call.settings == discovered
    assert result.success is True
    assert result.stage is None
    assert result.message
    assert result.base_dn == "dc=found,dc=test"


async def test_test_settings_returns_discovered_base_dn_on_success(admin: AdminStack) -> None:
    """연결 테스트가 성공하면 결과에 찾은 Base DN이 담긴다."""
    # when: 연결 테스트한다
    result = await _test(admin)

    # then: 성공 결과의 Base DN이 Fake AD가 찾은 값이다
    assert result.base_dn == BASE_DN


async def test_test_settings_never_saves(admin: AdminStack, uow_factory: UnitOfWorkFactory) -> None:
    """연결 테스트는 저장된 AD 설정을 바꾸지 않는다.

    테스트 코드: IN-004
    """
    # given: 예시 AD 설정이 저장되어 있다
    before = await seed_directory(uow_factory)

    await _test(admin)

    # when·then: 다른 값으로 연결 테스트한다
    #   → 저장된 설정(호스트·revision·암호문·저장자·시각)이 테스트 전과 같다
    async with uow_factory() as active:
        assert await active.directory_settings.get() == before


async def test_test_settings_reports_a_wrong_password_as_a_bind_failure_result(
    admin: AdminStack,
) -> None:
    """틀린 admin 비밀번호의 연결 테스트는 예외가 아니라 bind 단계 실패 결과다.

    테스트 코드: IN-005
    """
    # when: 틀린 admin 비밀번호로 연결 테스트한다
    result = await _test(admin, WRONG_PASSWORD)

    # then: success가 False, stage가 bind, Base DN이 없고 문구에 입력한 비밀번호가 없다
    assert result.success is False
    assert result.stage == VerificationStage.BIND
    assert result.base_dn is None
    assert result.message
    assert WRONG_PASSWORD not in result.message


@pytest.mark.parametrize(
    ("raise_in", "error", "stage"),
    [
        (
            "discover",
            DirectoryUnavailableError(stage=VerificationStage.CONNECT),
            VerificationStage.CONNECT,
        ),
        ("discover", DirectoryUnavailableError(stage=VerificationStage.TLS), VerificationStage.TLS),
        (
            "discover",
            DirectoryMisconfiguredError(stage=VerificationStage.SERVICE_BIND),
            VerificationStage.SERVICE_BIND,
        ),
        (
            "discover",
            DirectoryMisconfiguredError(stage=VerificationStage.BASE_DN),
            VerificationStage.BASE_DN,
        ),
        (
            "authenticate",
            InvalidCredentialsError(stage=VerificationStage.SEARCH),
            VerificationStage.SEARCH,
        ),
        (
            "authenticate",
            DirectoryMisconfiguredError(stage=VerificationStage.SEARCH),
            VerificationStage.SEARCH,
        ),
        (
            "authenticate",
            InvalidCredentialsError(stage=VerificationStage.BIND),
            VerificationStage.BIND,
        ),
        (
            "authenticate",
            DirectoryUnavailableError(stage=VerificationStage.CONNECT),
            VerificationStage.CONNECT,
        ),
    ],
)
async def test_test_settings_reports_each_failure_stage_without_raising(
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    raise_in: str,
    error: Exception,
    stage: VerificationStage,
) -> None:
    """연결 테스트는 AD가 실패한 단계를 예외 없이 결과의 단계로 알린다.

    테스트 코드: IN-006
    """
    # given: Fake AD가 connect·tls·service_bind·base_dn(탐색 중)
    #   또는 search·bind(인증 중)에서 실패한다
    if raise_in == "discover":
        directory.discover_fails_with = error  # type: ignore[assignment]
    else:
        directory.authenticate_fails_with = error  # type: ignore[assignment]

    # when: 연결 테스트한다
    result = await _test(admin)

    # then: success가 False이고 stage가 그 단계이며 안내 문구가 있다
    assert result.success is False
    assert result.stage == stage
    assert result.base_dn is None
    assert result.message


async def test_test_settings_does_not_authenticate_when_base_dn_discovery_fails(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    """Base DN을 찾지 못하면 admin 인증을 하지 않는다.

    테스트 코드: IN-007
    """
    # given: Fake AD의 Base DN 탐색이 service_bind 단계에서 실패한다
    directory.discover_fails_with = DirectoryMisconfiguredError(
        stage=VerificationStage.SERVICE_BIND
    )

    # when: 연결 테스트한다
    result = await _test(admin)

    # then: 결과 stage가 service_bind이고 Fake AD의 인증 호출은 0회다
    assert result.stage == VerificationStage.SERVICE_BIND
    assert directory.authenticate_calls == []


async def test_test_settings_without_an_admin_password_is_invalid_and_skips_the_admin_bind(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    """현재 admin 비밀번호 없이 연결 테스트하면 InvalidValueError이고 admin 바인드를 하지 않는다.

    테스트 코드: IN-014
    """
    # when·then: 비밀번호 없이 연결 테스트한다 → InvalidValueError가 나고 인증 호출이 0회다
    with pytest.raises(InvalidValueError):
        await _test(admin, None)

    assert directory.authenticate_calls == []


@pytest.mark.parametrize("subject", ["dev-admin", "dev-sales", "dev-user"])
async def test_a_test_without_the_admin_password_is_rejected_even_for_a_retired_dev_id(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, subject: str
) -> None:
    """예전 개발용 아이디의 admin도 비밀번호 없이는 같은 문구로 거절된다.

    테스트 코드: IN-014
    """
    # given: 예전 개발용 아이디(dev-admin 등)를 가진 admin
    actor = make_principal(subject, Role.ADMIN)

    # when·then: 비밀번호 없이 연결 테스트한다
    #   → 고정 문구의 InvalidValueError이고 AD 탐색·인증 호출이 0회다
    with pytest.raises(InvalidValueError) as caught:
        await admin.test_settings.execute(actor=actor, draft=_draft(), password=None, client_ip=IP)

    assert str(caught.value) == PASSWORD_REQUIRED
    assert directory.discover_calls == []
    assert directory.authenticate_calls == []


async def test_bind_failures_count_toward_the_admins_attempt_limit(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """admin 바인드 실패는 시도 제한에 쌓이고, 한도를 채우면 올바른 비밀번호도 AD 인증 없이 막힌다.

    테스트 코드: IN-030
    """
    # given: 틀린 비밀번호 테스트로 계정 실패 한도를 채웠다
    for _ in range(MAX_PER_ACCOUNT):
        await _test(admin, WRONG_PASSWORD)
    async with uow_factory() as uow:
        counter = await uow.login_failures.get_for_update(account_key("root"))
    calls = len(directory.authenticate_calls)

    # when·then: 올바른 비밀번호로 연결 테스트한다
    #   → TooManyAttemptsError이고 AD 인증 호출 수는 늘지 않으며 실패 횟수는 한도와 같다
    with pytest.raises(TooManyAttemptsError):
        await _test(admin)  # 올바른 비밀번호도 잠금 중에는 AD 인증을 부르지 않는다

    assert counter is not None
    assert counter.failures == MAX_PER_ACCOUNT
    assert len(directory.authenticate_calls) == calls


async def test_connection_failures_do_not_count_toward_the_attempt_limit(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    """연결 실패는 시도 제한 횟수에 들어가지 않는다.

    테스트 코드: IN-031
    """
    # given: Fake AD 인증이 connect 단계로 한도보다 많이 실패했다
    directory.authenticate_fails_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)
    for _ in range(MAX_PER_ACCOUNT + 1):
        await _test(admin)
    directory.authenticate_fails_with = None

    # when: 복구된 AD로 연결 테스트한다
    result = await _test(admin)

    # then: 잠기지 않고 성공한다
    assert result.success is True


async def test_test_settings_without_bind_password_uses_the_stored_one(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """바인드 비밀번호를 생략하면 저장된 비밀번호로 AD를 부른다.

    테스트 코드: IN-008
    """
    # given: 바인드 비밀번호 svc-pass가 저장된 예시 AD 설정
    stored = await seed_directory(uow_factory)
    keep = _draft(make_directory_connection(user_filter="(uid={login_id})"), bind_password=None)

    # when: 사용자 필터만 바꾸고 바인드 비밀번호를 생략해 연결 테스트한다
    result = await _test(admin, draft=keep)

    # then: AD 탐색에 저장된 비밀번호가 쓰이고 성공한다
    assert result.success is True
    assert directory.discover_calls[0].bind_password.reveal() == BIND_PASSWORD
    assert directory.discover_calls[0].connection.host == stored.connection.host


async def test_test_settings_without_bind_password_after_host_change_is_rejected_before_ad(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """호스트를 바꾸고 바인드 비밀번호를 생략하면 AD를 부르기 전에 InvalidValueError다.

    테스트 코드: IN-010
    """
    # given: 예시 AD 설정이 저장되어 있다
    await seed_directory(uow_factory)

    # when·then: 호스트를 바꾸고 바인드 비밀번호 없이 연결 테스트한다
    #   → bind_password 문구의 InvalidValueError이고 AD 호출이 0회다
    with pytest.raises(InvalidValueError) as caught:
        await _test(admin, draft=_draft(NEW_CONNECTION, bind_password=None))

    assert "bind_password" in str(caught.value)
    assert directory.discover_calls == []
    assert directory.authenticate_calls == []


async def test_test_settings_without_bind_password_and_no_stored_settings_is_rejected(
    admin: AdminStack, directory: FakeDirectoryAuthenticator
) -> None:
    """저장된 설정이 없으면 바인드 비밀번호 생략은 InvalidValueError다.

    테스트 코드: IN-012
    """
    # when·then: 바인드 비밀번호 없이 연결 테스트한다 (전제: AD 설정이 없다)
    #   → bind_password 문구의 InvalidValueError이고 AD 탐색 호출이 0회다
    with pytest.raises(InvalidValueError) as caught:
        await _test(admin, draft=_draft(make_directory_connection(), bind_password=None))

    assert "bind_password" in str(caught.value)
    assert directory.discover_calls == []


async def test_test_settings_without_bind_password_and_unreadable_stored_one_is_rejected(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """저장된 비밀번호를 풀 수 없으면 바인드 비밀번호 생략은 InvalidValueError다.

    테스트 코드: IN-013
    """
    # given: 저장된 바인드 비밀번호를 풀 수 없는 설정이 있다
    await seed_directory(uow_factory, unreadable=True)

    # when: 바인드 비밀번호를 생략하고 연결 테스트를 한다
    with pytest.raises(InvalidValueError) as caught:
        await _test(admin, draft=_draft(make_directory_connection(), bind_password=None))

    # then: bind_password 문구의 InvalidValueError이고 AD 탐색 호출이 0회다

    assert "bind_password" in str(caught.value)
    assert directory.discover_calls == []


async def test_test_settings_with_a_new_password_works_when_the_stored_one_is_unreadable(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """저장된 비밀번호를 풀 수 없어도 새 비밀번호를 보내면 연결 테스트가 통과한다.

    테스트 코드: IN-013
    """
    # given: 저장된 바인드 비밀번호를 풀 수 없는 설정이 있다
    await seed_directory(uow_factory, unreadable=True)

    # when: 새 바인드 비밀번호를 보내 연결 테스트를 한다
    result = await _test(admin, draft=_draft(make_directory_connection(), NEW_PASSWORD))

    # then: 연결 테스트가 성공한다
    assert result.success is True


async def test_test_settings_with_a_new_bind_password_leaves_the_stored_one_untouched(
    admin: AdminStack,
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
) -> None:
    """새 바인드 비밀번호로 연결 테스트해도 저장된 암호문과 비밀번호는 그대로다.

    테스트 코드: IN-009
    """
    # given: 바인드 비밀번호 svc-pass가 저장된 예시 AD 설정
    before = await seed_directory(uow_factory)
    keep_host = make_directory_connection()

    # when: 새 바인드 비밀번호로 연결 테스트한다
    result = await _test(admin, draft=_draft(keep_host, NEW_PASSWORD))

    # then: AD 탐색에는 새 비밀번호가 쓰이고, 저장된 암호문은 그대로여서 풀면 예전 비밀번호다
    assert result.success is True
    assert directory.discover_calls[0].bind_password.reveal() == NEW_PASSWORD
    async with uow_factory() as active:
        stored = await active.directory_settings.get()
    assert stored == before
    assert stored is not None
    assert auth.cipher.unseal(stored.sealed_bind_password) == BIND_PASSWORD
    assert NEW_PASSWORD not in repr(result)


async def test_a_host_that_differs_only_in_case_keeps_the_stored_bind_password(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """호스트를 대문자로만 바꾼 값은 같은 엔드포인트라 바인드 비밀번호 생략이 통과한다.

    테스트 코드: IN-010
    """
    # given: dc1.corp.test가 저장된 예시 AD 설정
    await seed_directory(uow_factory)
    same_host_upper = make_directory_connection(host="DC1.CORP.TEST")

    # when: 대문자 호스트에 바인드 비밀번호를 생략하고 연결 테스트한다
    result = await _test(admin, draft=_draft(same_host_upper, bind_password=None))

    # then: 통과하고 저장된 비밀번호로 AD를 불렀다
    assert result.success is True
    assert directory.discover_calls[0].bind_password.reveal() == BIND_PASSWORD
    assert directory.discover_calls[0].connection.host == "dc1.corp.test"
