"""Deal 목록 기한초과·미업데이트 필터 feature의 step.

시계는 로컬 정오에서 시작해 며칠씩 움직인다(움직이면 세션이 만료되므로 다시 로그인한다).
Given은 공개 API로 Deal·Action·경고 기준을 만들고, Then은 응답의 code·total·risk만 본다.
"""

from typing import TYPE_CHECKING

from tests.functional.steps.actions import given_action
from tests.functional.steps.alerts import when_update_alert_settings
from tests.functional.steps.auth import ADMIN_LOGIN, given_logged_in_as
from tests.functional.steps.deal_risk import (
    given_clock_at_local_noon,
    given_days_pass,
    given_due_in,
)
from tests.functional.steps.deals import given_deal, when_update_deal
from tests.functional.steps.users import log_in

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api


async def given_deals_with_every_risk(api: Api) -> dict[str, str]:
    """경고 기준 7일. 이름 -> code. 마지막 시점의 오늘은 시작일 + 8일이다.

    stale_only: 시작일 등록, Action 없음 / both: 시작일 등록, Due가 어제인 Action(지금은 둘 다) /
    closed: Due가 지난 Action이 있지만 Lost / overdue_only: 오늘 등록, Due가 어제인 Action /
    fresh: 오늘 등록, Action 없음.
    """
    await given_clock_at_local_noon(api)
    await given_logged_in_as(api, role="admin")
    saved = await when_update_alert_settings(api, 7)
    assert saved.status_code == 200, saved.text
    login_id = await given_logged_in_as(api, role="sales")
    codes: dict[str, str] = {}
    codes["stale_only"] = str((await given_deal(api, name="stale only"))["code"])
    codes["both"] = str((await given_deal(api, name="both"))["code"])
    await given_action(api, codes["both"], due_date=given_due_in(api, -1))
    codes["closed"] = str((await given_deal(api, name="closed"))["code"])
    await given_action(api, codes["closed"], due_date=given_due_in(api, -1))
    closed = await when_update_deal(api, codes["closed"], forecast_key="lost")
    assert closed.status_code == 200, closed.text
    await given_days_pass(api, 8, login_id=login_id)
    codes["overdue_only"] = str((await given_deal(api, name="overdue only"))["code"])
    await given_action(api, codes["overdue_only"], due_date=given_due_in(api, -1))
    codes["fresh"] = str((await given_deal(api, name="fresh"))["code"])
    await log_in(api, login_id)
    return codes


async def given_threshold_changed_by_admin(api: Api, login_id: str, days: int) -> None:
    await log_in(api, ADMIN_LOGIN)
    saved = await when_update_alert_settings(api, days)
    assert saved.status_code == 200, saved.text
    await log_in(api, login_id)


def then_every_row_has_risk_in(response: Response, accepted: set[str]) -> None:
    risks = {str(item["risk"]) for item in response.json()["items"]}
    assert risks <= accepted, risks
