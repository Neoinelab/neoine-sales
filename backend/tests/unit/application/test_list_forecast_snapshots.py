"""ListForecastSnapshots: 저장된 기준 월 목록을 최근 순으로 돌려준다."""

from typing import TYPE_CHECKING

from app.application.forecast.list_snapshots import ListForecastSnapshots
from app.domain.forecast.snapshot import YearMonth
from tests.unit.application.forecast_snapshot_env import local, store_snapshot

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


async def test_no_snapshots_gives_an_empty_list(env: DealEnv) -> None:
    """스냅숏이 없으면 빈 목록이다

    테스트 코드: FC-025
    """
    # when: 목록을 읽는다
    listed = list(await ListForecastSnapshots(env.uow_factory).execute())

    # then: 비어 있다
    assert listed == []


async def test_periods_are_listed_newest_first_with_their_taken_at(env: DealEnv) -> None:
    """기준 월은 최근 순이고 생성 시각이 함께 나온다

    테스트 코드: FC-025
    """
    # given: 2026-08, 2026-09, 2025-12 스냅숏
    await store_snapshot(env, YearMonth(2026, 8), local(2026, 9, 1, 0, 5))
    await store_snapshot(env, YearMonth(2026, 9), local(2026, 10, 1, 0, 5))
    await store_snapshot(env, YearMonth(2025, 12), local(2026, 1, 1, 0, 5))

    # when: 목록을 읽는다
    infos = await ListForecastSnapshots(env.uow_factory).execute()

    # then: 2026-09, 2026-08, 2025-12 순이고 각자 생성 시각이다
    assert [(info.period, info.taken_at) for info in infos] == [
        (YearMonth(2026, 9), local(2026, 10, 1, 0, 5)),
        (YearMonth(2026, 8), local(2026, 9, 1, 0, 5)),
        (YearMonth(2025, 12), local(2026, 1, 1, 0, 5)),
    ]
