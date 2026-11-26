"""DirectoryLogin 유스케이스: 서비스 계정 search-then-bind 로그인과 비밀번호 해시 저장(AC7·AC13).

AD가 답하지 못할 때의 대체 로그인은 test_directory_login_fallback.py다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import DIRECTORY_NOT_CONFIGURED, LOGIN_FAILED
from app.application.ports.directory import InvalidCredentialsError, VerificationStage
from app.application.ports.directory_settings_repository import DirectorySettingsWrite
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories import NOW
from tests.factories_auth import BASE_DN, BIND_PASSWORD
from tests.factories_directory import make_directory_connection
from tests.fakes.auth_stack import SESSION_TTL
from tests.support.auth_seed import (
    DUMMY_PASSWORD,
    account_key,
    seed_directory,
    seed_user,
    set_user_phone,
)

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

IP = "10.0.0.1"


@pytest.fixture
async def ready(uow_factory: UnitOfWorkFactory) -> None:
    """AD 설정이 있고 kim(sales)이 등록된 상태."""
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)


async def _login(
    auth: AuthStack,
    login_id: str = "kim",
    password: str = "pw-kim",  # noqa: S107
) -> IssuedSession:
    outcome = await auth.login.execute(login_id=login_id, password=Password(password), client_ip=IP)
    return outcome.session


@pytest.mark.usefixtures("ready")
async def test_login_issues_session_for_registered_user(auth: AuthStack, clock: FixedClock) -> None:
    """등록된 사용자가 AD 비밀번호로 로그인하면 세션이 발급된다.

    테스트 코드: AU-001
    """
    # when: kim이 AD 비밀번호로 로그인한다
    #   (전제: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다)
    issued = (
        await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    ).session

    # then: sales 주체와 만료 시각이 있는 세션이 발급되고 토큰으로 인증된다
    assert issued.principal.subject == "kim"
    assert issued.principal.role is Role.SALES
    assert issued.expires_at == NOW + SESSION_TTL
    assert (await auth.authenticate.execute(issued.token)).subject == "kim"


@pytest.mark.usefixtures("ready")
async def test_login_principal_carries_the_users_row_id(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """로그인한 주체의 id는 users 행의 id다.

    테스트 코드: AU-008
    """
    # when: kim이 로그인한다 (전제: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다)
    issued = await _login(auth)

    # then: 주체 id가 users 행 id와 같다
    stored = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert stored is not None
    assert issued.principal.user_id == stored.id


@pytest.mark.usefixtures("ready")
async def test_login_after_reregistration_uses_the_new_row_not_the_resigned_one(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """퇴사 행과 재직 행이 함께 있으면 재직 행으로 로그인된다.

    테스트 코드: AU-009, AU-008
    """
    old = await seed_user(uow_factory, "lee", Role.USER, resigned=True)
    new = await seed_user(uow_factory, "lee", Role.SALES)
    auth.directory.add_account("lee", "pw-lee")

    # when: lee가 로그인한다
    issued = (
        await auth.login.execute(login_id="lee", password=Password("pw-lee"), client_ip=IP)
    ).session

    # then: 새 재직 행(sales)으로 로그인되고 퇴사 행은 그대로다
    assert issued.principal.user_id == new.id
    assert issued.principal.user_id != old.id
    assert issued.principal.role is Role.SALES
    assert (await uow.users.get(old.id)).last_login_at is None  # 퇴사 행은 건드리지 않는다


@pytest.mark.usefixtures("ready")
async def test_login_role_comes_from_the_users_table(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """로그인한 사용자의 역할은 users 행의 값이다.

    테스트 코드: AU-008
    """
    # given: users 행의 역할이 user인 lee가 AD에도 있다
    await seed_user(uow_factory, "lee", Role.USER)
    auth.directory.add_account("lee", "pw-lee")

    # when: lee가 로그인한다
    issued = (
        await auth.login.execute(login_id="lee", password=Password("pw-lee"), client_ip=IP)
    ).session

    # then: 역할이 users 행 값(user)이다
    assert issued.principal.role is Role.USER


@pytest.mark.usefixtures("ready")
async def test_login_succeeds_when_the_directory_display_name_is_256_chars(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    """AD 이름이 256자여도 로그인되고 세션이 인증된다.

    테스트 코드: AU-006
    """
    # given: AD 표시 이름이 256자인 kim 계정
    directory.add_account("kim", "pw-kim", display_name="가" * 256, email="kim@corp.test")

    # when: kim이 로그인한다
    issued = await _login(auth)

    # then: 로그인과 세션 인증이 성공한다
    assert issued.principal.subject == "kim"
    assert (await auth.authenticate.execute(issued.token)).subject == "kim"


@pytest.mark.usefixtures("ready")
async def test_login_updates_last_login_and_profile(auth: AuthStack, uow: FakeUnitOfWork) -> None:
    """AD 로그인에 성공하면 최근 로그인 시각과 AD의 이름·이메일이 남는다.

    테스트 코드: AU-005
    """
    # when: kim이 로그인한다 (전제: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다)
    await _login(auth)

    # then: 로그인 시각과 AD 이름·이메일이 users 행에 저장된다
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.last_login_at == NOW
    assert user.display_name == "김영업"
    assert user.email == "kim@corp.test"


@pytest.mark.usefixtures("ready")
async def test_login_overwrites_profile_with_the_latest_directory_values(
    auth: AuthStack, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    """다시 로그인하면 최신 AD 이름·이메일로 덮어쓴다.

    테스트 코드: AU-005
    """
    # given: kim이 한 번 로그인했고 한 시간 뒤 AD의 이름·이메일이 바뀌었다
    await _login(auth)
    clock.advance(3600)
    auth.directory.add_account("kim", "pw-kim", display_name="김부장", email="kim2@corp.test")

    # when: 다시 로그인한다
    await _login(auth)

    # then: 새 AD 값과 새 로그인 시각이 저장된다
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert (user.display_name, user.email) == ("김부장", "kim2@corp.test")
    assert user.last_login_at == clock.now()


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize(
    "case",
    [
        "wrong-password",
        "unknown-in-directory",
        "not-registered",
        "deleted",
        "resigned",
        "malformed-id",
    ],
)
async def test_login_failures_share_one_message_and_issue_no_session(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, case: str
) -> None:
    """AD 거절·미등록·삭제·퇴사·형식 오류는 같은 문구의 실패이고 세션이 없다.

    테스트 코드: AU-010, AU-011, AU-016
    """
    # given: AD에는 있지만 앱에 없거나 삭제·퇴사된 계정과 AD 비밀번호 불일치 사례
    auth.directory.add_account("newbie", "pw-newbie")  # AD에는 있지만 앱에 등록되지 않음
    auth.directory.add_account("gone", "pw-gone")
    auth.directory.add_account("quit", "pw-quit")  # AD에는 있지만 앱에서 퇴사 처리됨
    await seed_user(uow_factory, "gone", Role.SALES, deleted=True)
    await seed_user(uow_factory, "quit", Role.SALES, resigned=True)
    attempts = {
        "wrong-password": ("kim", "not-the-password"),
        "unknown-in-directory": ("ghost", "pw-ghost"),
        "not-registered": ("newbie", "pw-newbie"),
        "deleted": ("gone", "pw-gone"),
        "resigned": ("quit", "pw-quit"),
        "malformed-id": ("kim)(uid=*", "pw-kim"),
    }
    login_id, password = attempts[case]

    # when: 사례별 아이디·비밀번호로 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await _login(auth, login_id, password)

    # then: 공통 실패 문구의 AuthenticationError이고 세션이 만들어지지 않는다
    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert uow.sessions._items == {}


@pytest.mark.usefixtures("ready")
async def test_login_failure_exception_never_contains_the_password(auth: AuthStack) -> None:
    """실패 예외의 문구·원인 체인에 비밀번호 원문이 없다.

    테스트 코드: AU-065
    """
    # when: 틀린 비밀번호로 로그인한다
    #   (전제: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다)
    with pytest.raises(AuthenticationError) as caught:
        await _login(auth, "kim", DUMMY_PASSWORD)

    # then: 예외와 원인 체인 어디에도 비밀번호가 없다
    chain = [caught.value, caught.value.__cause__, caught.value.__context__]
    for error in filter(None, chain):
        assert DUMMY_PASSWORD not in f"{error!s}{error!r}{error.args!r}"


@pytest.mark.usefixtures("ready")
async def test_login_id_is_normalized_before_lookup(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    """앞뒤 공백·대문자가 섞인 아이디도 같은 사용자로 로그인된다.

    테스트 코드: AU-004
    """
    # when: '  Kim '으로 로그인한다
    #   (전제: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다)
    issued = (
        await auth.login.execute(login_id="  Kim ", password=Password("pw-kim"), client_ip=IP)
    ).session

    # then: kim으로 로그인되고 AD에는 정규화한 아이디가 전달된다
    assert issued.principal.subject == "kim"
    assert [call.login_id for call in directory.authenticate_calls] == [LoginId("kim")]


async def test_login_without_directory_settings_and_without_a_hash_is_rejected_and_counted(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork
) -> None:
    """AD 설정도 해시도 없으면 409이고 AD를 부르지 않으며 실패 1회로 센다.

    테스트 코드: AU-031
    """
    # when: 해시 없는 사용자가 로그인한다 (전제: AD 설정이 저장되어 있지 않다)
    with pytest.raises(InvalidStateError) as caught:
        await _login(auth)

    # then: AD 미등록 문구의 오류이고 AD 호출이 없으며 실패 횟수가 1이다
    assert str(caught.value) == DIRECTORY_NOT_CONFIGURED
    assert directory.authenticate_calls == []
    assert directory.discover_calls == []
    assert uow.login_failures._items[account_key("kim")].failures == 1


@pytest.mark.usefixtures("ready")
async def test_login_passes_stored_base_dn_and_unsealed_password(
    auth: AuthStack, directory: FakeDirectoryAuthenticator
) -> None:
    """AD 로그인은 저장된 Base DN과 복호화한 바인드 비밀번호를 쓴다.

    테스트 코드: AU-015
    """
    # when: kim이 로그인한다 (전제: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다)
    await _login(auth)

    # then: 저장된 Base DN과 풀어 쓴 바인드 비밀번호로 한 번 호출하고 Base DN은 다시 찾지 않는다
    (call,) = directory.authenticate_calls
    assert call.base_dn == BASE_DN  # 로그인마다 다시 찾지 않고 저장된 값을 쓴다
    assert directory.discover_calls == []
    assert call.settings.connection == make_directory_connection()
    assert call.settings.credentials is None
    assert call.login_id == LoginId("kim")
    assert call.password == "pw-kim"  # noqa: S105 - 가짜 값


@pytest.mark.usefixtures("ready")
# 테스트 코드: IN-036
async def test_login_uses_the_current_settings_each_time(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, directory: FakeDirectoryAuthenticator
) -> None:
    """AD 설정이 바뀌면 다음 로그인부터 새 설정을 쓴다.

    테스트 코드: AU-015
    """
    # given: kim이 한 번 로그인한 뒤 DB의 AD 설정(호스트·Base DN·바인드 비밀번호)이 바뀌었다
    await _login(auth)
    async with uow_factory() as uow:
        await uow.directory_settings.save(
            DirectorySettingsWrite(
                connection=make_directory_connection(host="dc2.corp.test"),
                base_dn="dc=other,dc=test",
                expected_revision=1,
                updated_by=None,
                now=NOW,
            )
        )
        await uow.commit()

    # when: 다시 로그인한다
    await _login(auth)

    # then: 두 번째 로그인은 새 설정을 쓴다
    first, second = directory.authenticate_calls
    assert first.base_dn == BASE_DN
    assert (second.base_dn, second.settings.connection.host) == (
        "dc=other,dc=test",
        "dc2.corp.test",
    )
    assert second.settings.credentials is None


@pytest.mark.usefixtures("ready")
async def test_login_passes_the_password_only_to_the_directory(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork
) -> None:
    """비밀번호 원문은 AD에만 전달되고 저장 행·세션 결과에 남지 않는다.

    테스트 코드: AU-065
    """
    # given: AD 계정의 비밀번호가 더미 값이다
    directory.add_account("kim", DUMMY_PASSWORD)

    # when: kim이 로그인한다
    issued = await _login(auth, "kim", DUMMY_PASSWORD)

    # then: 저장된 행과 발급 결과 어디에도 비밀번호 원문이 없다
    assert directory.authenticate_calls[0].password == DUMMY_PASSWORD
    stored = repr(uow.users._items) + repr(uow.sessions._items) + repr(uow.login_failures._items)
    assert DUMMY_PASSWORD not in stored
    assert DUMMY_PASSWORD not in repr(issued)


@pytest.mark.usefixtures("ready")
async def test_login_of_a_user_deleted_during_the_login_is_a_plain_login_failure(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """처리 도중 사용자가 삭제되어도 404가 아닌 로그인 실패(401 문구)가 된다."""
    # given: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다
    original_get = uow.users.get_active_by_login_id

    async def get_then_delete(login_id: LoginId) -> User | None:
        found = await original_get(login_id)
        assert found is not None
        await uow.users.delete(found.id)  # 다른 요청이 사용자를 삭제하고 커밋했다
        return found

    uow.users.get_active_by_login_id = get_then_delete  # type: ignore[method-assign]

    # when: 읽은 직후 다른 요청이 사용자를 삭제한 상태에서 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await _login(auth)

    # then: 공통 실패이고 세션이 만들어지지 않는다
    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert uow.sessions._items == {}


@pytest.mark.usefixtures("ready")
async def test_successful_directory_login_saves_new_password_hash(
    auth: AuthStack, uow: FakeUnitOfWork, clock: FixedClock
) -> None:
    """AD 로그인에 성공할 때마다 새 솔트의 해시로 덮어쓴다.

    테스트 코드: AU-007
    """
    # when: kim이 로그인한다(처음)
    #   (전제: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다)
    await _login(auth)

    # then: 비밀번호 해시가 저장되고 원문은 없으며, 다시 로그인하면 다른 해시로 덮어쓴다
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    first = await uow.password_hashes.get(user.id)
    assert first is not None
    assert await auth.hasher.verify(Password("pw-kim"), first)
    assert "pw-kim" not in repr(first)
    assert "pw-kim" not in first.encoded
    assert uow.password_hashes.saved_at(user.id) == NOW

    clock.advance(60)
    await _login(auth)

    second = await uow.password_hashes.get(user.id)
    assert second is not None
    assert second != first  # 새 솔트로 덮어쓴다
    assert uow.password_hashes.saved_at(user.id) == clock.now()
    assert len(uow.password_hashes._items) == 1


@pytest.mark.usefixtures("ready")
async def test_hash_follows_the_latest_directory_password(
    auth: AuthStack, directory: FakeDirectoryAuthenticator, uow: FakeUnitOfWork
) -> None:
    """저장 해시는 가장 최근에 성공한 AD 비밀번호를 따른다.

    테스트 코드: AU-007
    """
    # given: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다
    await _login(auth)
    directory.add_account("kim", "pw-kim-changed", display_name="김영업", email="kim@corp.test")

    # when: AD 비밀번호가 바뀐 뒤 새 비밀번호로 로그인한다
    await _login(auth, "kim", "pw-kim-changed")

    # then: 해시는 새 비밀번호만 검증한다
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    stored = await uow.password_hashes.get(user.id)
    assert stored is not None
    assert await auth.hasher.verify(Password("pw-kim-changed"), stored)
    assert not await auth.hasher.verify(Password("pw-kim"), stored)


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize("stage", [VerificationStage.BIND, VerificationStage.SEARCH])
async def test_rejected_password_gets_401_even_when_hash_matches(
    auth: AuthStack,
    directory: FakeDirectoryAuthenticator,
    uow: FakeUnitOfWork,
    stage: VerificationStage,
) -> None:
    """AD가 비밀번호를 거절하면(바인드 거부·검색 0건) 저장 해시가 맞아도 401이고 실패 1회다.

    테스트 코드: AU-013, AU-014
    """
    # given: 해시가 저장된 kim, AD는 비밀번호 바인드 거부 또는 검색 0건으로 응답한다
    await _login(auth)  # 해시가 생긴다
    directory.authenticate_fails_with = InvalidCredentialsError(stage=stage)
    saved = dict(uow.password_hashes._items)
    verify_calls = len(auth.hasher.verify_calls)

    # when: 같은 비밀번호로 다시 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await _login(auth)  # 같은 비밀번호(해시와 일치)

    # then: 401이고 해시는 그대로이며 대체 로그인을 시도하지 않고 실패가 1회 센다
    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert uow.password_hashes._items == saved  # AD가 거부해도 해시는 지우지 않는다
    assert len(auth.hasher.verify_calls) == verify_calls  # 대체 로그인을 시도하지 않았다
    assert uow.login_failures._items[account_key("kim")].failures == 1


@pytest.mark.usefixtures("ready")
async def test_failed_directory_login_saves_no_hash(auth: AuthStack, uow: FakeUnitOfWork) -> None:
    """실패한 AD 로그인은 해시를 만들지 않는다.

    테스트 코드: AU-013
    """
    # when: 틀린 비밀번호로 로그인한다
    #   (전제: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다)
    with pytest.raises(AuthenticationError):
        await _login(auth, "kim", "not-the-password")

    # then: 저장된 해시가 없고 해시 계산도 하지 않았다
    assert uow.password_hashes._items == {}
    assert auth.hasher.hash_calls == 0


async def test_login_of_an_unregistered_user_saves_no_hash(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AD에는 있지만 등록되지 않은 아이디는 401이고 해시를 만들지 않는다.

    테스트 코드: AU-010
    """
    await seed_directory(uow_factory)
    # given: AD에만 있고 앱에 없는 newbie
    auth.directory.add_account("newbie", "pw-newbie")

    # when: newbie가 로그인한다
    with pytest.raises(AuthenticationError):
        await _login(auth, "newbie", "pw-newbie")

    # then: 해시는 저장되지 않고 앱에 활성 사용자가 없다는 이유가 남는다
    assert uow.password_hashes._items == {}
    assert "stage=app_user reason=no_active_app_user" in caplog.text
    assert "newbie" not in caplog.text


@pytest.mark.usefixtures("ready")
async def test_a_directory_login_carries_no_directory_warning(auth: AuthStack) -> None:
    """AD 로그인 결과에는 AD 경고가 없다.

    테스트 코드: AU-001
    """
    # when: kim이 로그인한다 (전제: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다)
    outcome = await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: 경고가 없다
    assert outcome.directory_warning is None


@pytest.mark.usefixtures("ready")
async def test_login_password_never_reaches_stored_rows_in_plain_text(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """저장된 해시·AD 설정 행에 비밀번호 원문이 없다.

    테스트 코드: AU-065
    """
    # when: kim이 로그인한다 (전제: AD 설정이 있고 kim(sales)이 등록되어 있으며 AD가 정상 응답한다)
    await _login(auth, "kim", "pw-kim")

    # then: 해시 행과 AD 설정 행에 사용자·바인드 비밀번호 원문이 없다
    stored = repr(uow.password_hashes._items) + repr(uow.directory_settings._items)
    assert "pw-kim" not in stored
    assert BIND_PASSWORD not in stored


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize(
    ("directory_phone", "stored"),
    [(" 010-1234-5678 ", "010-1234-5678"), ("010.1234.5678 내선 12", "010.1234.5678 내선 12")],
    ids=["mobile-with-spaces", "format-outside-app-rule"],
)
async def test_login_overwrites_the_phone_with_the_directory_mobile(
    auth: AuthStack,
    uow: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    directory_phone: str,
    stored: str,
) -> None:
    """AD 로그인에 성공하면 앱에서 입력한 전화번호를 AD의 mobile 값으로 형식과 무관하게 덮어쓴다.

    테스트 코드: AU-089
    """
    # given: kim 행의 전화가 앱에서 입력한 값이고, AD는 mobile 값(공백 또는 앱 형식 밖)을 준다
    await set_user_phone(uow_factory, "kim", "02-111-2222")
    auth.directory.add_account(
        "kim", "pw-kim", display_name="김부장", email="kim2@corp.test", phone=directory_phone
    )

    # when: kim이 맞는 비밀번호로 로그인한다
    await _login(auth)

    # then: 전화는 정리한 AD 값이고 이름·이메일도 AD 값이다
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.phone == stored
    assert (user.display_name, user.email) == ("김부장", "kim2@corp.test")


@pytest.mark.usefixtures("ready")
@pytest.mark.parametrize(
    "directory_phone", [None, "", "  "], ids=["no-attribute", "empty", "blank"]
)
async def test_login_keeps_the_stored_phone_when_the_directory_has_none(
    auth: AuthStack,
    uow: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    directory_phone: str | None,
) -> None:
    """AD에 전화번호가 없으면(못 읽은 경우 포함) 저장된 전화번호를 그대로 둔다.

    테스트 코드: AU-091
    """
    # given: kim 행의 전화가 admin이 등록 때 넣은 값이고, AD는 전화 없이 이름·이메일만 준다
    await set_user_phone(uow_factory, "kim", "02-111-2222")
    auth.directory.add_account(
        "kim", "pw-kim", display_name="김영업", email="kim@corp.test", phone=directory_phone
    )

    # when: kim이 로그인한다
    issued = await _login(auth)

    # then: 세션이 발급되고 전화는 그대로이며 이름·이메일은 AD 값이다
    assert issued.principal.subject == "kim"
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.phone == "02-111-2222"
    assert (user.display_name, user.email) == ("김영업", "kim@corp.test")


@pytest.mark.usefixtures("ready")
async def test_login_leaves_a_user_without_a_phone_empty_when_the_directory_has_none(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """전화가 비어 있던 사용자는 AD에 전화번호가 없어도 계속 비어 있다.

    테스트 코드: AU-091
    """
    # given: 전화가 없는 kim과 전화번호를 주지 않는 AD 계정
    auth.directory.add_account("kim", "pw-kim", display_name="김영업", email="kim@corp.test")

    # when: kim이 로그인한다
    await _login(auth)

    # then: 전화는 비어 있다(null)
    user = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert user is not None
    assert user.phone is None
