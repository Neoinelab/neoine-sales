"""Forecast 월말 스냅숏 feature의 step(docker-compose 계획: 앱 내 스케줄러).

스냅숏을 만드는 주체는 HTTP API가 아니라 서버의 주기 확인이다.
그래서 이 feature의 When은 두 종류다: 스냅숏을 만드는 시나리오는 같은 DB에 실제 Container를
조립해 `ensure_monthly_forecast_snapshot().execute()`를 한 번 실행하고
(스케줄러 루프는 돌리지 않는다),
스냅숏을 읽는 시나리오는 읽기 API 하나를 호출한다. 확인의 시계는 시나리오가 정한 시각의 고정 시계다
(API 서버 시계와 별개이므로 로그인 세션이 만료되지 않는다).
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Final

from app.container import Container
from tests.fakes.unit_of_work import FixedClock
from tests.functional.conftest import make_settings
from tests.functional.steps.forecast import cells_of, open_total_of

if TYPE_CHECKING:
    from app.application.forecast.ensure_monthly_snapshot import SnapshotCheckResult
    from httpx import Response

    from tests.functional.conftest import Api

SNAPSHOTS: Final = "/api/v1/forecast/snapshots"
# 2026-10-01 00:05(서버 OS 로컬) 확인 -> 기준 월 2026-09
RUN_AT: Final = datetime(2026, 10, 1, 0, 5).astimezone()
LATER_RUN_AT: Final = datetime(2026, 10, 1, 9, 0).astimezone()
MID_MONTH_AT: Final = datetime(2026, 10, 15, 14, 30).astimezone()
AUGUST_RUN_AT: Final = datetime(2026, 9, 1, 0, 5).astimezone()
Cell = tuple[int, int]  # (건수, 금액)


# --- Given / When: 서버의 스냅숏 확인 ---


async def run_snapshot_check(api: Api, *, at: datetime = RUN_AT) -> SnapshotCheckResult:
    """서버가 `at` 시각에 전월 스냅숏 확인을 한 번 하고 결과를 돌려준다."""
    url = api.database_url.render_as_string(hide_password=False)
    container = Container(make_settings(url), clock=FixedClock(at))
    try:
        return await container.ensure_monthly_forecast_snapshot().execute()
    finally:
        await container.dispose()


async def given_snapshot_taken(api: Api, *, at: datetime = RUN_AT) -> None:
    """스냅숏이 이미 저장되어 있다(확인이 새로 만들었다)."""
    result = await run_snapshot_check(api, at=at)
    assert result.outcome.value == "taken", f"Given 실패: 스냅숏 확인 결과 {result.outcome}"


async def when_snapshot_check_runs(api: Api, *, at: datetime = RUN_AT) -> SnapshotCheckResult:
    return await run_snapshot_check(api, at=at)


# --- When: 읽기 API ---


async def when_list_snapshots(api: Api) -> Response:
    return await api.get(SNAPSHOTS)


async def when_get_snapshot_summary(api: Api, period: str, **params: str | int) -> Response:
    return await api.get(f"{SNAPSHOTS}/{period}/summary", params=dict(params))


# --- Then ---


def then_snapshot_periods_are(response: Response, periods: list[str]) -> None:
    assert [item["period"] for item in response.json()["items"]] == periods, response.json()


def then_snapshot_taken_at_is(response: Response, index: int, moment: datetime) -> None:
    taken = datetime.fromisoformat(response.json()["items"][index]["taken_at"])
    assert taken == moment, (taken, moment)


def row_of(response: Response, owner: int) -> dict[str, Any]:
    return next(r for r in response.json()["rows"] if r["owner"]["id"] == owner)


def then_snapshot_row_is(
    response: Response, *, owner: int, cells: dict[str, Cell], open_total: Cell
) -> None:
    """그 담당자 행의 0이 아닌 셀과 open_total이 같다."""
    row = row_of(response, owner)
    nonzero = {key: cell for key, cell in cells_of(row).items() if cell != (0, 0)}
    assert nonzero == cells
    assert open_total_of(row) == open_total


def then_snapshot_owner_ids_are(response: Response, owner_ids: list[int]) -> None:
    assert [row["owner"]["id"] for row in response.json()["rows"]] == owner_ids


def then_snapshot_basis_is(response: Response, period: str, taken_at: datetime) -> None:
    body = response.json()
    assert body["basis"] == "snapshot"
    assert body["snapshot_period"] == period
    assert datetime.fromisoformat(body["as_of"]) == taken_at


def row_owner(response: Response, owner: int) -> dict[str, Any]:
    """그 담당자 행의 owner(UserRef)."""
    return dict(row_of(response, owner)["owner"])
