"""참조하는 사용자 행이 없을 때 FK 위반이 500이 아니라 의도한 실패로 끝난다.

저장소 계약(tests/unit/repositories/test_user_reference_fk_contract.py):
FK 위반은 UserNotFoundError.
- 로그인: 세션 INSERT 시점에 사용자 행이 없으면 LOGIN_FAILED(AuthenticationError).
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.credentials import Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from tests.support.auth_seed import seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"


async def test_login_whose_user_row_is_missing_at_the_session_insert_is_login_failed(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """세션을 만들 때 사용자 행이 없으면 로그인은 LOGIN_FAILED 오류이고 세션이 남지 않는다."""
    # given: AD 설정, sales 사용자 kim, 세션 INSERT 시점에 사용자 행이 없는 Fake
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)
    uow.sessions.user_exists = lambda _user_id: False  # 세션 INSERT 시점에 사용자 행이 없음

    # when·then: kim이 로그인하면 LOGIN_FAILED 인증 오류다
    with pytest.raises(AuthenticationError) as caught:
        await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: 세션이 저장되지 않는다
    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert uow.sessions._items == {}


async def test_login_of_an_existing_user_still_issues_a_session_with_the_fk_check_on(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    """사용자 행이 있으면 FK 검사를 켜도 로그인은 세션을 발급한다."""
    # given: AD 설정, sales 사용자 kim, 사용자 행 존재를 검사하는 Fake 세션 저장소
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)
    uow.sessions.user_exists = lambda user_id: user_id in uow.users._items

    # when: kim이 로그인한다
    outcome = await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    # then: 로그인한 사용자가 kim이고 세션이 하나 저장된다
    assert outcome.session.principal.subject == "kim"
    assert len(uow.sessions._items) == 1
