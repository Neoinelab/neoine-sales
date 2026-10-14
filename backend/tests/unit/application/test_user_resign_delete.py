"""사용자 삭제의 퇴사 분기: 연결이 있으면 행을 남기고 퇴사 처리 (AC3·4·5, T11·T14·T19)."""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.tokens import hash_token
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from app.domain.user.errors import UserInUseError
from app.domain.user.value_objects import UserDeleteReason
from tests.factories import NOW
from tests.fakes.admin_stack import DEV_ACTOR
from tests.support.admin_seed import session_is_active
from tests.support.auth_seed import seed_user
from tests.support.user_links import LINK_KINDS, link_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_delete_user_with_any_reference_resigns_instead_of_deleting(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, kind: str
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, kind)

    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.RESIGNED
    async with uow_factory() as uow:
        kept = await uow.users.get(target.id)
    assert kept.deleted_at == NOW
    assert kept.delete_reason is UserDeleteReason.RESIGNED
    assert kept.login_id.value == "kim"


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_resigning_still_deletes_the_users_session_rows(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory, kind: str
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, kind)
    token = (await auth.issue.execute(target.to_principal())).token

    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert not await session_is_active(uow_factory, token)
    async with uow_factory() as uow:
        assert await uow.sessions.get_by_token_hash(hash_token(token)) is None


async def test_a_user_who_only_registered_himself_is_not_linked(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """자기참조(자기 자신이 등록자)는 연결이 아니다."""
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)

    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.DELETED


async def test_resigned_user_keeps_the_references_that_pointed_to_him(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, "deal_owner")

    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    async with uow_factory() as uow:
        (deal,) = await uow.deals.list()
        refs = await uow.users.get_refs([deal.details.owner_user_id])
    assert refs[target.id].resigned is True
    assert refs[target.id].label.endswith("(퇴사)")


async def test_resigned_user_cannot_be_deleted_again(
    admin: AdminStack, auth: AuthStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, "deal_owner")
    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    with pytest.raises(InvalidStateError, match="이미 퇴사"):
        await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    async with uow_factory() as uow:
        assert (await uow.users.get(target.id)).deleted_at == NOW  # 첫 퇴사 시각 그대로


async def test_resigned_user_cannot_log_in_even_with_a_surviving_session(
    auth: AuthStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """세션 행이 남아 있어도 Authenticate가 퇴사 여부를 매 요청 확인한다(AC4)."""
    target = await seed_user(uow_factory, "kim", Role.SALES)
    token = (await auth.issue.execute(target.to_principal())).token
    async with uow_factory() as active:
        user = await active.users.get(target.id)
        user.resign(NOW)
        await active.users.update(user)
        await active.commit()

    with pytest.raises(AuthenticationError):
        await auth.authenticate.execute(token)


async def test_last_admin_protection_also_applies_to_the_resign_branch(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await link_user(uow_factory, boss, "deal_owner")

    with pytest.raises(InvalidStateError, match="마지막 관리자"):
        await admin.delete_user.execute(user_id=boss.id, actor=DEV_ACTOR)

    async with uow_factory() as uow:
        assert (await uow.users.get(boss.id)).is_active


async def test_self_protection_also_applies_to_the_resign_branch(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    me = await seed_user(uow_factory, "root", Role.ADMIN)
    await seed_user(uow_factory, "boss", Role.ADMIN)
    await link_user(uow_factory, me, "deal_owner")

    with pytest.raises(InvalidStateError, match="자기 자신"):
        await admin.delete_user.execute(user_id=me.id, actor=me.to_principal())


async def test_a_resigned_admin_is_not_counted_as_an_active_admin(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    boss = await seed_user(uow_factory, "boss", Role.ADMIN)
    await link_user(uow_factory, boss, "deal_owner")
    await admin.delete_user.execute(user_id=boss.id, actor=root.to_principal())

    with pytest.raises(InvalidStateError, match="마지막 관리자"):
        await admin.delete_user.execute(user_id=root.id, actor=DEV_ACTOR)


async def test_physical_delete_blocked_by_a_late_reference_falls_back_to_resign(
    admin: AdminStack,
    uow: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """has_links가 놓친 연결을 FK(UserInUseError)가 잡아도 500이 아니라 퇴사 처리가 된다(T19)."""
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, "deal_owner")

    with pytest.raises(UserInUseError):  # 전제: 이 Fake는 연결이 있으면 물리 삭제를 거부한다
        await uow.users.delete(target.id)

    async def no_links_seen(_: object) -> bool:
        return False

    monkeypatch.setattr(uow.users, "has_links", no_links_seen)
    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.RESIGNED
    async with uow_factory() as active:
        assert not (await active.users.get(target.id)).is_active
