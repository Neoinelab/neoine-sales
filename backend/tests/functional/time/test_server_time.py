"""Feature: 화면은 서버 시각을 기준으로 한다.

서버는 자기 시각과 업무 날짜를 알려 주고(GET /api/v1/time), 모든 응답의 시각을 서버 OS 로컬
오프셋(Asia/Seoul이면 +09:00)으로 내보낸다. 순간은 바뀌지 않는다.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.dashboard import when_get_dashboard_summary
from tests.functional.steps.deal_risk import only_row
from tests.functional.steps.deals import given_deal, when_get_deal, when_list_deals
from tests.functional.steps.server_time import (
    given_server_clock_at_utc,
    then_carries_seoul_offset,
    then_instant_is_server_clock,
    when_get_server_time,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_logged_in_user_receives_server_time(api: Api, role: str) -> None:
    """Scenario: 로그인한 사용자는 서버 시각(+09:00)과 서버 업무 날짜를 받는다."""
    # Given: 서버 시계는 UTC 12월 31일 15시대 = 서울 새해 0시대
    await given_server_clock_at_utc(api, 2026, 12, 31, 15, 0)
    await given_logged_in_as(api, role=role)  # type: ignore[arg-type]
    # When
    response = await when_get_server_time(api)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert set(body) == {"now", "today"}
    then_carries_seoul_offset(body["now"])
    then_instant_is_server_clock(body["now"], api)
    assert body["now"] == api.clock.now().astimezone().isoformat()
    assert body["today"] == "2027-01-01"
    assert date.fromisoformat(body["now"][:10]) == date.fromisoformat(body["today"])


async def test_server_date_follows_server_timezone_not_utc(api: Api) -> None:
    """Scenario: UTC로는 아직 전날이어도 서버(서울) 날짜는 이미 다음 날이다."""
    # Given
    await given_server_clock_at_utc(api, 2026, 10, 22, 15, 0)
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get_server_time(api)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert api.clock.now().date() == date(2026, 10, 22)  # UTC 날짜
    assert body["today"] == "2026-10-23"
    assert datetime.fromisoformat(body["now"]).date() == date.fromisoformat(body["today"])


async def test_anonymous_cannot_read_server_time(api: Api) -> None:
    """Scenario: 로그인하지 않으면 서버 시각을 읽을 수 없다(401)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_get_server_time(api)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_deal_detail_timestamps_carry_server_offset(api: Api) -> None:
    """Scenario: Deal 상세의 시각은 서버 오프셋으로 오고 순간은 등록 시각과 같다."""
    # Given
    await given_server_clock_at_utc(api, 2026, 12, 31, 15, 0)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_get_deal(api, deal["code"])
    # Then
    then_status_is(response, 200)
    body = response.json()
    for field in ("created_at", "updated_at", "status_changed_at", "last_updated_at"):
        then_carries_seoul_offset(body[field])
        then_instant_is_server_clock(body[field], api)  # 등록 직후라 시계와 같다


async def test_deal_list_timestamps_carry_server_offset(api: Api) -> None:
    """Scenario: Deal 목록 행의 시각도 서버 오프셋이다."""
    # Given
    await given_server_clock_at_utc(api, 2026, 12, 31, 15, 0)
    await given_logged_in_as(api, role="sales")
    await given_deal(api)
    # When
    response = await when_list_deals(api)
    # Then
    then_status_is(response, 200)
    row = only_row(response)
    for field in ("created_at", "last_updated_at"):
        then_carries_seoul_offset(row[field])
        then_instant_is_server_clock(row[field], api)


async def test_dashboard_as_of_carries_server_offset(api: Api) -> None:
    """Scenario: Dashboard 요약의 as_of도 서버 오프셋이다."""
    # Given
    await given_server_clock_at_utc(api, 2026, 12, 31, 15, 0)
    await given_logged_in_as(api, role="user")
    # When
    response = await when_get_dashboard_summary(api, year=2026)
    # Then
    then_status_is(response, 200)
    body = response.json()
    then_carries_seoul_offset(body["as_of"])
    then_instant_is_server_clock(body["as_of"], api)
