"""Feature: 영업은 Deal 목록을 "최종 업데이트" 기간(updated_from/to)으로 좁힌다.

최종 업데이트는 모든 Action 중 가장 최근 수행 시각(없으면 Deal 등록 시각)이고 Deal 수정은
반영하지 않는다. 날짜는 서버 OS 로컬 업무 날짜이고 양끝을 포함한다. 연/분기는 계속 Expected
Close 기준이다. 서버는 프리셋(최근 2주·1/2/3/6개월)을 오늘 기준 날짜 범위로 풀어 준다.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import given_action
from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_lists import then_codes_are, then_codes_are_exactly, then_total_is
from tests.functional.steps.deal_risk import (
    given_clock_at_local_noon,
    given_days_pass,
)
from tests.functional.steps.deals import (
    given_clock_at,
    given_deal,
    when_list_deals,
    when_update_deal,
)
from tests.functional.steps.updated_period import (
    days_from_today,
    then_period_starts_are,
    then_periods_follow_the_server_date,
    when_list_updated_periods,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def test_only_deals_updated_within_the_period_are_listed(api: Api) -> None:
    """Scenario: 30일 전에 등록하고 손대지 않은 Deal은 최근 2주 기간에서 빠진다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    await given_deal(api, name="오래된 딜")
    await given_days_pass(api, 30, login_id=login_id)
    recent = await given_deal(api, name="새 딜")
    # When
    response = await when_list_deals(api, updated_from=days_from_today(api, -14))
    # Then
    then_codes_are(response, [recent["code"]])
    then_total_is(response, 1)


async def test_a_new_action_brings_an_old_deal_into_the_period(api: Api) -> None:
    """Scenario: 오래된 Deal에 Action을 남기면 그 Action 날짜로 기간에 들어온다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    old = await given_deal(api, name="오래된 딜")
    await given_days_pass(api, 30, login_id=login_id)
    recent = await given_deal(api, name="새 딜")
    await given_action(api, old["code"])
    # When
    response = await when_list_deals(api, updated_from=days_from_today(api, -14))
    # Then
    then_codes_are_exactly(response, [old["code"], recent["code"]])
    then_total_is(response, 2)


async def test_editing_a_deal_does_not_move_it_into_the_period(api: Api) -> None:
    """Scenario: 오래된 Deal을 수정해도 최종 업데이트가 아니므로 기간에 들어오지 않는다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_days_pass(api, 30, login_id=login_id)
    await when_update_deal(api, deal["code"], revenue_amount=200_000_000)
    # When
    response = await when_list_deals(api, updated_from=days_from_today(api, -14))
    # Then
    then_codes_are(response, [])
    then_total_is(response, 0)


@pytest.mark.parametrize(
    ("start", "end", "expected_total"),
    [
        (0, 0, 1),  # 오늘 하루: 양끝 포함
        (1, None, 0),  # 시작이 내일이면 제외
        (None, -1, 0),  # 끝이 어제면 제외
        (-3, None, 1),  # 한쪽만: 그 날 이후 전체
        (None, 3, 1),  # 한쪽만: 그 날 이전 전체
    ],
)
async def test_both_ends_of_the_period_are_inclusive(
    api: Api, start: int | None, end: int | None, expected_total: int
) -> None:
    """Scenario: 오늘 등록한 Deal은 시작·끝 날짜가 오늘이면 포함되고 하루 벗어나면 제외된다."""
    # Given
    await given_clock_at_local_noon(api)
    await given_logged_in_as(api, role="sales")
    await given_deal(api)
    params = {}
    if start is not None:
        params["updated_from"] = days_from_today(api, start)
    if end is not None:
        params["updated_to"] = days_from_today(api, end)
    # When
    response = await when_list_deals(api, **params)
    # Then
    then_total_is(response, expected_total)


@pytest.mark.parametrize(
    ("moment", "included"),
    [
        (datetime(2026, 6, 30, 23, 59, 59), True),  # 끝 날짜의 마지막 1초
        (datetime(2026, 7, 1, 0, 0, 0), False),  # 끝 날짜 다음 날 00:00:00
        (datetime(2026, 6, 1, 0, 0, 0), True),  # 시작 날짜 00:00:00
        (datetime(2026, 5, 31, 23, 59, 59), False),  # 시작 날짜 전날의 마지막 1초
    ],
)
async def test_the_period_boundaries_follow_the_server_local_midnight(
    api: Api, moment: datetime, included: bool
) -> None:
    """Scenario: 판정은 서버 로컬 자정 경계다(23:59:59는 그 날, 00:00:00은 다음 날)."""
    # Given
    await given_clock_at(api, moment.astimezone())
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_list_deals(api, updated_from="2026-06-01", updated_to="2026-06-30")
    # Then
    then_codes_are(response, [deal["code"]] if included else [])


async def test_updated_period_and_year_quarter_are_combined(api: Api) -> None:
    """Scenario: 최종 업데이트 기간과 연/분기(Expected Close)는 AND로 결합한다."""
    # Given
    await given_clock_at_local_noon(api)
    await given_logged_in_as(api, role="sales")
    q2 = await given_deal(api, revenue_date="2026-05-20")
    await given_deal(api, revenue_date="2026-08-20")
    # When
    response = await when_list_deals(
        api, year=2026, quarter=2, updated_from=days_from_today(api, 0)
    )
    # Then
    then_codes_are(response, [q2["code"]])
    then_total_is(response, 1)


@pytest.mark.parametrize("role", ["user", "sales", "admin"])
async def test_presets_are_resolved_from_the_server_date(api: Api, role: str) -> None:
    """Scenario: 로그인한 누구나 서버 오늘 날짜 기준 프리셋 5개를 받는다(역할 무관)."""
    # Given
    await given_clock_at_local_noon(api)
    await given_logged_in_as(api, role=role)  # type: ignore[arg-type]
    # When
    response = await when_list_updated_periods(api)
    # Then
    then_periods_follow_the_server_date(response)


async def test_presets_fall_back_to_the_month_end(api: Api) -> None:
    """Scenario: 3월 31일의 최근 1개월은 2월 28일부터이고 6개월은 전년 9월 30일부터다."""
    # Given
    await given_clock_at(api, datetime(2026, 3, 31, 12, 0).astimezone())
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_updated_periods(api)
    # Then
    then_period_starts_are(
        response,
        {"2w": date(2026, 3, 17), "1m": date(2026, 2, 28), "6m": date(2025, 9, 30)},
    )


async def test_presets_follow_the_server_clock_after_midnight(api: Api) -> None:
    """Scenario: 자정이 지나 다시 조회하면 프리셋의 today도 다음 날로 바뀐다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    await given_days_pass(api, 1, login_id=login_id)
    # When
    response = await when_list_updated_periods(api)
    # Then
    then_periods_follow_the_server_date(response)


async def test_presets_require_login(api: Api) -> None:
    """Scenario: 로그인하지 않으면 프리셋을 받을 수 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_logged_out(api)
    # When
    response = await when_list_updated_periods(api)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_a_period_that_starts_after_it_ends_is_rejected(api: Api) -> None:
    """Scenario: 최종 업데이트 시작일이 종료일보다 늦으면 422(invalid-value)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, updated_from="2026-07-01", updated_to="2026-06-30")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


@pytest.mark.parametrize("field", ["updated_from", "updated_to"])
@pytest.mark.parametrize("day", ["1899-12-31", "3000-01-01", "0001-01-01", "9999-12-31"])
async def test_an_updated_date_outside_1900_2999_is_rejected_not_a_server_error(
    api: Api, field: str, day: str
) -> None:
    """Scenario: 허용 범위(1900~2999) 밖의 날짜는 500이 아니라 422(invalid-value)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, **{field: day})
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


@pytest.mark.parametrize("field", ["updated_from", "updated_to"])
@pytest.mark.parametrize("day", ["1900-01-01", "2999-12-31"])
async def test_an_updated_date_at_the_range_edges_is_accepted(
    api: Api, field: str, day: str
) -> None:
    """Scenario: 허용 범위의 양 끝 날짜는 조회된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, **{field: day})
    # Then
    then_status_is(response, 200)
