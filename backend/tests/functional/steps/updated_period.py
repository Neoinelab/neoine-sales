"""최종 업데이트 기간 feature의 step: 오늘(서버 업무 날짜) 기준 날짜 만들기, 목록·프리셋 조회.

Given은 공개 API로 Deal·Action을 만들고 서버 시계를 옮긴다. When은 HTTP API 하나, Then은 응답의
code 목록·total·프리셋 값만 본다. 서버 시계가 움직이면 세션이 만료되므로 시간이 지난 뒤에는 같은
사용자로 다시 로그인한다(`deal_risk.given_days_pass`).
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING, Final

from app.domain.common.business_date import business_date
from tests.functional.steps.deals import DEALS
from tests.support.functional_clock import active_clock

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

UPDATED_PERIODS: Final = f"{DEALS}/updated-periods"
PRESET_KEYS: Final = ["2w", "1m", "2m", "3m", "6m"]
UPCOMING_KEYS: Final = ["1m", "2m"]


def days_from_today(api: Api, offset: int) -> str:
    """서버 업무 날짜에서 offset일 뒤(음수면 전)의 `YYYY-MM-DD`."""
    return (business_date(api.clock.now()) + timedelta(days=offset)).isoformat()


async def when_list_updated_periods(api: Api) -> Response:
    return await api.get(UPDATED_PERIODS)


def then_periods_follow_the_server_date(response: Response) -> None:
    """200이고 today는 서버 업무 날짜, 키는 정해진 순서, 각 범위는 도메인 규칙과 같다."""
    from app.domain.deal.updated_period import UpdatedPeriodPreset  # noqa: PLC0415 - 지연 import

    assert response.status_code == 200, f"{response.status_code}: {response.text}"
    body = response.json()
    today = business_date(active_clock().now())
    assert body["today"] == today.isoformat()
    assert [p["key"] for p in body["periods"]] == PRESET_KEYS
    for period in body["periods"]:
        start, end = UpdatedPeriodPreset(period["key"]).range_until(today)
        assert (period["from"], period["to"]) == (start.isoformat(), end.isoformat())
    then_upcoming_follow_the_server_date(response)


def then_upcoming_follow_the_server_date(response: Response) -> None:
    """upcoming은 정해진 순서이고 각 범위가 도메인 규칙(오늘~N개월 뒤)과 같다."""
    from app.domain.deal.updated_period import UpcomingPeriodPreset  # noqa: PLC0415 - 지연 import

    assert response.status_code == 200, f"{response.status_code}: {response.text}"
    today = business_date(active_clock().now())
    upcoming = response.json()["upcoming"]
    assert [u["key"] for u in upcoming] == UPCOMING_KEYS
    for item in upcoming:
        start, end = UpcomingPeriodPreset(item["key"]).range_from(today)
        assert (item["from"], item["to"]) == (start.isoformat(), end.isoformat())


def then_upcoming_ends_are(response: Response, today: date, expected: dict[str, date]) -> None:
    assert response.status_code == 200, f"{response.status_code}: {response.text}"
    upcoming = {u["key"]: u for u in response.json()["upcoming"]}
    assert {k: upcoming[k]["from"] for k in expected} == {k: today.isoformat() for k in expected}
    ends = {k: v.isoformat() for k, v in expected.items()}
    assert {k: upcoming[k]["to"] for k in expected} == ends


def then_period_starts_are(response: Response, expected: dict[str, date]) -> None:
    assert response.status_code == 200, f"{response.status_code}: {response.text}"
    starts = {p["key"]: p["from"] for p in response.json()["periods"]}
    assert {k: starts[k] for k in expected} == {k: v.isoformat() for k, v in expected.items()}
