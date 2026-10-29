"""참조하는 사용자 행이 없을 때 FK 위반이 500이 아니라 의도한 실패로 끝난다 (리뷰 Minor 1·2).

저장소 계약(tests/unit/repositories/test_user_reference_fk_contract.py):
FK 위반은 UserNotFoundError.
- 로그인: 세션 INSERT 시점에 사용자 행이 없으면 LOGIN_FAILED(AuthenticationError).
- 등록: 요청 admin(actor) 행이 없어 created_by FK가 실패하면 AuthenticationError(401).
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.credentials import LoginId, Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from tests.factories_auth import make_user
from tests.fakes.admin_stack import ADMIN_ACTOR
from tests.support.admin_seed import active_logins
from tests.support.auth_seed import seed_directory, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"


async def test_login_whose_user_row_is_missing_at_the_session_insert_is_login_failed(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)
    uow.sessions.user_exists = lambda _user_id: False  # 세션 INSERT 시점에 사용자 행이 없음

    with pytest.raises(AuthenticationError) as caught:
        await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    assert type(caught.value) is AuthenticationError
    assert str(caught.value) == LOGIN_FAILED
    assert uow.sessions._items == {}


async def test_login_of_an_existing_user_still_issues_a_session_with_the_fk_check_on(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    await seed_directory(uow_factory)
    await seed_user(uow_factory, "kim", Role.SALES)
    uow.sessions.user_exists = lambda user_id: user_id in uow.users._items

    outcome = await auth.login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)

    assert outcome.session.principal.subject == "kim"
    assert len(uow.sessions._items) == 1


async def test_register_with_a_missing_actor_row_is_an_authentication_error(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    uow.users.enforce_creator_fk = True  # ADMIN_ACTOR의 행은 만들지 않았다

    with pytest.raises(AuthenticationError):
        await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    assert await active_logins(uow_factory) == []


async def test_register_with_an_existing_actor_succeeds_with_the_fk_check_on(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork
) -> None:
    async with uow_factory() as active:
        await active.users.add(make_user("root", Role.ADMIN, entity_id=ADMIN_ACTOR.user_id))
        await active.commit()
    uow.users.enforce_creator_fk = True

    user = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    assert user.created_by_user_id == ADMIN_ACTOR.user_id
    async with uow_factory() as active:
        assert await active.users.get_active_by_login_id(LoginId("kim")) is not None
