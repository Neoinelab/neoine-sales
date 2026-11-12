"""인증 방식별 진행 상태의 BDD 밖 규칙: 방식 어느 쪽이든 재직 admin이 있으면 모든 단계가 끝난다.

방식 판정 케이스는 `test_setup_progress.py`(SU-001~SU-006)가 맡는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.support.auth_seed import seed_auth_mode, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.auth_stack import AuthStack


async def _flags(auth: AuthStack) -> tuple[bool, bool, bool]:
    status = await auth.status.execute()
    return (status.needs_directory_setup, status.needs_storage_setup, status.needs_admin_setup)


@pytest.mark.parametrize("mode", list(AuthMode))
async def test_auth_status_closes_every_step_once_an_admin_exists(
    auth: AuthStack, uow_factory: UnitOfWorkFactory, mode: AuthMode
) -> None:
    """저장된 방식이 ad든 local이든 재직 admin이 있으면 모든 단계가 끝남이다."""
    # given: 방식이 저장되어 있고 재직 admin이 있다
    await seed_auth_mode(uow_factory, mode)
    await seed_user(uow_factory, "boss", Role.ADMIN)

    # when: 진행 상태를 조회한다
    status = await auth.status.execute()

    # then: 방식은 그대로이고 세 단계 플래그가 모두 false다
    assert status.auth_mode is mode
    assert await _flags(auth) == (False, False, False)
