"""ApplyDealChange의 금액·Expected Close 단일 변경: 검증 문구, 이력, 잠금 없음."""

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
    """금액을 바꾸면 저장되고 이력에 원 콤마 숫자로 남는다.

    테스트 코드: DD-027
    """
    # given: 금액 150,000,000원 Deal
    view = await env.new_deal()

    # when: 금액을 1,870,000,000으로 바꾼다
    result = await apply_change(env, view, "revenue_amount", 1_870_000_000)

    # then: 새 금액이 저장되고 함께 바뀐 값·알림 없이 '금액(단위:원)' 이력이 콤마 숫자로 남는다
    assert result.view.item.deal.details.revenue_amount.value == 1_870_000_000
    assert (result.co_changed, result.notice) == ((), None)
    assert await env.changes(view) == [("amount", "금액(단위:원)", "150,000,000", "1,870,000,000")]


@pytest.mark.parametrize("amount", [0, -1, 2**53])
async def test_an_invalid_amount_is_rejected_and_nothing_changes(env: DealEnv, amount: int) -> None:
    """금액 0·-1·2^53은 거절되고 금액·이력이 그대로다.

    테스트 코드: DD-028
    """
    # given: 금액 150,000,000원 Deal
    view = await env.new_deal()

    # when: 범위 밖 금액으로 바꾼다
    with raises_with(InvalidValueError, AMOUNT_MESSAGE):
        await apply_change(env, view, "revenue_amount", amount)

    # then: '1원 이상의 정수' 오류이고 금액·이력이 그대로다
    assert (await env.uow.deals.get(view.item.deal.id)).details.revenue_amount.value == 150_000_000
    assert await env.changes(view) == []


@pytest.mark.parametrize("amount", [1, 2**53 - 1])
async def test_the_amount_boundaries_are_accepted(env: DealEnv, amount: int) -> None:
    """금액 1과 2^53-1은 저장된다.

    테스트 코드: DD-028
    """
    # given: 금액 150,000,000원 Deal
    view = await env.new_deal()

    # when: 경계 금액으로 바꾼다
    result = await apply_change(env, view, "revenue_amount", amount)

    # then: 응답 Deal의 금액이 그 값이다
    assert result.view.item.deal.details.revenue_amount.value == amount


async def test_changing_the_expected_close_saves_it_and_logs_the_dates(env: DealEnv) -> None:
    """Expected Close를 바꾸면 저장되고 이력에 YYYY-MM-DD로 남는다.

    테스트 코드: DD-029
    """
    # given: Expected Close 2026-06-30 Deal
    view = await env.new_deal()

    # when: 2026-12-31로 바꾼다
    result = await apply_change(env, view, "revenue_date", date(2026, 12, 31))

    # then: 새 날짜가 저장되고 'Expected Close' 이력이 ISO 날짜로 남는다
    assert result.view.item.deal.details.revenue_date == date(2026, 12, 31)
    assert await env.changes(view) == [
        ("expectedClose", "Expected Close", "2026-06-30", "2026-12-31")
    ]


async def test_the_same_amount_changes_nothing(env: DealEnv) -> None:
    """같은 금액으로 바꾸면 이력도 수정 시각 변경도 없다.

    테스트 코드: DD-023
    """
    # given: 금액 150,000,000원 Deal이고 시간이 600초 지났다
    view = await env.new_deal()
    env.clock.advance(600)

    # when: 같은 금액으로 바꾼다
    await apply_change(env, view, "revenue_amount", 150_000_000)

    # then: 이력이 없고 수정 시각이 그대로다
    assert await env.changes(view) == []
    assert (await env.uow.deals.get(view.item.deal.id)).updated_at == view.item.deal.updated_at


async def test_a_closed_deal_can_change_its_amount_and_date(env: DealEnv) -> None:
    """종결된 Deal도 금액·Expected Close를 하나씩 바꿀 수 있고 Status·Forecast는 그대로다.

    테스트 코드: DD-030
    """
    # given: 계약완료·Won Deal
    view = await env.new_deal(status_key="contract_completed", forecast_key="won")

    # when: 금액을 5로, 이어서 Expected Close를 2027-01-01로 바꾼다
    await apply_change(env, view, "revenue_amount", 5)
    # then: 금액·날짜가 바뀌고 Forecast는 Won 그대로다
    result = await apply_change(env, view, "revenue_date", date(2027, 1, 1))

    details = result.view.item.deal.details
    assert (details.revenue_amount.value, details.revenue_date) == (5, date(2027, 1, 1))
    assert result.view.item.deal.sync.forecast_key == "won"


async def test_a_change_does_not_move_the_deal_in_the_list(env: DealEnv) -> None:
    """값을 바꿔도 목록 순서가 바뀌지 않고 최종 업데이트는 Action 기준 그대로다."""
    # given: Deal 두 건과 목록 순서
    older = await env.new_deal()
    await env.new_deal()
    before = [v.item.deal.id for v in (await env.list.execute(DealQuery())).items]
    env.clock.advance(60)

    # when: 오래된 Deal의 금액을 바꾼다
    await apply_change(env, older, "revenue_amount", 10)

    # then: 목록 순서와 최종 업데이트가 그대로이고 금액만 바뀐다
    page = await env.list.execute(DealQuery())
    assert [v.item.deal.id for v in page.items] == before  # 최종 업데이트는 Action 기준(E4)
    edited = next(v for v in page.items if v.item.deal.id == older.item.deal.id)
    assert edited.item.last_updated_on == older.item.deal.created_at.astimezone().date()
    assert edited.item.deal.details.revenue_amount.value == 10


async def test_changes_read_contacts_in_bulk_not_one_by_one(env: DealEnv) -> None:
    """변경 한 번에 연락처를 건건이 읽지 않고 묶어서 읽는다."""
    # given: 고객·파트너가 있는 Deal이고 연락처 왕복 횟수를 0으로 비웠다
    view = await env.new_deal(
        customer=make_draft(company="한빛은행", name="정민수"),
        partner=make_draft(company="코어테크", name="민지훈"),
    )
    env.uow.contacts.round_trips = 0

    # when: 금액을 바꾼다
    await apply_change(env, view, "revenue_amount", 10)

    # then: 연락처 읽기 왕복이 2회 이하다
    assert env.uow.contacts.round_trips <= 2  # 이름 조회 한 번 + 응답 조립 한 번


async def test_a_single_change_succeeds_on_a_legacy_deal_whose_product_is_empty(
    env: DealEnv,
) -> None:
    """Product가 빈 레거시 Deal도 금액을 단일 변경할 수 있다.

    테스트 코드: DD-027
    """
    # given: 마이그레이션이 Product를 빈 값으로 채운 레거시 Deal
    view = await env.new_deal()
    stored = await env.uow.deals.get(view.item.deal.id)
    object.__setattr__(stored.details, "product", "")

    # when: 금액을 바꾼다
    result = await apply_change(env, view, "revenue_amount", 1_870_000_000)

    # then: 저장되고 금액 이력 한 건만 남는다
    assert result.view.item.deal.details.revenue_amount.value == 1_870_000_000
    assert await env.changes(view) == [("amount", "금액(단위:원)", "150,000,000", "1,870,000,000")]
