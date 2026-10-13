"""DealActionRepository 계약(저장·삭제·존재): Fake와 SQL(PostgreSQL)에 같은 테스트를 적용한다."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_action_repository import DealActionQuery
from app.domain.common.errors import AlreadyExistsError
from app.domain.deal_action.errors import DealActionNotFoundError
from tests.factories import later, make_deal_action, make_deal_action_details

if TYPE_CHECKING:
    from tests.contracts.deal_action_case import Case


async def test_add_then_get_round_trips_every_field(action_case: Case) -> None:
    action = make_deal_action(
        later(5),
        action="제안 발표",
        next_action="견적 회신",
        due_date=date(2026, 2, 3),
        memo="내용",
    )
    await action_case.add(action)

    stored = await action_case.repository.get(action.id)

    assert stored == action
    assert stored.details == action.details
    assert stored.details.due_date == date(2026, 2, 3)
    assert stored.created_at == action.created_at


async def test_null_next_action_and_due_date_load_as_none(action_case: Case) -> None:
    legacy = await action_case.add_legacy()

    stored = await action_case.repository.get(legacy.id)

    assert stored.details.next_action is None
    assert stored.details.due_date is None
    assert [a.id for a in await action_case.repository.search(DealActionQuery())] == [legacy.id]


async def test_add_with_an_existing_id_raises_already_exists(action_case: Case) -> None:
    action = make_deal_action()
    await action_case.add(action)

    with pytest.raises(AlreadyExistsError):
        await action_case.repository.add(action)


async def test_get_unknown_action_raises_not_found(action_case: Case) -> None:
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.get(make_deal_action().id)


async def test_update_persists_new_fields(action_case: Case) -> None:
    action = make_deal_action()
    await action_case.add(action)
    action.update(
        make_deal_action_details(
            deal_id=action.details.deal_id,
            action="변경",
            next_action="다음",
            due_date=date(2026, 5, 5),
            memo="c",
        ),
        later(10),
    )

    await action_case.repository.update(action)

    stored = await action_case.repository.get(action.id)
    assert stored.details.action == "변경"
    assert stored.details.next_action == "다음"
    assert stored.details.due_date == date(2026, 5, 5)
    assert stored.details.memo == "c"
    assert stored.updated_at == later(10)


async def test_update_unknown_action_raises_not_found(action_case: Case) -> None:
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.update(make_deal_action())


async def test_delete_removes_the_row_physically(action_case: Case) -> None:
    action = make_deal_action()
    await action_case.add(action)

    await action_case.repository.delete(action.id)

    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.get(action.id)
    assert await action_case.search() == []
    assert not await action_case.repository.exists_for_deal(action.details.deal_id)


async def test_delete_unknown_raises_not_found(action_case: Case) -> None:
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.delete(make_deal_action().id)


async def test_exists_for_deal_is_true_only_for_the_deal_that_has_rows(action_case: Case) -> None:
    action = make_deal_action()
    await action_case.add(action)

    assert await action_case.repository.exists_for_deal(action.details.deal_id)
    assert not await action_case.repository.exists_for_deal(make_deal_action().details.deal_id)
