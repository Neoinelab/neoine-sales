"""Feature: Deal의 Next Action·기한초과는 Next Action이 있는 가장 최근 Action을 기준으로 한다.

진행사항만 있는 Action은 기준 행이 될 수 없어 건너뛴다. 기한초과는 기준 행의 Due Date가 오늘보다
앞이면 상태(Open/종료)와 무관하게 유지된다. 최종 업데이트와 미업데이트는 진행사항만 있는 Action을
포함한 모든 Action의 가장 최근 수행 시각(과 Deal 수정 시각)을 따른다. 오늘은 서버 로컬 날짜다.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import given_action
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deal_risk import (
    given_clock_at_local_noon,
    given_days_pass,
    given_due_in,
    only_row,
    then_risk_is,
)
from tests.functional.steps.deals import given_deal, when_get_deal, when_list_deals
from tests.functional.steps.next_action_status import (
    given_progress_only_action,
    given_status_changed,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def test_a_later_progress_only_action_does_not_replace_the_next_action(api: Api) -> None:
    """Scenario: 더 최근 Action이 진행사항만이면 목록·상세의 Next Action은 이전 행의 값이다."""
    # Given
    await given_clock_at_local_noon(api)
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    due = given_due_in(api, 30)
    await given_action(api, deal["code"], next_action="계약서 검토", due_date=due)
    await given_progress_only_action(api, deal["code"], action="전화 통화")
    # When
    listed = only_row(await when_list_deals(api))
    detail = (await when_get_deal(api, deal["code"])).json()
    # Then
    expected = {"text": "계약서 검토", "due_date": due, "status": "open"}
    assert listed["next_action"] == expected
    assert detail["next_action"] == expected


async def test_overdue_follows_the_due_date_of_that_basis_row(api: Api) -> None:
    """Scenario: 기준 행의 Due가 지났으면 더 최근의 진행사항만 Action이 있어도 기한초과다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_action(api, deal["code"], due_date=given_due_in(api, 1))
    await given_progress_only_action(api, deal["code"], action="전화 통화")
    await given_days_pass(api, 2, login_id=login_id)
    # When
    response = await when_get_deal(api, deal["code"])
    # Then
    then_status_is(response, 200)
    then_risk_is(response.json(), "overdue")


async def test_closing_the_next_action_keeps_the_overdue_mark(api: Api) -> None:
    """Scenario: 기한 지난 Next Action을 종료해도 기한초과 표시는 유지되고 상태만 달라진다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    created = await given_action(api, deal["code"], due_date=given_due_in(api, 1))
    await given_days_pass(api, 2, login_id=login_id)
    await given_status_changed(api, created["id"], "done", "늦게 끝냄")
    # When
    listed = only_row(await when_list_deals(api))
    detail = (await when_get_deal(api, deal["code"])).json()
    # Then
    then_risk_is(listed, "overdue")
    then_risk_is(detail, "overdue")
    assert detail["next_action"]["status"] == "done"


async def test_a_deal_with_only_progress_only_actions_has_no_next_action(api: Api) -> None:
    """Scenario: Next Action이 한 번도 없는 Deal은 next_action이 null이고 기한초과도 아니다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_progress_only_action(api, deal["code"])
    await given_days_pass(api, 5, login_id=login_id)
    # When
    response = await when_get_deal(api, deal["code"])
    # Then
    body = response.json()
    assert body["next_action"] is None
    then_risk_is(body, None)


async def test_a_progress_only_action_refreshes_the_last_update_and_clears_stale(
    api: Api,
) -> None:
    """Scenario: 진행사항만 등록해도 최종 업데이트가 그 시각이 되고 미업데이트가 풀린다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_days_pass(api, 13, login_id=login_id)
    registered = await given_progress_only_action(api, deal["code"])
    await given_days_pass(api, 1, login_id=login_id)  # Deal 등록 후 14일째지만 Action은 1일 전
    # When
    response = await when_get_deal(api, deal["code"])
    # Then
    body = response.json()
    assert datetime.fromisoformat(body["last_updated_at"]) == datetime.fromisoformat(
        registered["acted_at"]
    )
    then_risk_is(body, None)


async def test_the_deal_turns_stale_again_after_the_threshold_from_the_progress_action(
    api: Api,
) -> None:
    """Scenario: 진행사항만 Action 이후에도 14일이 지나면 다시 미업데이트다."""
    # Given
    await given_clock_at_local_noon(api)
    login_id = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_days_pass(api, 13, login_id=login_id)
    await given_progress_only_action(api, deal["code"])
    await given_days_pass(api, 14, login_id=login_id)
    # When
    response = await when_get_deal(api, deal["code"])
    # Then
    then_risk_is(response.json(), "stale")
