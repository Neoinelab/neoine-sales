"""유스케이스 수준의 명단 경쟁(실제 PostgreSQL): 최초 admin 동시 등록, 1단계 저장과 2단계 경쟁.

T-P15·T-P25, SETUP-7. (사용자 삭제와의 경쟁 T-P16은 S5 범위다.)
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from app.domain.auth.credentials import Password
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories_auth import make_directory_settings, make_user
from tests.support.auth_seed import active_admin_logins, seed_directory

if TYPE_CHECKING:
    from tests.integration.conftest import RealAuth

pytestmark = pytest.mark.integration
IP = "10.0.0.1"
WAIT = 0.5


async def _setup(real: RealAuth, login_id: str, password: str) -> object:
    return await real.stack.setup_admin.execute(
        login_id=login_id, password=Password(password), client_ip=IP
    )


async def test_concurrent_first_admin_setup_creates_one_admin(real_auth: RealAuth) -> None:
    await seed_directory(real_auth.uow_factory)
    barrier = asyncio.Barrier(2)

    async def both_authenticated_before_either_registers() -> None:
        await asyncio.wait_for(barrier.wait(), timeout=10)

    real_auth.directory.on_authenticate = both_authenticated_before_either_registers

    results = await asyncio.gather(
        _setup(real_auth, "kim", "pw-kim"),
        _setup(real_auth, "lee", "pw-lee"),
        return_exceptions=True,
    )

    failures = [r for r in results if isinstance(r, BaseException)]
    assert len(failures) == 1
    assert isinstance(failures[0], InvalidStateError)
    assert len(await active_admin_logins(real_auth.uow_factory)) == 1


async def test_setup_directory_cannot_save_after_admin_created(real_auth: RealAuth) -> None:
    original = await seed_directory(real_auth.uow_factory)
    probing = asyncio.Event()
    release = asyncio.Event()

    async def hold_probe_open() -> None:
        probing.set()
        await asyncio.wait_for(release.wait(), timeout=10)

    real_auth.directory.on_probe = hold_probe_open
    step_one = asyncio.create_task(
        real_auth.stack.register_directory.execute(
            make_directory_settings(base_dn="dc=new,dc=test")
        )
    )
    await asyncio.wait_for(probing.wait(), timeout=10)

    await _setup(real_auth, "kim", "pw-kim")  # 1단계가 probe 중일 때 2단계가 끝난다
    release.set()

    with pytest.raises(InvalidStateError):
        await step_one
    async with real_auth.uow_factory() as uow:
        assert await uow.directory_settings.get() == original


async def test_setup_directory_waits_for_the_roster_lock(real_auth: RealAuth) -> None:
    await seed_directory(real_auth.uow_factory)
    changed = make_directory_settings(base_dn="dc=new,dc=test")

    async with real_auth.uow_factory() as holder:
        await holder.users.lock_roster()
        step_one = asyncio.create_task(real_auth.stack.register_directory.execute(changed))
        await asyncio.sleep(WAIT)
        waiting = not step_one.done()
    stored = await asyncio.wait_for(step_one, timeout=10)

    assert waiting, "1단계 저장이 명단 잠금 없이 진행됐다"
    assert stored.revision == 2


async def test_setup_admin_waits_for_the_roster_lock(real_auth: RealAuth) -> None:
    await seed_directory(real_auth.uow_factory)

    async with real_auth.uow_factory() as holder:
        await holder.users.lock_roster()
        step_two = asyncio.create_task(_setup(real_auth, "kim", "pw-kim"))
        await asyncio.sleep(WAIT)
        waiting = not step_two.done()
    await asyncio.wait_for(step_two, timeout=10)

    assert waiting, "2단계 등록이 명단 잠금 없이 진행됐다"
    assert await active_admin_logins(real_auth.uow_factory) == ["kim"]


async def test_setup_admin_blocked_by_a_concurrent_admin_insert_keeps_one_admin(
    real_auth: RealAuth,
) -> None:
    """잠금을 쥔 쪽이 admin을 만들고 커밋하면, 기다리던 2단계는 재확인에서 409로 끝난다."""
    await seed_directory(real_auth.uow_factory)

    async with real_auth.uow_factory() as holder:
        await holder.users.lock_roster()
        step_two = asyncio.create_task(_setup(real_auth, "kim", "pw-kim"))
        await asyncio.sleep(WAIT)
        await holder.users.add(make_user("boss", Role.ADMIN))
        await holder.commit()

    with pytest.raises(InvalidStateError):
        await asyncio.wait_for(step_two, timeout=10)
    assert await active_admin_logins(real_auth.uow_factory) == ["boss"]
