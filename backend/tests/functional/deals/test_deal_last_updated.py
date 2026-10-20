"""Feature: 최종 업데이트는 Action 기준이다(Deal 수정은 반영하지 않는다).

last_updated_at은 모든 Action(진행사항만 있는 행 포함)의 가장 최근 수행 시각이고, Action이 없으면
Deal 등록 시각이다. 인라인 수정 같은 Deal 수정은 값을 바꾸지 않고 미업데이트도 풀지 않는다.
기본 정렬도 이 값을 따른다. 오늘은 서버 로컬 날짜다.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import given_action, when_delete_action
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deal_risk import (
    given_clock_at_local_noon,
    given_days_pass,
    only_row,
    then_risk_is,
)
from tests.functional.steps.deals import (
    given_deal,
    list_codes,
    when_get_deal,
    when_list_deals,
    when_update_deal,
)
from tests.functional.steps.next_action_status import given_progress_only_action

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def test_a_deal_edit_does_not_change_the_last_update_or_clear_stale(api: Api) -> None:
    """Scenario: 15일 뒤 금액을 고쳐도 최종 업데이트는 등록 시각이고 미업데이트가 유지된다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_days_pass(api, 15, login_id=login_id)
    # When
    edited = await when_update_deal(api, deal["code"], revenue_amount=200_000_000)
    # Then
    then_status_is(edited, 200)
    body = (await when_get_deal(api, deal["code"])).json()
    assert datetime.fromisoformat(body["last_updated_at"]) == datetime.fromisoformat(
        deal["created_at"]
    )
    then_risk_is(body, "stale")


async def test_registering_an_action_clears_stale(api: Api) -> None:
    """Scenario: 진행사항만 Action을 등록하면 최종 업데이트가 그 시각이 되고 미업데이트가 풀린다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_days_pass(api, 15, login_id=login_id)
    # When
    registered = await given_progress_only_action(api, deal["code"])
    # Then
    body = (await when_get_deal(api, deal["code"])).json()
    assert datetime.fromisoformat(body["last_updated_at"]) == datetime.fromisoformat(
        registered["acted_at"]
    )
    then_risk_is(body, None)


async def test_deleting_the_only_action_falls_back_to_the_registration_time(api: Api) -> None:
    """Scenario: 유일한 Action을 지우면 최종 업데이트가 Deal 등록 시각으로 돌아간다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_days_pass(api, 5, login_id=login_id)
    created = await given_action(api, deal["code"])
    # When
    deleted = await when_delete_action(api, created["id"])
    # Then
    then_status_is(deleted, 204)
    body = only_row(await when_list_deals(api))
    assert datetime.fromisoformat(body["last_updated_at"]) == datetime.fromisoformat(
        deal["created_at"]
    )


async def test_default_sort_uses_action_time_not_deal_edits(api: Api) -> None:
    """Scenario: 나중에 수정한 Deal보다 Action을 남긴 Deal이 기본 정렬에서 앞선다."""
    # Given
    await given_logged_in_as(api, role="sales")
    edited = await given_deal(api, name="수정만")
    acted = await given_deal(api, name="Action")
    await given_progress_only_action(api, acted["code"])
    await when_update_deal(api, edited["code"], revenue_amount=200_000_000)
    # When
    response = await when_list_deals(api)
    # Then
    assert list_codes(response) == [acted["code"], edited["code"]]
