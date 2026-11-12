"""AD 설정 저장 UpdateDirectorySettings (AC4~AC6·AC10·AC12).

저장 전에 서비스 계정으로 Base DN을 찾고, 요청 admin이 새 설정으로 검색·바인드되는지 확인한다.
바인드 비밀번호는 암호화해 저장하며, 비우면 저장된 값을 쓴다(서버·계정이 같을 때만).
expected_revision=None은 설정이 아직 없을 때 새로 만든다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.directory.errors import DirectoryVerificationError
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
from app.domain.common.errors import InvalidStateError, InvalidValueError, NotFoundError
from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import DirectorySettingsDraft
from tests.factories_auth import BASE_DN, BIND_PASSWORD, WRONG_PASSWORD, make_principal
from tests.factories_directory import make_directory_connection
from tests.fakes.admin_stack import ADMIN_ACTOR, ADMIN_PASSWORD
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.support.admin_seed import session_is_active
from tests.support.auth_seed import account_key, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.directory.settings import StoredDirectorySettings
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


async def _update(
    admin: AdminStack,
    *,
    expected_revision: int | None = 1,
    password: str | None = ADMIN_PASSWORD,
    draft: DirectorySettingsDraft | None = None,
    actor: object = ADMIN_ACTOR,
) -> StoredDirectorySettings:
    return await admin.update_settings.execute(
        actor=actor,  # type: ignore[arg-type]
        draft=draft or _draft(),
        expected_revision=expected_revision,
        password=None if password is None else Password(password),
        client_ip=IP,
    )


async def _stored(uow_factory: UnitOfWorkFactory) -> StoredDirectorySettings | None:
    async with uow_factory() as uow:
        return await uow.directory_settings.get()


async def test_update_verifies_the_actor_with_the_discovered_base_dn_then_saves(
    admin: AdminStack,
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
) -> None:
    """저장은 찾은 Base DN으로 admin을 확인한 뒤 새 설정·Base DN·저장자·revision을 기록한다.

    바인드 비밀번호는 암호문으로만 남는다.

    테스트 코드: IN-022, IN-032
    """
    # given: revision 1인 예시 AD 설정과, Base DN dc=found,dc=test를 찾아 주는 Fake AD
    await seed_directory(uow_factory)
    directory.base_dn = "dc=found,dc=test"

    stored = await _update(admin)

    # when: 새 호스트·새 바인드 비밀번호·admin 비밀번호로 revision 1을 저장한다
    (call,) = directory.authenticate_calls
    # then: admin 인증은 찾은 Base DN과 admin 아이디로 했고,
    #   저장된 값은 새 호스트·Base DN·revision 2·저장자이며
    #   암호문을 풀면 새 비밀번호이고 평문은 토큰에 없다
    assert (call.base_dn, call.login_id.value, call.password) == (
        "dc=found,dc=test",
        "root",
        ADMIN_PASSWORD,
    )
    assert call.settings.connection == NEW_CONNECTION
    assert (stored.connection, stored.base_dn, stored.revision, stored.updated_by) == (
        NEW_CONNECTION,
        "dc=found,dc=test",
        2,
        ADMIN_ACTOR.user_id,
    )
    assert auth.cipher.unseal(stored.sealed_bind_password) == NEW_PASSWORD
    assert NEW_PASSWORD not in stored.sealed_bind_password.token
    assert await _stored(uow_factory) == stored


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
async def test_update_verification_failure_saves_nothing_and_reports_the_stage(  # noqa: PLR0913, PLR0917
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
    raise_in: str,
    error: Exception,
    stage: VerificationStage,
) -> None:
    """확인이 단계별로 실패하면 저장은 그 단계의 오류이고 기존 설정은 그대로다.

    테스트 코드: IN-028
    """
    # given: 예시 AD 설정과 한 단계에서 실패하는 Fake AD
    before = await seed_directory(uow_factory)
    if raise_in == "discover":
        directory.discover_fails_with = error  # type: ignore[assignment]
    else:
        directory.authenticate_fails_with = error  # type: ignore[assignment]

    # when·then: 저장한다 → DirectoryVerificationError의 stage가 그 단계이고 저장된 설정은 그대로다
    with pytest.raises(DirectoryVerificationError) as caught:
        await _update(admin)

    assert caught.value.stage == stage
    assert caught.value.message
    assert await _stored(uow_factory) == before


async def test_update_with_a_wrong_password_keeps_the_old_settings(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """틀린 admin 비밀번호로 저장하면 bind 단계 오류이고 기존 설정이 그대로다.

    테스트 코드: IN-029
    """
    # given: 예시 AD 설정이 저장되어 있다
    before = await seed_directory(uow_factory)

    # when·then: 틀린 admin 비밀번호로 저장한다
    #   → bind 단계 오류이고 문구에 입력한 비밀번호가 없으며 설정은 그대로다
    with pytest.raises(DirectoryVerificationError) as caught:
        await _update(admin, password=WRONG_PASSWORD)

    assert caught.value.stage == VerificationStage.BIND
    assert WRONG_PASSWORD not in str(caught.value)
    assert await _stored(uow_factory) == before


async def test_update_bind_failure_adds_one_failure_to_the_admins_counter(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """확인의 bind 실패는 admin 시도 제한 실패 횟수를 1 늘린다.

    테스트 코드: IN-029
    """
    # given: 예시 AD 설정이 저장되어 있다
    await seed_directory(uow_factory)

    with pytest.raises(DirectoryVerificationError):
        await _update(admin, password=WRONG_PASSWORD)

    # when: 틀린 admin 비밀번호로 저장한다
    async with uow_factory() as uow:
        counter = await uow.login_failures.get_for_update(account_key("root"))
    # then: admin 계정의 실패 횟수가 1이다
    assert counter is not None
    assert counter.failures == 1


async def test_update_is_refused_while_the_admin_is_locked_out(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """실패 한도를 채운 admin의 저장은 TooManyAttemptsError이고 admin 바인드를 하지 않는다.

    테스트 코드: IN-030
    """
    # given: 틀린 비밀번호 저장으로 계정 실패 한도를 채웠다
    before = await seed_directory(uow_factory)
    for _ in range(MAX_PER_ACCOUNT):
        with pytest.raises(DirectoryVerificationError):
            await _update(admin, password=WRONG_PASSWORD)
    calls = len(directory.authenticate_calls)

    # when·then: 올바른 비밀번호로 저장한다
    #   → TooManyAttemptsError이고 AD 인증 호출 수는 늘지 않으며 설정은 그대로다
    with pytest.raises(TooManyAttemptsError):
        await _update(admin)

    assert len(directory.authenticate_calls) == calls
    assert await _stored(uow_factory) == before


async def test_update_with_a_stale_revision_conflicts_without_calling_the_directory(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """이미 바뀐 revision으로 저장하면 AD를 부르지 않고 InvalidStateError다.

    테스트 코드: IN-024
    """
    # given: revision 1인 AD 설정
    before = await seed_directory(uow_factory)

    # when·then: revision 2로 저장한다
    #   → InvalidStateError이고 AD 탐색·인증 호출이 0회이며 설정은 그대로다
    with pytest.raises(InvalidStateError):
        await _update(admin, expected_revision=before.revision + 1)

    assert directory.authenticate_calls == []
    assert directory.discover_calls == []
    assert await _stored(uow_factory) == before


async def test_update_requires_a_password_from_a_directory_admin(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """현재 admin 비밀번호 없이 저장하면 InvalidValueError이고 인증을 하지 않는다.

    테스트 코드: IN-014
    """
    # given: 예시 AD 설정이 저장되어 있다
    before = await seed_directory(uow_factory)

    # when·then: admin 비밀번호 없이 저장한다
    #   → InvalidValueError이고 AD 인증 호출이 0회이며 설정은 그대로다
    with pytest.raises(InvalidValueError):
        await _update(admin, password=None)

    assert directory.authenticate_calls == []
    assert await _stored(uow_factory) == before


@pytest.mark.parametrize(
    "subject", ["dev-admin", "dev-sales", "dev-user", "dev-admin2", "xdev-admin", "root"]
)
async def test_a_missing_password_is_rejected_before_any_discovery(
    admin: AdminStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
    subject: str,
) -> None:
    """현재 admin 비밀번호가 없으면 Base DN 탐색 전에 고정 문구로 거절된다(예약 아이디도 같다).

    테스트 코드: IN-014
    """
    # given: 예시 AD 설정과 여러 admin 아이디(예전 개발용 아이디 포함)
    before = await seed_directory(uow_factory)
    actor = make_principal(subject, Role.ADMIN)

    # when·then: admin 비밀번호 없이 저장한다
    #   → 고정 문구의 InvalidValueError이고 AD 호출이 0회이며 설정은 그대로다
    with pytest.raises(InvalidValueError) as caught:  # 예약 아이디도 예외가 아니다
        await _update(admin, actor=actor, password=None)

    assert str(caught.value) == PASSWORD_REQUIRED
    assert directory.discover_calls == []
    assert directory.authenticate_calls == []
    assert await _stored(uow_factory) == before


async def test_update_keeps_existing_sessions_alive(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """AD 설정을 저장해도 이미 열린 세션은 유지된다.

    테스트 코드: IN-035
    """
    # given: AD 설정과 KIM의 로그인 세션
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)
    outcome = await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    issued = outcome.session

    # when: admin이 AD 설정을 저장한다
    await _update(admin)

    # then: KIM의 세션이 계속 유효하다
    assert (await auth.authenticate.execute(issued.token)).subject == "kim"
    assert await session_is_active(uow_factory, issued.token)


async def test_update_without_bind_password_reuses_stored_password(
    admin: AdminStack,
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
) -> None:
    """엔드포인트·계정이 같으면 바인드 비밀번호를 생략해도 저장된 비밀번호가 유지된다.

    사용자 필터·연결 제한 시간만 바꾸는 경우다.

    테스트 코드: IN-008, IN-011
    """
    # given: 바인드 비밀번호 svc-pass가 저장된 예시 AD 설정
    before = await seed_directory(uow_factory)
    same_endpoint = make_directory_connection(
        user_filter="(uid={login_id})", connect_timeout_seconds=9
    )

    # when: 사용자 필터·연결 제한 시간만 바꾸고 바인드 비밀번호를 생략해 저장한다
    stored = await _update(admin, draft=_draft(same_endpoint, bind_password=None))

    # then: AD 탐색에 저장된 비밀번호가 쓰이고, 새 값이 저장되며
    #   암호문을 풀면 svc-pass이고 revision이 1 오른다
    assert directory.discover_calls[0].bind_password.reveal() == BIND_PASSWORD
    assert auth.cipher.unseal(stored.sealed_bind_password) == BIND_PASSWORD
    assert stored.connection == same_endpoint
    assert stored.revision == before.revision + 1


async def test_update_without_bind_password_after_host_change_is_rejected_before_contacting_ad(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """호스트를 바꾸고 바인드 비밀번호를 생략하면 AD를 부르기 전에 InvalidValueError다.

    테스트 코드: IN-010
    """
    # given: 예시 AD 설정이 저장되어 있다
    before = await seed_directory(uow_factory)

    # when·then: 호스트를 바꾸고 바인드 비밀번호 없이 저장한다
    #   → bind_password 문구의 InvalidValueError이고 AD 호출이 0회이며 설정은 그대로다
    with pytest.raises(InvalidValueError) as caught:
        await _update(admin, draft=_draft(NEW_CONNECTION, bind_password=None))

    assert "bind_password" in str(caught.value)
    assert directory.discover_calls == []
    assert directory.authenticate_calls == []
    assert await _stored(uow_factory) == before


async def test_update_with_a_new_password_replaces_the_stored_one(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """새 바인드 비밀번호로 저장하면 암호문이 새 값으로 바뀐다.

    테스트 코드: IN-033
    """
    # given: 예시 AD 설정(예전 암호문)이 저장되어 있다
    await seed_directory(uow_factory)

    # when: 새 바인드 비밀번호로 저장한다
    stored = await _update(admin, draft=_draft(make_directory_connection(), NEW_PASSWORD))

    # then: 저장된 암호문을 풀면 새 비밀번호다
    assert auth.cipher.unseal(stored.sealed_bind_password) == NEW_PASSWORD


async def test_update_with_unreadable_stored_password_needs_a_new_one(
    admin: AdminStack,
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
) -> None:
    """저장된 비밀번호를 풀 수 없으면 생략은 거절되고 새 비밀번호로는 저장된다.

    테스트 코드: IN-013
    """
    # given: 풀 수 없는 암호문이 저장되어 있다
    before = await seed_directory(uow_factory, unreadable=True)

    with pytest.raises(InvalidValueError) as caught:
        await _update(admin, draft=_draft(make_directory_connection(), bind_password=None))
    # when: 바인드 비밀번호 없이 저장하고 이어서 새 비밀번호로 저장한다
    stored = await _update(admin, draft=_draft(make_directory_connection(), NEW_PASSWORD))

    # then: 첫 요청은 bind_password 문구의 InvalidValueError(AD 호출 없음),
    #   둘째는 revision 2로 새 비밀번호가 저장된다
    assert "bind_password" in str(caught.value)
    assert before.revision == 1
    assert (stored.revision, auth.cipher.unseal(stored.sealed_bind_password)) == (2, NEW_PASSWORD)
    assert len(directory.discover_calls) == 1  # 거부된 요청은 AD에 묻지 않았다


async def test_update_with_null_revision_creates_settings_when_missing(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """설정이 없을 때 null revision으로 저장하면 revision 1로 만들어진다.

    테스트 코드: IN-027
    """
    # when: null revision으로 모든 칸을 채워 저장한다 (전제: AD 설정이 없다)
    stored = await _update(admin, expected_revision=None)

    # then: revision 1, 저장자 admin, 찾은 Base DN이 저장된다
    assert (stored.revision, stored.updated_by, stored.base_dn) == (1, ADMIN_ACTOR.user_id, BASE_DN)
    assert auth.cipher.unseal(stored.sealed_bind_password) == NEW_PASSWORD
    assert await _stored(uow_factory) == stored


async def test_update_with_null_revision_conflicts_when_settings_exist(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """설정이 있는데 null revision으로 저장하면 충돌이다.

    테스트 코드: IN-025
    """
    # given: 이미 저장된 AD 설정이 있다
    before = await seed_directory(uow_factory)

    # when: expected_revision을 null로 저장한다
    with pytest.raises(DirectorySettingsConflictError):
        await _update(admin, expected_revision=None)

    # then: 충돌이고 AD 탐색 호출이 없으며 저장된 설정은 그대로다
    assert directory.discover_calls == []
    assert await _stored(uow_factory) == before


async def test_update_with_an_integer_revision_is_not_found_when_settings_are_missing(
    admin: AdminStack,
) -> None:
    """설정이 없는데 정수 revision으로 저장하면 NotFoundError다.

    테스트 코드: IN-026
    """
    # when: 정수 revision(1)으로 저장한다 (전제: 저장된 AD 설정이 없다)
    with pytest.raises(NotFoundError):
        await _update(admin, expected_revision=1)

    # then: NotFoundError가 발생한다(위 with 블록이 단언)


async def test_update_with_null_revision_without_bind_password_is_rejected(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """설정이 없을 때 바인드 비밀번호를 생략하면 거절되고 행이 생기지 않는다.

    테스트 코드: IN-012
    """
    # when: 바인드 비밀번호를 생략하고 null revision으로 저장한다 (전제: 저장된 AD 설정이 없다)
    with pytest.raises(InvalidValueError) as caught:
        await _update(admin, expected_revision=None, draft=_draft(bind_password=None))

    # then: bind_password 문구로 거절되고 AD 탐색 호출이 없으며 행이 생기지 않는다
    assert "bind_password" in str(caught.value)
    assert directory.discover_calls == []
    assert await _stored(uow_factory) is None


async def test_each_save_raises_the_revision_by_one(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """저장할 때마다 revision이 1씩 오른다.

    테스트 코드: IN-023
    """
    # given: revision 1인 예시 AD 설정
    await seed_directory(uow_factory)

    # when: 받은 revision으로 두 번 연속 저장한다
    first = await _update(admin, expected_revision=1)
    second = await _update(admin, expected_revision=first.revision)

    # then: revision은 2, 3이다
    assert (first.revision, second.revision) == (2, 3)


async def test_failed_creation_leaves_no_row_behind(
    admin: AdminStack, directory: FakeDirectoryAuthenticator, uow_factory: UnitOfWorkFactory
) -> None:
    """설정이 없을 때 확인이 실패하면 422 단계 오류이고 행이 생기지 않는다.

    테스트 코드: IN-028
    """
    # given: AD 설정이 없고 Fake AD가 서비스 계정 바인드 단계에서 실패한다
    directory.discover_fails_with = DirectoryMisconfiguredError(
        stage=VerificationStage.SERVICE_BIND
    )

    # when: null revision으로 처음 등록한다
    with pytest.raises(DirectoryVerificationError) as caught:
        await _update(admin, expected_revision=None)

    # then: service_bind 단계 오류이고 저장된 행이 없다
    assert caught.value.stage == VerificationStage.SERVICE_BIND
    assert await _stored(uow_factory) is None


async def test_the_next_login_uses_the_saved_base_dn_and_bind_password(
    admin: AdminStack,
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow_factory: UnitOfWorkFactory,
) -> None:
    """저장 결과는 조회와 같고 다음 AD 로그인은 저장된 Base DN·비밀번호로 Base DN 탐색 없이 한다.

    테스트 코드: IN-036
    """
    # given: 예시 AD 설정과 KIM 계정, Fake AD가 찾아 줄 Base DN
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)
    directory.base_dn = "dc=saved,dc=test"
    stored = await _update(admin)
    discovered_before_login = len(directory.discover_calls)

    # when: KIM이 AD로 로그인한다
    await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: 조회 결과는 저장 결과와 같고, 로그인은 저장된 Base DN·새 비밀번호를 썼으며 탐색은 없었다
    assert (await admin.get_settings.execute()).stored == stored
    assert (await auth.status.execute()).directory_configured is True
    login_call = directory.authenticate_calls[-1]
    assert login_call.base_dn == "dc=saved,dc=test"
    assert login_call.settings.bind_password.reveal() == NEW_PASSWORD
    assert len(directory.discover_calls) == discovered_before_login
