"""AC9: 사용자 목록의 상태 필터(active|resigned|all)와 퇴사 정보 (T23)."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.user.value_objects import UserDeleteReason, UserStatusFilter
from tests.factories import later
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack


async def _seed(uow_factory: UnitOfWorkFactory) -> None:
    await seed_user(uow_factory, "amy", Role.ADMIN, now=later(1))
    await seed_user(uow_factory, "old1", Role.SALES, resigned=True, now=later(2))
    await seed_user(uow_factory, "bob", Role.USER, now=later(3))
    await seed_user(uow_factory, "old2", Role.USER, resigned=True, now=later(4))


async def test_list_users_defaults_to_active_users_only(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _seed(uow_factory)

    users = await admin.list_users.execute()

    assert [u.login_id.value for u in users] == ["amy", "bob"]


async def test_list_users_status_resigned_returns_only_resigned_users(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _seed(uow_factory)

    users = await admin.list_users.execute(status=UserStatusFilter.RESIGNED)

    assert [u.login_id.value for u in users] == ["old1", "old2"]
    assert all(u.deleted_at is not None for u in users)
    assert all(u.delete_reason is UserDeleteReason.RESIGNED for u in users)


async def test_list_users_status_all_returns_everyone_in_creation_order(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _seed(uow_factory)

    users = await admin.list_users.execute(status=UserStatusFilter.ALL)

    assert [u.login_id.value for u in users] == ["amy", "old1", "bob", "old2"]


async def test_resigned_rows_with_the_same_login_id_are_listed_separately(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    first = await seed_user(uow_factory, "kim", Role.SALES, resigned=True, now=later(1))
    second = await seed_user(uow_factory, "kim", Role.SALES, resigned=True, now=later(2))
    active = await seed_user(uow_factory, "kim", Role.SALES, now=later(3))

    users = await admin.list_users.execute(status=UserStatusFilter.ALL)

    assert [u.id for u in users] == [first.id, second.id, active.id]


async def test_status_all_applies_offset_and_limit(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _seed(uow_factory)

    page = await admin.list_users.execute(status=UserStatusFilter.ALL, offset=1, limit=2)

    assert [u.login_id.value for u in page] == ["old1", "bob"]


@pytest.mark.parametrize("status", list(UserStatusFilter))
@pytest.mark.parametrize(("offset", "limit"), [(-1, 10), (0, 0), (0, 201)])
async def test_list_users_rejects_out_of_range_paging_for_every_status(
    admin: AdminStack, status: UserStatusFilter, offset: int, limit: int
) -> None:
    with pytest.raises(InvalidValueError):
        await admin.list_users.execute(status=status, offset=offset, limit=limit)


def test_status_filter_values_match_the_api_query_values() -> None:
    assert {s.value for s in UserStatusFilter} == {"active", "resigned", "all"}
