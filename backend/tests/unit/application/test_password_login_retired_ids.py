"""PasswordLogin은 폐지된 개발 로그인 아이디(dev-admin|dev-sales|dev-user)를 거부한다.

AD에 같은 이름 계정이 있거나 local 해시가 있어도 401 LOGIN_FAILED(같은 문구)이고,
AD 호출과 해시 검증을 하지 않으며, 실패 1회가 시도 제한에 남고 세션은 만들어지지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.credentials import Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.support.auth_seed import (
    account_key,
    seed_auth_mode,
    seed_directory,
    seed_local_user,
    seed_user,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"
PW = "pw-dev-1234"  # 가짜 값
RETIRED = ["dev-admin", "dev-sales", "dev-user", "DEV-Admin"]
OTHER_DEV = ["dev-qa", "dev-admin2", "dev-ops"]


@pytest.mark.parametrize("login_id", RETIRED)
async def test_retired_dev_login_id_is_rejected_without_calling_the_directory(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    directory: FakeDirectoryAuthenticator,
    login_id: str,
) -> None:
    """예약 아이디 셋은 AD에 계정이 있어도 401이고 AD를 부르지 않는다.

    테스트 코드: AU-020
    """
    # given: AD에 계정이 있고 users에도 등록된 예약 아이디
    await seed_directory(uow_factory)
    await seed_user(uow_factory, login_id, Role.SALES)
    directory.add_account(login_id, PW)  # AD 인증은 통과하는 계정

    # when: 예약 아이디로 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.password_login.execute(login_id=login_id, password=Password(PW), client_ip=IP)

    # then: 공통 실패이고 AD 호출·세션이 없으며 실패가 1회 센다
    assert str(caught.value) == LOGIN_FAILED
    assert directory.authenticate_calls == []
    assert directory.discover_calls == []
    assert uow.sessions._items == {}
    assert uow.login_failures._items[account_key(login_id.lower())].failures == 1


@pytest.mark.parametrize("login_id", RETIRED)
async def test_retired_dev_login_id_is_rejected_in_local_mode(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    uow: FakeUnitOfWork,
    login_id: str,
) -> None:
    """local 모드에서도 예약 아이디는 해시가 맞아도 401이다.

    테스트 코드: AU-020
    """
    # given: local 모드, 올바른 비밀번호의 해시가 있는 예약 아이디
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_local_user(uow_factory, login_id, PW, Role.SALES)  # 올바른 비밀번호의 해시가 있다

    # when: 예약 아이디로 로그인한다
    with pytest.raises(AuthenticationError) as caught:
        await auth.password_login.execute(login_id=login_id, password=Password(PW), client_ip=IP)

    # then: 공통 실패이고 해시 검증·세션이 없으며 실패가 1회 센다
    assert str(caught.value) == LOGIN_FAILED
    assert auth.hasher.verify_calls == []
    assert uow.sessions._items == {}
    assert uow.login_failures._items[account_key(login_id.lower())].failures == 1


@pytest.mark.parametrize("login_id", ["devops", *OTHER_DEV])
async def test_other_ids_can_still_sign_in_in_local_mode(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, login_id: str
) -> None:
    """예약 아이디가 아닌 아이디는 local 모드에서 로그인된다.

    테스트 코드: AU-021
    """
    # given: local 모드, 예약이 아닌 dev- 계열 아이디의 admin
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_local_user(uow_factory, login_id, PW, Role.ADMIN)

    # when: 로그인한다
    outcome = await auth.password_login.execute(
        login_id=login_id, password=Password(PW), client_ip=IP
    )

    # then: 로그인된다
    assert outcome.session.principal.subject == login_id


@pytest.mark.parametrize("login_id", OTHER_DEV)
async def test_other_dev_prefixed_id_follows_the_normal_directory_flow(
    auth: AuthStack,
    uow_factory: UnitOfWorkFactory,
    directory: FakeDirectoryAuthenticator,
    login_id: str,
) -> None:
    """예약이 아닌 dev- 아이디는 일반 AD 흐름으로 로그인된다.

    테스트 코드: AU-021
    """
    # given: AD 설정과 AD 계정이 있는 dev- 계열 아이디
    await seed_directory(uow_factory)
    await seed_user(uow_factory, login_id, Role.SALES)
    directory.add_account(login_id, PW)

    # when: 로그인한다
    outcome = await auth.password_login.execute(
        login_id=login_id, password=Password(PW), client_ip=IP
    )

    # then: AD를 거쳐 로그인된다
    assert outcome.session.principal.subject == login_id
    assert len(directory.authenticate_calls) == 1
