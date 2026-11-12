"""local 첫 admin 등록의 구현 규칙(BDD 밖): 해시 계산은 DB 트랜잭션 밖에서 한다.

첫 admin 등록의 케이스(SU-029~SU-038)는 `test_setup_local_admin_cases.py`가 맡는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.credentials import Password
from app.domain.auth.mode import AuthMode
from tests.support.auth_seed import seed_auth_mode, seed_storage

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork


@pytest.fixture
async def local_ready(uow_factory: UnitOfWorkFactory) -> None:
    """방식 local, 저장 위치가 등록된 상태."""
    await seed_auth_mode(uow_factory, AuthMode.LOCAL)
    await seed_storage(uow_factory)


@pytest.mark.usefixtures("local_ready")
async def test_local_setup_hashes_outside_any_transaction(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    """scrypt 계산 동안 DB 트랜잭션을 잡지 않는다(해시는 열린 UoW 밖에서 계산)."""
    # given: 해시 계산 시점에 열려 있는 UoW 수를 기록하는 해셔
    seen: list[int] = []
    original = auth.hasher.hash

    async def spy(password: Password):  # type: ignore[no-untyped-def]  # noqa: ANN202
        seen.append(uow.open_units)
        return await original(password)

    auth.hasher.hash = spy  # type: ignore[method-assign]

    # when: local 첫 admin을 등록한다
    await auth.setup_local_admin.execute(
        login_id="kim", password=Password("Passw0rd-ok"), display_name="김관리"
    )

    # then: 해시 계산 시점에 열린 UoW는 0개였다
    assert seen == [0]
