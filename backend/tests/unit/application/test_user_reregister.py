"""AC7: 퇴사자의 login_id 재등록은 항상 새 행(새 id). 퇴사 행은 복구·재사용되지 않는다."""

from datetime import date
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
    """퇴사한 아이디를 다시 등록하면 새 id의 새 행이 생긴다

    테스트 코드: US-008
    """
    # given: 퇴사한 kim
    old = await seed_user(uow_factory, "kim", Role.SALES, resigned=True)

    # when: 같은 아이디를 user 역할로 다시 등록한다
    new = await admin.register_user.execute(login_id="kim", role=Role.USER, actor=ADMIN_ACTOR)

    # then: 새 id의 재직 사용자이고 그 아이디의 재직 행은 새 행이다
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
    """다시 등록해도 퇴사 행은 시각·역할이 그대로다

    테스트 코드: US-008
    """
    # given: 퇴사한 admin kim
    old = await seed_user(uow_factory, "kim", Role.ADMIN, resigned=True, now=NOW)

    # when: 같은 아이디를 user 역할로 다시 등록한다
    await admin.register_user.execute(login_id="kim", role=Role.USER, actor=ADMIN_ACTOR)

    # then: 퇴사 행은 퇴사 시각과 admin 역할 그대로다
    async with uow_factory() as uow:
        stored = await uow.users.get(old.id)
    assert stored.deleted_at == NOW
    assert stored.role is Role.ADMIN  # 새 등록의 역할이 옛 행에 덮어써지지 않는다
    assert not stored.is_active


async def test_history_stays_attached_to_the_resigned_row_not_the_new_one(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """퇴사 행을 가리키던 이력은 계속 퇴사 행을 가리킨다

    테스트 코드: US-008
    """
    # given: 소유 Deal 때문에 퇴사 처리된 kim
    old = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, old, "deal_owner")
    async with uow_factory() as uow:
        user = await uow.users.get(old.id)
        user.resign(NOW)
        await uow.users.update(user)
        await uow.commit()

    # when: 같은 아이디를 다시 등록한다
    new = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    # then: Deal의 Owner는 예전 행이고 퇴사로 표시되며 새 행은 재직이다
    async with uow_factory() as uow:
        (item,) = await uow.deals.search(DealQuery().with_today(date(2026, 1, 1)))
        deal = item.deal
        refs = await uow.users.get_refs([deal.details.owner_user_id, new.id])
    assert deal.details.owner_user_id == old.id
    assert refs[old.id].resigned is True
    assert refs[new.id].resigned is False


async def test_many_resignations_of_the_same_login_id_can_coexist_with_one_active(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """같은 아이디의 퇴사 행은 여러 개 있을 수 있고 재직 행은 하나다"""
    # given: 퇴사 이력이 있는 kim
    first = await seed_user(uow_factory, "kim", Role.SALES, resigned=True)
    # when: 재등록과 퇴사를 반복한 뒤 다시 등록한다
    second = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)
    # then: 세 행의 id가 모두 다르고 재직 행은 마지막 하나다
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
    """같은 아이디의 퇴사 행이 있어도 재직자가 있으면 중복 오류다

    테스트 코드: US-007
    """
    # given: 퇴사 행과 재직 행이 있는 kim
    await seed_user(uow_factory, "kim", Role.SALES, resigned=True)
    current = await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    # when: 표기가 다른 같은 아이디로 등록한다
    with pytest.raises(AlreadyExistsError):
        await admin.register_user.execute(login_id=again, role=Role.ADMIN, actor=ADMIN_ACTOR)

    # then: 이미 존재 오류이고 재직 행은 그대로다
    async with uow_factory() as uow:
        active = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert active is not None
    assert active.id == current.id


async def test_second_sequential_registration_of_the_same_login_id_conflicts(
    admin: AdminStack,
) -> None:
    """같은 아이디를 연달아 등록하면 두 번째는 중복 오류다

    테스트 코드: US-007
    """
    # given: 방금 등록한 kim
    await admin.register_user.execute(login_id="kim", role=Role.SALES, actor=ADMIN_ACTOR)

    # when: 같은 아이디로 다시 등록한다
    with pytest.raises(AlreadyExistsError):
        await admin.register_user.execute(login_id="kim", role=Role.USER, actor=ADMIN_ACTOR)
    # then: 이미 존재 오류다
