"""사용자 삭제(퇴사/물리 삭제)와 동시에 일어나는 지정·세션 발급·로그인 경쟁 (AC6, T18·T19).

기대 결과는 모두 '연결 판정이 정확하고 어떤 경우도 500(IntegrityError)이 아니다'이다.
잠금 규칙(미검증, infra가 로컬에서 확인): 삭제는 대상 users 행에 FOR UPDATE,
지정·세션 INSERT는 FOR KEY SHARE.
"""

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.auth.messages import LOGIN_FAILED
from app.application.auth.tokens import hash_token
from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.register_deal import RegisterDeal
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.credentials import Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from app.domain.auth.session import AuthSession, SessionId
from app.domain.common.errors import InvalidReferenceError
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import (
    NOW,
    make_customer_input,
    make_deal,
    make_deal_action_input,
    make_deal_input,
)
from tests.fakes.admin_stack import ADMIN_ACTOR, build_admin_stack
from tests.fakes.auth_stack import build_auth_stack
from tests.fakes.unit_of_work import FixedClock
from tests.support.admin_seed import session_is_active
from tests.support.auth_seed import seed_directory, seed_user
from tests.support.gated_uow import gated
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from app.domain.customer.entities import Customer
    from app.domain.user.entities import User
    from tests.fakes.admin_stack import AdminStack
    from tests.integration.conftest import RealAuth

pytestmark = pytest.mark.integration
WAIT = 0.5
SETTLE = 0.7
IP = "203.0.113.7"


def _admin(real: RealAuth) -> AdminStack:
    return build_admin_stack(real.stack, real.uow_factory, FixedClock(NOW))


async def _customer(real: RealAuth) -> Customer:
    return await RegisterCustomer(real.uow_factory, FixedClock(NOW)).execute(make_customer_input())


async def _seed(real: RealAuth, login: str = "kim") -> User:
    await seed_user(real.uow_factory, "amy", Role.ADMIN)
    return await seed_user(real.uow_factory, login, Role.SALES)


async def test_delete_waits_for_an_inflight_assignment_then_resigns_instead_of_orphaning(
    real_auth: RealAuth,
) -> None:
    admin = _admin(real_auth)
    owner = await _seed(real_auth)
    customer = await _customer(real_auth)

    async with real_auth.uow_factory() as holder:
        assert await holder.users.lock_assignable(owner.id)  # 지정 쪽이 먼저 사용자 행을 붙잡는다
        deletion = asyncio.create_task(
            admin.delete_user.execute(user_id=owner.id, actor=ADMIN_ACTOR)
        )
        await asyncio.sleep(WAIT)
        waiting = not deletion.done()
        await holder.deals.add(make_deal(customer_id=customer.id, owner_user_id=owner.id))
        await holder.commit()
    outcome = await asyncio.wait_for(deletion, timeout=10)

    assert waiting, "삭제가 지정 중인 트랜잭션을 기다리지 않았다"
    assert outcome is DeleteOutcome.RESIGNED  # 새로 생긴 연결을 보고 물리 삭제하지 않는다
    async with real_auth.uow_factory() as uow:
        (deal,) = await uow.deals.list()
        assert deal.details.owner_user_id == owner.id
        assert not (await uow.users.get(owner.id)).is_active


async def test_assignment_started_after_a_resignation_began_is_rejected_as_422_not_500(
    real_auth: RealAuth,
) -> None:
    owner = await _seed(real_auth)
    customer = await _customer(real_auth)
    register = RegisterDeal(real_auth.uow_factory, FixedClock(NOW))

    async with real_auth.uow_factory() as deleter:
        user = await deleter.users.get_for_update(owner.id)
        user.resign(NOW)
        await deleter.users.update(user)  # 미커밋 퇴사
        assignment = asyncio.create_task(
            register.execute(make_deal_input(customer.id, code="NEW-1", owner_user_id=owner.id))
        )
        await asyncio.sleep(WAIT)
        waiting = not assignment.done()
        await deleter.commit()

    assert waiting, "지정이 진행 중인 퇴사 처리를 기다리지 않았다"
    with pytest.raises(InvalidReferenceError):
        await asyncio.wait_for(assignment, timeout=10)
    async with real_auth.uow_factory() as uow:
        assert list(await uow.deals.list()) == []


async def test_assignment_started_during_a_physical_delete_is_rejected_as_422_not_500(
    real_auth: RealAuth,
) -> None:
    owner = await _seed(real_auth)
    customer = await _customer(real_auth)
    register = RegisterDealAction(real_auth.uow_factory, FixedClock(NOW))
    async with real_auth.uow_factory() as uow:
        await ensure_users(uow.users, OWNER_ID)
        deal = make_deal(customer_id=customer.id)
        await uow.deals.add(deal)
        await uow.commit()

    async with real_auth.uow_factory() as deleter:
        await deleter.users.get_for_update(owner.id)
        await deleter.users.delete(owner.id)  # 미커밋 물리 삭제
        assignment = asyncio.create_task(
            register.execute(deal.id, make_deal_action_input(actor_user_id=owner.id))
        )
        await asyncio.sleep(WAIT)
        waiting = not assignment.done()
        await deleter.commit()

    assert waiting, "활동자 지정이 진행 중인 삭제를 기다리지 않았다"
    with pytest.raises(InvalidReferenceError):
        await asyncio.wait_for(assignment, timeout=10)


async def test_session_issue_during_a_physical_delete_fails_as_an_authentication_error(
    real_auth: RealAuth,
) -> None:
    target = await _seed(real_auth)

    async with real_auth.uow_factory() as deleter:
        await deleter.users.get_for_update(target.id)
        await deleter.users.delete(target.id)
        issuing = asyncio.create_task(real_auth.stack.issue.execute(target.to_principal()))
        await asyncio.sleep(WAIT)
        waiting = not issuing.done()
        await deleter.commit()

    assert waiting, "세션 발급이 진행 중인 삭제를 기다리지 않았다"
    with pytest.raises(AuthenticationError):  # IntegrityError(500)가 새어 나오면 안 된다
        await asyncio.wait_for(issuing, timeout=10)


async def test_delete_waits_for_an_inflight_session_issue_and_removes_that_session_too(
    real_auth: RealAuth,
) -> None:
    admin = _admin(real_auth)
    target = await _seed(real_auth)

    session = AuthSession(
        id=SessionId(uuid4()),
        principal=target.to_principal(),
        created_at=NOW,
        expires_at=NOW + timedelta(hours=8),
    )
    async with real_auth.uow_factory() as holder:
        await holder.sessions.add(session, hash_token("late-token"))  # FK 검사가 KEY SHARE를 건다
        deletion = asyncio.create_task(
            admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)
        )
        await asyncio.sleep(WAIT)
        waiting = not deletion.done()
        await holder.commit()
    outcome = await asyncio.wait_for(deletion, timeout=10)

    assert waiting, "삭제가 세션 발급 중인 트랜잭션을 기다리지 않았다"
    assert outcome is DeleteOutcome.DELETED  # 방금 커밋된 세션 행도 지우고 물리 삭제된다
    assert not await session_is_active(real_auth.uow_factory, "late-token")


async def test_physical_delete_blocked_by_an_unseen_reference_falls_back_to_resign(
    real_auth: RealAuth, monkeypatch: pytest.MonkeyPatch
) -> None:
    """has_links가 놓친 연결을 FK가 잡으면 SAVEPOINT 롤백 후 퇴사 처리(T19). 세션 삭제는 유지."""
    admin = _admin(real_auth)
    target = await _seed(real_auth)
    customer = await _customer(real_auth)
    async with real_auth.uow_factory() as uow:
        await uow.deals.add(make_deal(customer_id=customer.id, owner_user_id=target.id))
        await uow.commit()
    token = (await real_auth.stack.issue.execute(target.to_principal())).token

    async def blind(self: SqlUserRepository, user_id: object) -> bool:
        return False

    monkeypatch.setattr(SqlUserRepository, "has_links", blind)

    outcome = await admin.delete_user.execute(user_id=target.id, actor=ADMIN_ACTOR)

    assert outcome is DeleteOutcome.RESIGNED
    async with real_auth.uow_factory() as uow:
        assert not (await uow.users.get(target.id)).is_active
    assert not await session_is_active(real_auth.uow_factory, token)


async def test_a_login_that_read_the_user_before_resignation_does_not_revive_the_row(
    real_auth: RealAuth,
) -> None:
    """로그인이 읽은 뒤 퇴사가 커밋되면, 로그인의 last-login 저장이 deleted_at을 지우면 안 된다."""
    await seed_directory(real_auth.uow_factory)
    target = await _seed(real_auth)
    reached, release = asyncio.Event(), asyncio.Event()
    login_factory = gated(
        real_auth.uow_factory, attribute="users", method="update", reached=reached, release=release
    )
    login = build_auth_stack(login_factory, FixedClock(NOW), real_auth.directory).login

    attempt = asyncio.create_task(
        login.execute(login_id="kim", password=Password("pw-kim"), client_ip=IP)
    )
    await asyncio.wait_for(reached.wait(), timeout=10)  # 로그인이 재직 행을 읽고 저장 직전
    async with real_auth.uow_factory() as uow:
        user = await uow.users.get_for_update(target.id)
        user.resign(NOW)
        await uow.users.update(user)
        await uow.commit()
    release.set()
    outcome = (await asyncio.gather(attempt, return_exceptions=True))[0]

    assert isinstance(outcome, AuthenticationError), repr(outcome)
    assert str(outcome) == LOGIN_FAILED
    async with real_auth.uow_factory() as uow:
        stored = await uow.users.get(target.id)
    assert not stored.is_active  # 퇴사가 되살아나지 않았다
    assert stored.deleted_at == NOW
