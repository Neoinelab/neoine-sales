"""SearchDealActions와 DealActionQuery: 필터·정렬·검증(AC9)."""

from datetime import date, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.customer.register_customer import RegisterCustomer
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.register_deal import RegisterDeal
from app.application.deal_action.delete_deal_action import DeleteDealAction
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.deal_action.search_deal_actions import SearchDealActions
from app.application.ports.deal_action_repository import DealActionQuery, DealActionSort
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealInUseError, DealNotFoundError
from app.domain.deal.value_objects import DealId
from app.domain.deal_action.value_objects import ActionType
from tests.factories import NOW, make_customer_input, make_deal_action_input, make_deal_input

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FixedClock


@pytest.fixture
async def deal_id(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> DealId:
    customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
    deal = await RegisterDeal(uow_factory, clock).execute(make_deal_input(customer.id))
    return deal.id


@pytest.fixture
async def seeded(uow_factory: UnitOfWorkFactory, clock: FixedClock, deal_id: DealId) -> list[str]:
    """(유형, 진행내역, 다음 계획, 메모, 진행자, 진행 일차, 계획일)"""
    register = RegisterDealAction(uow_factory, clock)
    rows = [
        (
            ActionType.CALL,
            "첫 통화",
            "견적서 준비",
            "예산 문의 100%",
            "김영업",
            0,
            date(2026, 2, 10),
        ),
        (
            ActionType.MEETING,
            "킥오프 미팅",
            "요구사항 정리",
            "일정 협의",
            "박영업",
            1,
            date(2026, 2, 1),
        ),
        (ActionType.EMAIL, "제안서 발송", "회신 확인", "견적 첨부", "박영업", 2, date(2026, 2, 10)),
        (
            ActionType.MEETING,
            "최종 미팅",
            "계약서 초안",
            "조건 협의",
            "김영업",
            3,
            date(2026, 3, 1),
        ),
    ]
    for action_type, action, next_action, memo, actor, day, due in rows:
        await register.execute(
            deal_id,
            make_deal_action_input(
                action_type=action_type,
                action=action,
                next_action=next_action,
                memo=memo,
                actor=actor,
                acted_at=NOW + timedelta(days=day),
                due_date=due,
            ),
        )
    return [row[1] for row in rows]


async def _names(uow_factory: UnitOfWorkFactory, **criteria: object) -> list[str]:
    found = await SearchDealActions(uow_factory).execute(DealActionQuery(**criteria))  # type: ignore[arg-type]
    return [a.details.action for a in found]


async def test_default_order_is_latest_activity_first(
    uow_factory: UnitOfWorkFactory, seeded: list[str]
) -> None:
    assert await _names(uow_factory) == list(reversed(seeded))


async def test_filters_combine_with_and(uow_factory: UnitOfWorkFactory, seeded: list[str]) -> None:
    assert await _names(uow_factory, action_type=ActionType.MEETING) == ["최종 미팅", "킥오프 미팅"]
    assert await _names(uow_factory, action_type=ActionType.MEETING, actor="박영업") == [
        "킥오프 미팅"
    ]


async def test_keyword_matches_action_next_action_and_memo_ignoring_case(
    uow_factory: UnitOfWorkFactory, seeded: list[str]
) -> None:
    assert await _names(uow_factory, keyword="킥오프") == ["킥오프 미팅"]  # action
    assert await _names(uow_factory, keyword="계약서") == ["최종 미팅"]  # next_action
    assert await _names(uow_factory, keyword="첨부") == ["제안서 발송"]  # memo


async def test_keyword_matches_across_next_action_and_memo_of_different_rows(
    uow_factory: UnitOfWorkFactory, seeded: list[str]
) -> None:
    """'견적'은 첫 통화의 next_action과 제안서 발송의 memo 두 곳에 있다."""
    assert await _names(uow_factory, keyword="견적") == ["제안서 발송", "첫 통화"]


async def test_keyword_treats_wildcards_literally(
    uow_factory: UnitOfWorkFactory, seeded: list[str]
) -> None:
    assert await _names(uow_factory, keyword="100%") == ["첫 통화"]
    assert await _names(uow_factory, keyword="%") == ["첫 통화"]
    assert await _names(uow_factory, keyword="_") == []


async def test_due_range_is_inclusive_on_both_ends(
    uow_factory: UnitOfWorkFactory, seeded: list[str]
) -> None:
    names = await _names(uow_factory, due_from=date(2026, 2, 1), due_to=date(2026, 2, 10))

    assert names == ["제안서 발송", "킥오프 미팅", "첫 통화"]


async def test_due_from_alone_and_due_to_alone(
    uow_factory: UnitOfWorkFactory, seeded: list[str]
) -> None:
    assert await _names(uow_factory, due_from=date(2026, 2, 11)) == ["최종 미팅"]
    assert await _names(uow_factory, due_to=date(2026, 1, 31)) == []


async def test_sort_by_due_date_ascending_breaks_ties_by_latest_activity(
    uow_factory: UnitOfWorkFactory, seeded: list[str]
) -> None:
    names = await _names(uow_factory, sort=DealActionSort.DUE_DATE_ASC)

    assert names == ["킥오프 미팅", "제안서 발송", "첫 통화", "최종 미팅"]


async def test_sort_by_due_date_descending_breaks_ties_by_latest_activity(
    uow_factory: UnitOfWorkFactory, seeded: list[str]
) -> None:
    names = await _names(uow_factory, sort=DealActionSort.DUE_DATE_DESC)

    assert names == ["최종 미팅", "제안서 발송", "첫 통화", "킥오프 미팅"]


def test_sort_values_are_the_api_names() -> None:
    assert {s.value for s in DealActionSort} == {
        "acted_at_desc",
        "due_date_asc",
        "due_date_desc",
    }
    assert DealActionQuery().sort is DealActionSort.ACTED_AT_DESC


async def test_period_is_inclusive_from_and_exclusive_to(
    uow_factory: UnitOfWorkFactory, seeded: list[str]
) -> None:
    names = await _names(
        uow_factory, acted_from=NOW + timedelta(days=1), acted_to=NOW + timedelta(days=3)
    )

    assert names == ["제안서 발송", "킥오프 미팅"]


async def test_paging(uow_factory: UnitOfWorkFactory, seeded: list[str]) -> None:
    assert await _names(uow_factory, offset=1, limit=2) == ["제안서 발송", "킥오프 미팅"]


async def test_filter_by_deal_requires_an_existing_deal(
    uow_factory: UnitOfWorkFactory, seeded: list[str], deal_id: DealId
) -> None:
    assert len(await _names(uow_factory, deal_id=deal_id)) == len(seeded)
    with pytest.raises(DealNotFoundError):
        await _names(uow_factory, deal_id=DealId(uuid4()))


async def test_history_of_a_deal_with_actions_stays_searchable_because_it_cannot_be_deleted(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, seeded: list[str], deal_id: DealId
) -> None:
    with pytest.raises(DealInUseError):
        await DeleteDeal(uow_factory, clock).execute(deal_id)

    assert len(await _names(uow_factory, deal_id=deal_id)) == len(seeded)


async def test_deleted_actions_are_excluded(
    uow_factory: UnitOfWorkFactory, clock: FixedClock, seeded: list[str]
) -> None:
    found = await SearchDealActions(uow_factory).execute(DealActionQuery(keyword="첨부"))
    await DeleteDealAction(uow_factory, clock).execute(found[0].id)

    assert await _names(uow_factory, keyword="첨부") == []


@pytest.mark.parametrize(
    "criteria",
    [
        {"limit": 0},
        {"offset": -1},
        {"acted_from": NOW, "acted_to": NOW},
        {"acted_from": NOW.replace(tzinfo=None)},
        {"keyword": "가" * 101},
        {"due_from": date(2026, 3, 2), "due_to": date(2026, 3, 1)},
        {"due_from": NOW},  # datetime은 날짜가 아니다
        {"due_to": NOW},
    ],
)
async def test_invalid_criteria_raise_invalid_value(
    uow_factory: UnitOfWorkFactory, criteria: dict[str, object]
) -> None:
    with pytest.raises(InvalidValueError):
        await _names(uow_factory, **criteria)


def test_query_accepts_equal_due_bounds() -> None:
    query = DealActionQuery(due_from=date(2026, 3, 1), due_to=date(2026, 3, 1))

    assert query.due_from == query.due_to
