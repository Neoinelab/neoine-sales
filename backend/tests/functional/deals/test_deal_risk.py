"""Feature: Deal Risk 표시(기한초과, 미업데이트, 종결 제외, 경고 기준 즉시 반영).

오늘은 서버 시계를 서버 로컬 시간대로 바꾼 달력 날짜다. 가장 최근 Action의 Due Date가 오늘보다
이전이면 기한초과(`overdue`), 마지막 갱신으로부터 경고 기준(기본 14일) 이상 지나면 미업데이트
(`stale`)이고 둘 다면 `overdue_stale`이다. Won·Lost Deal은 Risk가 없다. 시계는 시나리오가 움직이고,
서버 시계가 움직이면 세션이 만료되므로 같은 사용자로 다시 로그인한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import given_action
from tests.functional.steps.alerts import when_update_alert_settings
from tests.functional.steps.auth import ADMIN_LOGIN, given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deal_changes import CLOSING, when_change_deal
from tests.functional.steps.deal_risk import (
    given_clock_at_local_noon,
    given_days_pass,
    given_due_in,
    only_row,
    then_risk_is,
)
from tests.functional.steps.deals import (
    given_deal,
    when_get_deal,
    when_list_deals,
    when_update_deal,
)
from tests.functional.steps.users import log_in

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def _sales_with_deal_and_action_due_in(api: Api, days: int) -> tuple[str, str]:
    """영업 담당자가 Deal과 Due Date가 오늘+days일인 Action을 남겼다. (아이디, Deal code)"""
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_action(api, deal["code"], due_date=given_due_in(api, days))
    return login_id, str(deal["code"])


@pytest.mark.parametrize("view", ["list", "detail"])
async def test_a_deal_whose_next_action_due_has_passed_is_overdue(api: Api, view: str) -> None:
    """Scenario: Due Date가 지난 Action이 마지막이면 목록과 상세 모두 기한초과다."""
    # Given
    login_id, code = await _sales_with_deal_and_action_due_in(api, days=1)
    await given_days_pass(api, 2, login_id=login_id)
    # When
    response = await when_list_deals(api) if view == "list" else await when_get_deal(api, code)
    # Then
    then_status_is(response, 200)
    body = only_row(response) if view == "list" else response.json()
    then_risk_is(body, "overdue")


async def test_a_deal_due_today_is_not_overdue(api: Api) -> None:
    """Scenario: Due Date가 오늘이면 기한초과가 아니다."""
    # Given
    login_id, code = await _sales_with_deal_and_action_due_in(api, days=1)
    await given_days_pass(api, 1, login_id=login_id)
    # When
    response = await when_get_deal(api, code)
    # Then
    then_status_is(response, 200)
    then_risk_is(response.json(), None)


@pytest.mark.parametrize(("days", "risk"), [(13, None), (14, "stale")])
async def test_a_deal_untouched_for_stale_days_becomes_stale(
    api: Api, days: int, risk: str | None
) -> None:
    """Scenario: 14일째부터 미업데이트이고 13일째까지는 아니다(기본 경고 기준 14일)."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    await given_deal(api)
    await given_days_pass(api, days, login_id=login_id)
    # When
    response = await when_list_deals(api)
    # Then
    then_status_is(response, 200)
    then_risk_is(only_row(response), risk)


async def test_overdue_and_untouched_deal_is_overdue_stale(api: Api) -> None:
    """Scenario: 기한이 지나고 오래 갱신하지 않았으면 두 경고를 함께 보여준다."""
    # Given
    login_id, code = await _sales_with_deal_and_action_due_in(api, days=1)
    await given_days_pass(api, 20, login_id=login_id)
    # When
    response = await when_get_deal(api, code)
    # Then
    then_status_is(response, 200)
    then_risk_is(response.json(), "overdue_stale")


async def test_a_won_deal_never_shows_risk(api: Api) -> None:
    """Scenario: Won으로 종결된 Deal은 기한이 지나고 오래돼도 Risk가 없다."""
    # Given
    login_id, code = await _sales_with_deal_and_action_due_in(api, days=0)
    closed = await when_change_deal(api, code, "forecast_key", "won", CLOSING)
    then_status_is(closed, 200)
    await given_days_pass(api, 60, login_id=login_id)
    # When
    response = await when_list_deals(api)
    # Then
    then_status_is(response, 200)
    then_risk_is(only_row(response), None)


async def test_a_lost_deal_never_shows_risk(api: Api) -> None:
    """Scenario: Lost로 종결된 Deal은 기한이 지나고 오래돼도 Risk가 없다."""
    # Given
    login_id, code = await _sales_with_deal_and_action_due_in(api, days=0)
    closed = await when_update_deal(api, code, forecast_key="lost")
    then_status_is(closed, 200)
    await given_days_pass(api, 60, login_id=login_id)
    # When
    response = await when_get_deal(api, code)
    # Then
    then_status_is(response, 200)
    then_risk_is(response.json(), None)


async def test_admin_threshold_change_applies_immediately(api: Api) -> None:
    """Scenario: admin이 경고 기준을 7일로 줄이면 8일 지난 Deal이 곧바로 미업데이트가 된다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    await given_deal(api)
    await given_days_pass(api, 8, login_id=login_id)
    assert only_row(await when_list_deals(api))["risk"] is None
    await log_in(api, ADMIN_LOGIN)
    # When
    saved = await when_update_alert_settings(api, 7)
    # Then
    then_status_is(saved, 200)
    response = await when_list_deals(api)
    then_status_is(response, 200)
    then_risk_is(only_row(response), "stale")


async def test_a_raised_threshold_clears_the_stale_mark_at_once(api: Api) -> None:
    """Scenario: 경고 기준을 30일로 늘리면 15일 지난 Deal의 미업데이트가 사라진다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_days_pass(api, 15, login_id=login_id)
    assert (await when_get_deal(api, deal["code"])).json()["risk"] == "stale"
    await log_in(api, ADMIN_LOGIN)
    # When
    saved = await when_update_alert_settings(api, 30)
    # Then
    then_status_is(saved, 200)
    response = await when_get_deal(api, deal["code"])
    then_status_is(response, 200)
    then_risk_is(response.json(), None)
