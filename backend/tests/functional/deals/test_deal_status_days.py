"""Feature: Deal 응답은 Status에 머문 일수(`status_days`)와 진입 시각(`status_changed_at`)을 준다.

체류 일수는 오늘 - 진입 업무 날짜(서버 로컬 시간대)이고 진입 당일은 0이다. Status key가 실제로 바뀔
때만 진입 시각이 그 요청의 서버 시각으로 바뀌고, Forecast만 바꾸면 그대로다. 서버 시계가 움직이면
세션이 만료되므로 시간이 지난 뒤에는 같은 사용자로 다시 로그인한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import given_action
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deal_changes import when_change_deal
from tests.functional.steps.deal_risk import (
    given_clock_at_local_noon,
    given_days_pass,
    given_due_in,
    only_row,
    then_days_in_status_are,
    then_risk_is,
    then_status_entered_at,
)
from tests.functional.steps.deals import (
    given_deal,
    when_get_deal,
    when_list_deals,
    when_register_deal,
    when_update_deal,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def test_a_new_deal_entered_its_status_today(api: Api) -> None:
    """Scenario: 등록 응답은 진입 시각이 등록 시각이고 체류 일수가 0이며 Risk가 없다."""
    # Given
    await given_clock_at_local_noon(api)
    await given_logged_in_as(api, role="sales")
    api.clock.advance(1)
    # When
    response = await when_register_deal(api)
    # Then
    then_status_is(response, 201)
    body = response.json()
    then_days_in_status_are(body, 0)
    then_status_entered_at(body, api.clock.now())
    then_risk_is(body, None)


@pytest.mark.parametrize("view", ["list", "detail"])
async def test_days_in_status_count_from_the_entry_date(api: Api, view: str) -> None:
    """Scenario: 5일 전에 등록한 Deal은 목록과 상세 모두 체류 5일이고 진입 시각은 등록 시각이다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    registered_at = api.clock.now()
    await given_days_pass(api, 5, login_id=login_id)
    # When
    response = (
        await when_list_deals(api) if view == "list" else await when_get_deal(api, deal["code"])
    )
    # Then
    then_status_is(response, 200)
    body = only_row(response) if view == "list" else response.json()
    then_days_in_status_are(body, 5)
    then_status_entered_at(body, registered_at)


async def test_status_change_resets_days_in_status(api: Api) -> None:
    """Scenario: 5일 뒤 Status를 바꾸면 응답의 체류 일수가 0이고 진입 시각이 변경 시각이 된다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, status_key="prospecting")
    await given_days_pass(api, 5, login_id=login_id)
    # When
    response = await when_update_deal(api, deal["code"], status_key="introduction")
    # Then
    then_status_is(response, 200)
    then_days_in_status_are(response.json(), 0)
    then_status_entered_at(response.json(), api.clock.now())
    reread = await when_get_deal(api, deal["code"])
    then_days_in_status_are(reread.json(), 0)


async def test_a_single_status_change_resets_days_in_status(api: Api) -> None:
    """Scenario: /changes로 Status를 바꾸면 응답의 Deal이 체류 0일, 진입 시각 = 변경 시각이다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, status_key="prospecting")
    await given_days_pass(api, 5, login_id=login_id)
    # When
    response = await when_change_deal(api, deal["code"], "status_key", "introduction")
    # Then
    then_status_is(response, 200)
    changed = response.json()["deal"]
    then_days_in_status_are(changed, 0)
    then_status_entered_at(changed, api.clock.now())


async def test_forecast_only_change_keeps_days_in_status(api: Api) -> None:
    """Scenario: Forecast만 바꾸면 체류 일수와 진입 시각이 그대로다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    registered_at = api.clock.now()
    await given_days_pass(api, 5, login_id=login_id)
    # When
    response = await when_change_deal(api, deal["code"], "forecast_key", "best")
    # Then
    then_status_is(response, 200)
    unchanged = response.json()["deal"]
    then_days_in_status_are(unchanged, 5)
    then_status_entered_at(unchanged, registered_at)


async def test_write_responses_carry_risk_like_the_list(api: Api) -> None:
    """Scenario: 수정 응답도 같은 규칙으로 계산한 Risk를 담는다(기한이 지난 Deal은 기한초과)."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_action(api, deal["code"], due_date=given_due_in(api, 1))
    await given_days_pass(api, 3, login_id=login_id)
    # When
    response = await when_update_deal(api, deal["code"], name="ERP 구축 2차")
    # Then
    then_status_is(response, 200)
    then_risk_is(response.json(), "overdue")
    then_days_in_status_are(response.json(), 3)
