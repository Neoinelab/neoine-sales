"""AC9: 사용자 목록의 상태 필터(active|resigned|all)와 퇴사 정보 (T23)."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.user.value_objects import UserStatusFilter
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
    """상태를 정하지 않으면 재직자만 보인다

    테스트 코드: US-023
    """
    # given: 재직 2명과 퇴사 2명
    await _seed(uow_factory)

    # when: 기본 조건으로 읽는다
    users = await admin.list_users.execute()

    # then: 재직자만 나온다
    assert [u.login_id.value for u in users] == ["amy", "bob"]


async def test_list_users_status_resigned_returns_only_resigned_users(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """상태 resigned는 퇴사자만 퇴사 시각과 함께 보인다

    테스트 코드: US-024
    """
    # given: 재직 2명과 퇴사 2명
    await _seed(uow_factory)

    # when: 상태 resigned로 읽는다
    users = await admin.list_users.execute(status=UserStatusFilter.RESIGNED)

    # then: 퇴사자만 나오고 모두 퇴사 시각이 있고 퇴사 사유 필드는 없다
    assert [u.login_id.value for u in users] == ["old1", "old2"]
    assert all(u.deleted_at is not None for u in users)
    assert not any(hasattr(u, "delete_reason") for u in users)


async def test_list_users_status_all_returns_everyone_in_creation_order(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """상태 all은 재직자와 퇴사자를 등록 순서로 모두 보인다

    테스트 코드: US-025
    """
    # given: 재직 2명과 퇴사 2명
    await _seed(uow_factory)

    # when: 상태 all로 읽는다
    users = await admin.list_users.execute(status=UserStatusFilter.ALL)

    # then: 네 명이 등록 순서대로 나온다
    assert [u.login_id.value for u in users] == ["amy", "old1", "bob", "old2"]


async def test_resigned_rows_with_the_same_login_id_are_listed_separately(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """같은 아이디의 행도 따로 보인다

    테스트 코드: US-025
    """
    # given: 같은 아이디의 퇴사 행 둘과 재직 행
    first = await seed_user(uow_factory, "kim", Role.SALES, resigned=True, now=later(1))
    second = await seed_user(uow_factory, "kim", Role.SALES, resigned=True, now=later(2))
    active = await seed_user(uow_factory, "kim", Role.SALES, now=later(3))

    # when: 상태 all로 읽는다
    users = await admin.list_users.execute(status=UserStatusFilter.ALL)

    # then: 세 행이 각각 나온다
    assert [u.id for u in users] == [first.id, second.id, active.id]


async def test_status_all_applies_offset_and_limit(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """모든 상태에서 offset·limit으로 한 페이지를 받는다

    테스트 코드: US-026
    """
    # given: 재직 2명과 퇴사 2명
    await _seed(uow_factory)

    # when: 상태 all에 offset 1, limit 2로 읽는다
    page = await admin.list_users.execute(status=UserStatusFilter.ALL, offset=1, limit=2)

    # then: 둘째와 셋째 행만 나온다
    assert [u.login_id.value for u in page] == ["old1", "bob"]


@pytest.mark.parametrize("status", list(UserStatusFilter))
@pytest.mark.parametrize(("offset", "limit"), [(-1, 10), (0, 0), (0, 201)])
async def test_list_users_rejects_out_of_range_paging_for_every_status(
    admin: AdminStack, status: UserStatusFilter, offset: int, limit: int
) -> None:
    """어떤 상태에서도 범위 밖 페이지 값은 입력 오류다

    테스트 코드: US-027
    """
    # when: 범위 밖 offset·limit으로 읽는다
    with pytest.raises(InvalidValueError):
        await admin.list_users.execute(status=status, offset=offset, limit=limit)
    # then: 입력 오류다


def test_status_filter_values_match_the_api_query_values() -> None:
    """상태 필터 값은 API 쿼리 값과 같다"""
    # when: 필터 값 집합을 읽는다
    actual = {s.value for s in UserStatusFilter}
    # then: active·resigned·all 세 값이다
    assert actual == {"active", "resigned", "all"}
