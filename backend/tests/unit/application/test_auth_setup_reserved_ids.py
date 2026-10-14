"""최초 설정(SetupFirstAdmin)도 예약 dev 아이디를 첫 admin으로 만들지 않는다 (리뷰 Major 3).

RegisterUser와 같은 오류(InvalidValueError)로 거부하고, admin이 생기지 않으므로 최초 설정은 열린 채
남는다(SETUP_CLOSED가 되지 않고 정상 계정으로 다시 진행할 수 있다).
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.credentials import Password
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from tests.support.auth_seed import active_admin_logins, seed_directory

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork

IP = "10.0.0.1"
PASSWORD = "pw-reserved"  # noqa: S105 - 가짜 값


@pytest.mark.parametrize("reserved", ["dev-admin", "dev-sales", "dev-user", "DEV-ADMIN"])
async def test_setup_admin_rejects_the_reserved_dev_login_ids(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, uow: FakeUnitOfWork, reserved: str
) -> None:
    await seed_directory(uow_factory)
    auth.directory.add_account(reserved.lower(), PASSWORD)  # AD 인증은 통과하는 계정

    with pytest.raises(InvalidValueError):
        await auth.setup_admin.execute(login_id=reserved, password=Password(PASSWORD), client_ip=IP)

    assert await active_admin_logins(uow_factory) == []
    assert uow.sessions._items == {}


async def test_setup_stays_open_after_a_reserved_id_is_rejected(
    auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_directory(uow_factory)
    auth.directory.add_account("dev-admin", PASSWORD)
    auth.directory.add_account("kim", "pw-kim")
    with pytest.raises(InvalidValueError):
        await auth.setup_admin.execute(
            login_id="dev-admin", password=Password(PASSWORD), client_ip=IP
        )

    issued = await auth.setup_admin.execute(
        login_id="kim", password=Password("pw-kim"), client_ip=IP
    )

    assert (issued.principal.subject, issued.principal.role) == ("kim", Role.ADMIN)
    assert await active_admin_logins(uow_factory) == ["kim"]
