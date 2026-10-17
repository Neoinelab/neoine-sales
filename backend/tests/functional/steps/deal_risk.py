"""Deal Risk·Status 체류 feature의 step(P3 R2): 시계를 며칠 움직이고 응답의 파생 값을 확인한다.

서버 시계(`api.clock`)가 움직이면 세션(TTL 8시간)이 만료되므로, 시간이 지난 뒤에는 같은 사용자로
다시 로그인한다. 날짜 경계에 흔들리지 않도록 시나리오는 로컬 정오에서 시작한다.
"""

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any, Final

from app.domain.common.business_date import business_date
from tests.functional.steps.users import log_in

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

DAY_SECONDS: Final = 24 * 3600


def local_today(api: Api) -> date:
    """서버 시계가 가리키는 업무 날짜(OS 로컬 시간대)."""
    return business_date(api.clock.now())


async def given_clock_at_local_noon(api: Api) -> None:
    """서버 시계를 오늘(업무 날짜) 로컬 정오로 맞춘다. 로그인보다 먼저 부른다."""
    noon = datetime.combine(local_today(api), time(12)).astimezone()
    api.clock.advance(int((noon - api.clock.now()).total_seconds()))


async def given_days_pass(api: Api, days: int, *, login_id: str) -> None:
    """시계를 days일 뒤로 보내고 login_id로 다시 로그인한다(세션이 만료되기 때문)."""
    api.clock.advance(days * DAY_SECONDS)
    await log_in(api, login_id)


def given_due_in(api: Api, days: int) -> str:
    """오늘(업무 날짜)에서 days일 뒤의 Due Date 문자열(음수면 과거)."""
    return (local_today(api) + timedelta(days=days)).isoformat()


def only_row(response: Response) -> dict[str, Any]:
    items = response.json()["items"]
    assert len(items) == 1, items
    return dict(items[0])


def then_risk_is(body: dict[str, Any], expected: str | None) -> None:
    assert body["risk"] == expected, body["risk"]


def then_days_in_status_are(body: dict[str, Any], days: int) -> None:
    assert body["status_days"] == days, body["status_days"]


def then_status_entered_at(body: dict[str, Any], moment: datetime) -> None:
    assert datetime.fromisoformat(body["status_changed_at"]) == moment, body["status_changed_at"]
