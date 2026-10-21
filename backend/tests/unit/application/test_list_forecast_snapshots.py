"""ListForecastSnapshots(P6 R2 AC-16): 저장된 기준 월 목록을 최근 순으로 돌려준다."""

from typing import TYPE_CHECKING

from app.application.forecast.list_snapshots import ListForecastSnapshots
from app.domain.forecast.snapshot import YearMonth

from tests.unit.application.forecast_snapshot_env import local, store_snapshot

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


async def test_no_snapshots_gives_an_empty_list(env: DealEnv) -> None:
    assert list(await ListForecastSnapshots(env.uow_factory).execute()) == []


async def test_periods_are_listed_newest_first_with_their_taken_at(env: DealEnv) -> None:
    await store_snapshot(env, YearMonth(2026, 8), local(2026, 9, 1, 0, 5))
    await store_snapshot(env, YearMonth(2026, 9), local(2026, 10, 1, 0, 5))
    await store_snapshot(env, YearMonth(2025, 12), local(2026, 1, 1, 0, 5))

    infos = await ListForecastSnapshots(env.uow_factory).execute()

    assert [(info.period, info.taken_at) for info in infos] == [
        (YearMonth(2026, 9), local(2026, 10, 1, 0, 5)),
        (YearMonth(2026, 8), local(2026, 9, 1, 0, 5)),
        (YearMonth(2025, 12), local(2026, 1, 1, 0, 5)),
    ]
