"""Feature: 영업은 목록을 기한초과·미업데이트 Deal로 좁혀 본다.

판정은 Deal의 Risk 표시와 같다. 가장 최근 Next Action의 Due가 오늘보다 앞이면 기한초과, 마지막
갱신 후 경고 기준(여기서는 7일) 이상 지났으면 미업데이트, Won·Lost Deal은 어느 쪽에도 걸리지
않는다. 둘을 함께 켜면 어느 하나라도 해당하는 Deal, 다른 조건과는 AND이고 total은 필터 결과다.
오늘은 서버 시계를 서버 로컬 시간대로 바꾼 달력 날짜이고, 서버 시계가 움직이면 세션이 만료되므로
같은 사용자로 다시 로그인한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_list_risk import (
    given_deals_with_every_risk,
    then_every_row_has_risk_in,
)
from tests.functional.steps.deal_lists import then_codes_are_exactly, then_total_is
from tests.functional.steps.deals import when_list_deals

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def test_listing_only_overdue_deals(api: Api) -> None:
    """Scenario: overdue만 켜면 기한초과 Deal(기한초과만, 둘 다)만 보이고 Lost는 빠진다."""
    # Given
    codes = await given_deals_with_every_risk(api)
    # When
    response = await when_list_deals(api, overdue="true")
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [codes["both"], codes["overdue_only"]])
    then_total_is(response, 2)
    then_every_row_has_risk_in(response, {"overdue", "overdue_stale"})


async def test_listing_only_stale_deals(api: Api) -> None:
    """Scenario: stale만 켜면 미업데이트 Deal(미업데이트만, 둘 다)만 보인다."""
    # Given
    codes = await given_deals_with_every_risk(api)
    # When
    response = await when_list_deals(api, stale="true")
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [codes["stale_only"], codes["both"]])
    then_total_is(response, 2)
    then_every_row_has_risk_in(response, {"stale", "overdue_stale"})


async def test_listing_overdue_or_stale_deals_together(api: Api) -> None:
    """Scenario: 둘 다 켜면 어느 하나라도 해당하는 Deal이 보인다."""
    # Given
    codes = await given_deals_with_every_risk(api)
    # When
    response = await when_list_deals(api, overdue="true", stale="true")
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [codes["stale_only"], codes["both"], codes["overdue_only"]])
    then_total_is(response, 3)


async def test_a_risk_filter_is_combined_with_other_conditions_using_and(api: Api) -> None:
    """Scenario: 위험 필터와 검색어는 AND이고 total도 그 결과다."""
    # Given
    codes = await given_deals_with_every_risk(api)
    # When
    response = await when_list_deals(api, stale="true", keyword=codes["both"])
    # Then
    then_status_is(response, 200)
    then_codes_are_exactly(response, [codes["both"]])
    then_total_is(response, 1)


async def test_a_non_boolean_risk_filter_is_rejected(api: Api) -> None:
    """Scenario: overdue에 bool이 아닌 값을 주면 request-validation 422이다."""
    # Given
    await given_deals_with_every_risk(api)
    # When
    response = await when_list_deals(api, overdue="abc")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
