"""사용자 삭제의 명단 경쟁(PostgreSQL): 마지막 admin 보호와 lock_roster 직렬화 (USER-5, T-P16)."""

import asyncio
from typing import TYPE_CHECKING

import pytest

from app.application.auth.tokens import hash_token
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories import NOW
from tests.fakes.admin_stack import ADMIN_ACTOR, build_admin_stack
from tests.fakes.unit_of_work import FixedClock
from tests.support.admin_seed import active_logins, session_is_active
from tests.support.auth_seed import active_admin_logins, seed_user

if TYPE_CHECKING:
    from tests.fakes.admin_stack import AdminStack
    from tests.integration.conftest import RealAuth

pytestmark = pytest.mark.integration
WAIT = 0.5


def _admin_stack(real: RealAuth) -> AdminStack:
    return build_admin_stack(real.stack, real.uow_factory, FixedClock(NOW))


async def test_concurrent_mutual_admin_deletion_keeps_one_admin(real_auth: RealAuth) -> None:
    admin = _admin_stack(real_auth)
    amy = await seed_user(real_auth.uow_factory, "amy", Role.ADMIN)
    bob = await seed_user(real_auth.uow_factory, "bob", Role.ADMIN)

    results = await asyncio.gather(
        admin.delete_user.execute(user_id=bob.id, actor=amy.to_principal()),
        admin.delete_user.execute(user_id=amy.id, actor=bob.to_principal()),
        return_exceptions=True,
    )

    failures = [r for r in results if isinstance(r, BaseException)]
    assert len(failures) == 1
    assert isinstance(failures[0], InvalidStateError)
    assert len(await active_admin_logins(real_auth.uow_factory)) == 1


async def test_delete_user_waits_for_the_roster_lock(real_auth: RealAuth) -> None:
    admin = _admin_stack(real_auth)
    await seed_user(real_auth.uow_factory, "amy", Role.ADMIN)
    target = await seed_user(real_auth.uow_factory, "kim", Role.SALES)

    async with real_auth.uow_factory() as holder:
        await holder.users.lock_roster()
        deletion = asyncio.create_task(
            admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)
        )
        await asyncio.sleep(WAIT)
        waiting = not deletion.done()
    await asyncio.wait_for(deletion, timeout=10)

    assert waiting, "사용자 삭제가 명단 잠금 없이 진행됐다"
    assert await active_logins(real_auth.uow_factory) == ["amy"]


async def test_delete_that_waited_rechecks_the_last_admin_rule_after_the_lock(
    real_auth: RealAuth,
) -> None:
    """잠금을 쥔 쪽이 다른 admin을 지워 커밋하면, 기다리던 삭제는 '마지막 admin'으로 막힌다."""
    admin = _admin_stack(real_auth)
    amy = await seed_user(real_auth.uow_factory, "amy", Role.ADMIN)
    bob = await seed_user(real_auth.uow_factory, "bob", Role.ADMIN)

    async with real_auth.uow_factory() as holder:
        await holder.users.lock_roster()
        deletion = asyncio.create_task(
            admin.delete_user.execute(user_id=amy.id, actor=bob.to_principal())
        )
        await asyncio.sleep(WAIT)
        victim = await holder.users.get(bob.id)
        await holder.users.delete(victim.id)
        await holder.commit()

    with pytest.raises(InvalidStateError, match="마지막 관리자"):
        await asyncio.wait_for(deletion, timeout=10)

    assert await active_logins(real_auth.uow_factory) == ["amy"]


async def test_deleting_a_user_removes_their_session_rows_in_the_database(
    real_auth: RealAuth,
) -> None:
    admin = _admin_stack(real_auth)
    await seed_user(real_auth.uow_factory, "amy", Role.ADMIN)
    target = await seed_user(real_auth.uow_factory, "kim", Role.SALES)
    token = (await real_auth.stack.issue.execute(target.to_principal())).token
    assert await session_is_active(real_auth.uow_factory, token)

    outcome = await admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)

    assert outcome is DeleteOutcome.DELETED  # FK가 있는 세션 행을 먼저 지워야 물리 삭제가 된다
    assert not await session_is_active(real_auth.uow_factory, token)
    async with real_auth.uow_factory() as uow:
        assert await uow.sessions.get_by_token_hash(hash_token(token)) is None
