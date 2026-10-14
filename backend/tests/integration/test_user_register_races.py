"""login_id 유일성은 DB 인덱스 없이 roster 잠금 안의 재직자 확인으로 지킨다 (AC7, 추가 지시).

실제 PostgreSQL 세션을 겹쳐 동시 등록 중 정확히 한 건만 성공하고 나머지는
409(AlreadyExistsError)임을 고정한다. 퇴사자의 login_id는 재사용할 수 있고 그때마다 새 행이 생긴다.
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError
from app.domain.user.value_objects import UserStatusFilter
from tests.factories import NOW
from tests.factories_auth import make_user
from tests.fakes.admin_stack import build_admin_stack
from tests.fakes.unit_of_work import FixedClock
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.domain.auth.principal import Principal
    from tests.fakes.admin_stack import AdminStack
    from tests.integration.conftest import RealAuth

pytestmark = pytest.mark.integration
WAIT = 0.5


def _admin(real: RealAuth) -> AdminStack:
    return build_admin_stack(real.stack, real.uow_factory, FixedClock(NOW))


async def _actor(real: RealAuth) -> Principal:
    return (await seed_user(real.uow_factory, "amy", Role.ADMIN)).to_principal()


async def _rows(real: RealAuth, login_id: str) -> list[tuple[bool, str]]:
    async with real.uow_factory() as uow:
        users = await uow.users.list_users(status=UserStatusFilter.ALL, limit=200)
    return [(u.is_active, u.role.value) for u in users if u.login_id == LoginId(login_id)]


async def test_concurrent_registration_of_the_same_login_id_lets_exactly_one_win(
    real_auth: RealAuth,
) -> None:
    admin, actor = _admin(real_auth), await _actor(real_auth)

    results = await asyncio.gather(
        admin.register_user.execute(login_id="kim", role=Role.SALES, actor=actor),
        admin.register_user.execute(login_id="KIM", role=Role.USER, actor=actor),
        admin.register_user.execute(login_id=" kim ", role=Role.ADMIN, actor=actor),
        return_exceptions=True,
    )

    failures = [r for r in results if isinstance(r, BaseException)]
    assert len(failures) == 2
    assert all(isinstance(f, AlreadyExistsError) for f in failures)
    assert len(await _rows(real_auth, "kim")) == 1


async def test_registration_waits_for_the_roster_lock(real_auth: RealAuth) -> None:
    admin, actor = _admin(real_auth), await _actor(real_auth)

    async with real_auth.uow_factory() as holder:
        await holder.users.lock_roster()
        registration = asyncio.create_task(
            admin.register_user.execute(login_id="kim", role=Role.SALES, actor=actor)
        )
        await asyncio.sleep(WAIT)
        waiting = not registration.done()
    await asyncio.wait_for(registration, timeout=10)

    assert waiting, "등록이 명단 잠금 없이 진행됐다"
    assert len(await _rows(real_auth, "kim")) == 1


async def test_registration_that_waited_sees_an_active_duplicate_committed_meanwhile(
    real_auth: RealAuth,
) -> None:
    admin, actor = _admin(real_auth), await _actor(real_auth)

    async with real_auth.uow_factory() as holder:
        await holder.users.lock_roster()
        registration = asyncio.create_task(
            admin.register_user.execute(login_id="kim", role=Role.SALES, actor=actor)
        )
        await asyncio.sleep(WAIT)
        await holder.users.add(make_user("kim", Role.USER))
        await holder.commit()

    with pytest.raises(AlreadyExistsError):
        await asyncio.wait_for(registration, timeout=10)
    assert await _rows(real_auth, "kim") == [(True, "user")]


async def test_registration_that_waited_for_a_resignation_creates_a_new_row(
    real_auth: RealAuth,
) -> None:
    """퇴사가 먼저 확정되면 같은 login_id 등록이 새 행으로 성공한다(퇴사 행은 그대로)."""
    admin, actor = _admin(real_auth), await _actor(real_auth)
    old = await seed_user(real_auth.uow_factory, "kim", Role.SALES)

    async with real_auth.uow_factory() as holder:
        await holder.users.lock_roster()
        registration = asyncio.create_task(
            admin.register_user.execute(login_id="kim", role=Role.USER, actor=actor)
        )
        await asyncio.sleep(WAIT)
        stored = await holder.users.get_for_update(old.id)
        stored.resign(NOW)
        await holder.users.update(stored)
        await holder.commit()

    new = await asyncio.wait_for(registration, timeout=10)

    assert new.id != old.id
    assert sorted(await _rows(real_auth, "kim")) == [(False, "sales"), (True, "user")]
