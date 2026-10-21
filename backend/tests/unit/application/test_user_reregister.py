"""AC7: 퇴사자의 login_id 재등록은 항상 새 행(새 id). 퇴사 행은 복구·재사용되지 않는다."""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError
from tests.factories import NOW
from tests.fakes.admin_stack import ADMIN_ACTOR
from tests.support.auth_seed import seed_user
from tests.support.user_links import link_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack


async def test_register_after_resignation_creates_a_new_user_with_a_new_id(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    old = await seed_user(uow_factory, "kim", Role.SALES, resigned=True)

    new = await admin.register_user.execute(login_id="kim", role=Role.USER, actor=ADMIN_ACTOR)

    assert new.id != old.id
    assert new.is_active
    assert new.role is Role.USER
    async with uow_factory() as uow:
        active = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert active is not None
    assert active.id == new.id


async def test_old_row_stays_resigned_and_unchanged_after_reregistration(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    old = await seed_user(uow_factory, "kim", Role.ADMIN, resigned=True, now=NOW)

    await admin.register_user.execute(login_id="kim", role=Role.USER, actor=ADMIN_ACTOR)

    async with uow_factory() as uow:
        stored = await uow.users.get(old.id)
    assert stored.deleted_at == NOW
    assert stored.role is Role.ADMIN  # 새 등록의 역할이 옛 행에 덮어써지지 않는다
    assert not stored.is_active


async def test_history_stays_attached_to_the_resigned_row_not_the_new_one(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    old = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, old, "deal_owner")
    async with uow_factory() as uow:
        user = await uow.users.get(old.id)
        user.resign(NOW)
        await uow.users.update(user)
        await uow.commit()

    new = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    async with uow_factory() as uow:
        (item,) = await uow.deals.search(DealQuery())
        deal = item.deal
        refs = await uow.users.get_refs([deal.details.owner_user_id, new.id])
    assert deal.details.owner_user_id == old.id
    assert refs[old.id].resigned is True
    assert refs[new.id].resigned is False


async def test_many_resignations_of_the_same_login_id_can_coexist_with_one_active(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    first = await seed_user(uow_factory, "kim", Role.SALES, resigned=True)
    second = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)
    async with uow_factory() as uow:
        again = await uow.users.get(second.id)
        again.resign(NOW)
        await uow.users.update(again)
        await uow.commit()

    third = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    assert len({first.id, second.id, third.id}) == 3
    async with uow_factory() as uow:
        active = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert active is not None
    assert active.id == third.id


@pytest.mark.parametrize("again", ["kim", "KIM", " Kim "])
async def test_register_conflicts_with_an_active_user_even_if_older_rows_resigned(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, again: str
) -> None:
    await seed_user(uow_factory, "kim", Role.SALES, resigned=True)
    current = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    with pytest.raises(AlreadyExistsError):
        await admin.register_user.execute(login_id=again, role=Role.ADMIN, actor=ADMIN_ACTOR)

    async with uow_factory() as uow:
        active = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert active is not None
    assert active.id == current.id


async def test_second_sequential_registration_of_the_same_login_id_conflicts(
    admin: AdminStack,
) -> None:
    await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    with pytest.raises(AlreadyExistsError):
        await admin.register_user.execute(login_id="kim", role=Role.USER, actor=ADMIN_ACTOR)
