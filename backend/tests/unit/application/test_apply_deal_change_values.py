"""ApplyDealChange의 금액·Expected Close 단일 변경(AC-19·21): 검증 문구, 이력, 잠금 없음."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError
from tests.factories_deal import make_draft
from tests.support.expect import raises_with
from tests.unit.application.apply_helpers import apply_change

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

AMOUNT_MESSAGE = "매출금액은 1원 이상의 정수로 입력하세요."


async def test_changing_the_amount_saves_it_and_logs_the_formatted_amounts(env: DealEnv) -> None:
    view = await env.new_deal()

    result = await apply_change(env, view, "revenue_amount", 1_870_000_000)

    assert result.view.item.deal.details.revenue_amount.value == 1_870_000_000
    assert (result.co_changed, result.notice) == ((), None)
    assert await env.changes(view) == [("amount", "금액(단위:천원)", "150,000", "1,870,000")]


@pytest.mark.parametrize("amount", [0, -1, 2**53])
async def test_an_invalid_amount_is_rejected_and_nothing_changes(env: DealEnv, amount: int) -> None:
    view = await env.new_deal()

    with raises_with(InvalidValueError, AMOUNT_MESSAGE):
        await apply_change(env, view, "revenue_amount", amount)

    assert (await env.uow.deals.get(view.item.deal.id)).details.revenue_amount.value == 150_000_000
    assert await env.changes(view) == []


@pytest.mark.parametrize("amount", [1, 2**53 - 1])
async def test_the_amount_boundaries_are_accepted(env: DealEnv, amount: int) -> None:
    view = await env.new_deal()

    result = await apply_change(env, view, "revenue_amount", amount)

    assert result.view.item.deal.details.revenue_amount.value == amount


async def test_changing_the_expected_close_saves_it_and_logs_the_dates(env: DealEnv) -> None:
    view = await env.new_deal()

    result = await apply_change(env, view, "revenue_date", date(2026, 12, 31))

    assert result.view.item.deal.details.revenue_date == date(2026, 12, 31)
    assert await env.changes(view) == [
        ("expectedClose", "Expected Close", "2026-06-30", "2026-12-31")
    ]


async def test_the_same_amount_changes_nothing(env: DealEnv) -> None:
    view = await env.new_deal()
    env.clock.advance(600)

    await apply_change(env, view, "revenue_amount", 150_000_000)

    assert await env.changes(view) == []
    assert (await env.uow.deals.get(view.item.deal.id)).updated_at == view.item.deal.updated_at


async def test_a_closed_deal_can_change_its_amount_and_date(env: DealEnv) -> None:
    view = await env.new_deal(status_key="contract_completed", forecast_key="won")

    await apply_change(env, view, "revenue_amount", 5)
    result = await apply_change(env, view, "revenue_date", date(2027, 1, 1))

    details = result.view.item.deal.details
    assert (details.revenue_amount.value, details.revenue_date) == (5, date(2027, 1, 1))
    assert result.view.item.deal.sync.forecast_key == "won"


async def test_a_change_does_not_move_the_deal_in_the_list(env: DealEnv) -> None:
    older = await env.new_deal()
    await env.new_deal()
    before = [v.item.deal.id for v in (await env.list.execute(DealQuery())).items]
    env.clock.advance(60)

    await apply_change(env, older, "revenue_amount", 10)

    page = await env.list.execute(DealQuery())
    assert [v.item.deal.id for v in page.items] == before  # 최종 업데이트는 Action 기준(E4)
    edited = next(v for v in page.items if v.item.deal.id == older.item.deal.id)
    assert edited.item.last_updated_at == older.item.deal.created_at
    assert edited.item.deal.details.revenue_amount.value == 10


async def test_changes_read_contacts_in_bulk_not_one_by_one(env: DealEnv) -> None:
    view = await env.new_deal(
        customer=make_draft(company="한빛은행", name="정민수"),
        partner=make_draft(company="코어테크", name="민지훈"),
    )
    env.uow.contacts.round_trips = 0

    await apply_change(env, view, "revenue_amount", 10)

    assert env.uow.contacts.round_trips <= 2  # 이름 조회 한 번 + 응답 조립 한 번
