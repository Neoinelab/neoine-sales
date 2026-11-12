"""DirectoryLogin(R7): 재직 행이 둘 이상이면 경고 로그를 남기고 LOGIN_FAILED로 끝난다.

계약: Repository가 AmbiguousLoginIdError(app.domain.user.errors)를 올리고, DirectoryLogin이
잡아 AuthenticationError(LOGIN_FAILED)로 바꾼다. 경고(WARNING) 로그에는 비밀번호·login_id 원문을
넣지 않는다(건수나 해시만).
"""

import logging
from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from tests.support.auth_seed import DUMMY_PASSWORD, seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"


@pytest.fixture
async def duplicated(uow_factory: UnitOfWorkFactory, auth: AuthStack) -> None:
    """kim이 재직 행 둘로 등록된(정합 위반) 상태. AD에는 kim이 있다."""
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)
    await seed_user(uow_factory, "kim", Role.USER)
    auth.directory.add_account("kim", DUMMY_PASSWORD)


@pytest.mark.usefixtures("duplicated")
async def test_login_with_duplicate_active_rows_fails_with_the_common_message(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """같은 아이디의 재직 행이 둘이면 공통 실패 401이고 세션이 없다.

    테스트 코드: AU-012
    """
    # when: kim이 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.login.execute(login_id="kim", password=Password(DUMMY_PASSWORD), client_ip=IP)

    # then: 공통 실패 문구이고 세션이 없다
    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert uow.sessions._items == {}


@pytest.mark.usefixtures("duplicated")
async def test_login_with_duplicate_active_rows_logs_a_warning_without_secrets(
    auth: AuthStack, caplog: pytest.LogCaptureFixture
) -> None:
    """재직 행 중복은 비밀번호·아이디 원문 없는 경고 로그를 남긴다.

    테스트 코드: AU-012
    """
    caplog.set_level(logging.DEBUG)

    # when: kim이 로그인한다
    with pytest.raises(AuthenticationError):
        await auth.login.execute(login_id="kim", password=Password(DUMMY_PASSWORD), client_ip=IP)

    # then: 경고 로그가 남고 비밀번호와 아이디 원문은 없다
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "정합 위반을 운영자가 알 수 있도록 경고 로그가 남아야 한다"
    assert DUMMY_PASSWORD not in caplog.text
    assert "kim" not in caplog.text  # login_id 원문 금지(건수·해시만)


@pytest.mark.usefixtures("duplicated")
async def test_login_with_duplicate_active_rows_updates_neither_row(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """재직 행 중복이면 어느 행도 바꾸지 않는다.

    테스트 코드: AU-012
    """
    # when: kim이 로그인한다
    with pytest.raises(AuthenticationError):
        await auth.login.execute(login_id="kim", password=Password(DUMMY_PASSWORD), client_ip=IP)

    # then: 두 행 모두 최근 로그인 시각이 비어 있다
    users = await uow.users.list_users(limit=100)
    assert len(users) == 2
    assert all(u.last_login_at is None for u in users)


@pytest.mark.usefixtures("duplicated")
@pytest.mark.usefixtures("duplicated")
async def test_login_with_duplicate_active_rows_saves_no_hash(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """재직 행 중복이면 해시를 저장하지 않는다.

    테스트 코드: AU-012
    """
    # when: kim이 로그인한다
    with pytest.raises(AuthenticationError):
        await auth.login.execute(login_id="kim", password=Password(DUMMY_PASSWORD), client_ip=IP)

    # then: 저장된 해시가 없다
    assert uow.password_hashes._items == {}


@pytest.mark.usefixtures("duplicated")
async def test_duplicate_login_id_does_not_block_other_users(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    """한 아이디의 중복은 다른 사용자의 로그인을 막지 않는다."""
    # given: kim은 재직 행이 둘이고 lee는 정상이다
    await seed_user(uow_factory, "lee", Role.USER)
    auth.directory.add_account("lee", "pw-lee")

    # when: lee가 로그인한다
    outcome = await auth.login.execute(login_id="lee", password=Password("pw-lee"), client_ip=IP)

    # then: lee가 로그인된다
    assert outcome.session.principal.subject == "lee"


async def test_fake_repository_raises_for_duplicates_so_the_use_case_must_translate(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """Fake가 중복을 숨기지 않는다는 전제(유스케이스가 변환 책임을 진다)를 고정한다."""
    from app.domain.user.errors import AmbiguousLoginIdError  # noqa: PLC0415

    # given: kim의 재직 행이 둘이다
    await seed_user(uow_factory, "kim", Role.SALES)
    await seed_user(uow_factory, "kim", Role.USER)

    # when·then: 아이디로 재직 행을 조회하면 → 중복 오류가 올라온다
    with pytest.raises(AmbiguousLoginIdError):
        await uow.users.get_active_by_login_id(LoginId("kim"))
