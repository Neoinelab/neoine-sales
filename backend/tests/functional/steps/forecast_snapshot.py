"""Forecast 월말 스냅숏 feature의 step(P6 R2).

스냅숏을 만드는 주체는 HTTP API가 아니라 서버 CLI(`python -m app.jobs.forecast_snapshot`)다. 그래서
이 feature의 When은 두 종류다: 스냅숏을 만드는 시나리오는 CLI 진입점(`run`)을 같은 DB에
실제 Container로 한 번 실행하고, 스냅숏을 읽는 시나리오는 읽기 API 하나를
호출한다. CLI의 시계는 시나리오가 정한 실행 시각의 고정 시계다(API 서버 시계와 별개이므로
로그인 세션이 만료되지 않는다).
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Final

from app.container import Container
from tests.fakes.unit_of_work import FixedClock
from tests.functional.conftest import make_settings
from tests.functional.steps.forecast import cells_of, open_total_of

if TYPE_CHECKING:
    from collections.abc import Sequence

    from httpx import Response

    from tests.functional.conftest import Api

SNAPSHOTS: Final = "/api/v1/forecast/snapshots"
UNREACHABLE_DATABASE: Final = "postgresql+asyncpg://nobody:none@127.0.0.1:1/none"  # 접속 불가
# 2026-10-01 00:05(서버 OS 로컬) 실행 -> 기준 월 2026-09
RUN_AT: Final = datetime(2026, 10, 1, 0, 5).astimezone()
LATER_RUN_AT: Final = datetime(2026, 10, 1, 9, 0).astimezone()
AUGUST_RUN_AT: Final = datetime(2026, 9, 1, 0, 5).astimezone()
Cell = tuple[int, int]  # (건수, 금액)


# --- Given / When: 서버 CLI ---


async def run_snapshot_job(
    api: Api,
    argv: Sequence[str] = (),
    *,
    at: datetime = RUN_AT,
    database_url: str | None = None,
) -> int:
    """`python -m app.jobs.forecast_snapshot`을 `at` 시각에 실행하고 종료 코드를 돌려준다."""
    from app.jobs.forecast_snapshot import run  # noqa: PLC0415 - 구현 지연 import

    url = database_url or api.database_url.render_as_string(hide_password=False)
    container = Container(make_settings(url), clock=FixedClock(at))
    try:
        return await run(list(argv), container.take_forecast_snapshot())
    finally:
        await container.dispose()


async def given_snapshot_taken(
    api: Api, argv: Sequence[str] = (), *, at: datetime = RUN_AT
) -> None:
    """스냅숏이 이미 저장되어 있다(CLI가 성공했다)."""
    code = await run_snapshot_job(api, argv, at=at)
    assert code == 0, f"Given 실패: 스냅숏 CLI 종료 코드 {code}"


async def when_snapshot_job_runs(
    api: Api, argv: Sequence[str] = (), *, at: datetime = RUN_AT, database_url: str | None = None
) -> int:
    return await run_snapshot_job(api, argv, at=at, database_url=database_url)


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
