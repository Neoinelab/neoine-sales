"""TakeForecastSnapshot(P6 R2 AC-13~15): 월말 스냅숏을 한 트랜잭션에서 저장하거나 대체한다.

Fake UoW 위에서 결과(저장된 스냅숏)를 본다. 기준 월은 서버 OS 로컬 시간대의 달력 날짜로
정한다(2026-10-01 00:05 실행 → 기준 월 2026-09).
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.forecast.take_snapshot import TakeForecastSnapshot
from app.domain.code.values import CodeKind, ForecastOutcome
from app.domain.common.errors import InvalidValueError
from app.domain.forecast.snapshot import YearMonth
from tests.factories_catalog import make_code
from tests.fakes.unit_of_work import FixedClock
from tests.support.user_ids import OWNER_ID
from tests.unit.application.forecast_snapshot_env import (
    cell_keys,
    local,
    new_deal,
    new_owner,
    store_snapshot,
)

if TYPE_CHECKING:
    from app.domain.forecast.snapshot import ForecastSnapshot
    from tests.unit.application.deal_env import DealEnv

RUN_AT = local(2026, 10, 1, 0, 5)
SEPT = YearMonth(2026, 9)


def _use_case(env: DealEnv, clock: FixedClock | None = None) -> TakeForecastSnapshot:
    return TakeForecastSnapshot(env.uow_factory, clock or FixedClock(RUN_AT))


async def _stored(env: DealEnv, period: YearMonth = SEPT) -> ForecastSnapshot | None:
    return await env.uow.forecast_snapshots.get(period)


async def test_default_target_is_the_previous_month_of_the_local_business_date(
    env: DealEnv,
) -> None:
    result = await _use_case(env).execute()

    assert result.period == SEPT
    stored = await _stored(env)
    assert stored is not None
    assert stored.period == SEPT
    assert stored.taken_at == RUN_AT


async def test_a_run_on_the_last_evening_still_targets_the_month_before_the_run_month(
    env: DealEnv,
) -> None:
    result = await _use_case(env, FixedClock(local(2026, 9, 30, 23, 59))).execute()

    assert result.period == YearMonth(2026, 8)


async def test_january_first_run_targets_the_previous_december(env: DealEnv) -> None:
    result = await _use_case(env, FixedClock(local(2027, 1, 1, 0, 5))).execute()

    assert result.period == YearMonth(2026, 12)


async def test_cells_group_every_deal_by_revenue_year_month_owner_and_forecast(
    env: DealEnv,
) -> None:
    other = await new_owner(env, "other")
    await new_deal(env, "pipeline", 100, date(2026, 11, 15))
    await new_deal(env, "pipeline", 40, date(2026, 11, 30))
    await new_deal(env, "commit", 7, date(2026, 12, 31))
    await new_deal(env, "won", 500, date(2026, 11, 20))
    await new_deal(env, "pipeline", 5, date(2026, 11, 2), owner_user_id=other)
    await new_deal(env, "pipeline", 9, date(2027, 1, 1))  # 기간 제한 없이 모든 Deal
    await new_deal(env, "pipeline", 3, date(2025, 3, 1))

    result = await _use_case(env).execute()

    stored = await _stored(env)
    assert stored is not None
    assert cell_keys(stored.cells) == {
        (2026, 11, OWNER_ID, "pipeline", 2, 140),
        (2026, 12, OWNER_ID, "commit", 1, 7),
        (2026, 11, OWNER_ID, "won", 1, 500),
        (2026, 11, other, "pipeline", 1, 5),
        (2027, 1, OWNER_ID, "pipeline", 1, 9),
        (2025, 3, OWNER_ID, "pipeline", 1, 3),
    }
    assert result.cell_count == 6


async def test_snapshot_includes_lost_cells(env: DealEnv) -> None:
    await new_deal(env, "lost", 999, date(2026, 11, 1))

    await _use_case(env).execute()

    stored = await _stored(env)
    assert stored is not None
    assert cell_keys(stored.cells) == {(2026, 11, OWNER_ID, "lost", 1, 999)}


async def test_cells_carry_no_code_attributes_only_the_key(env: DealEnv) -> None:
    await new_deal(env, "commit", 10)

    await _use_case(env).execute()

    stored = await _stored(env)
    assert stored is not None
    assert stored.cells[0].forecast_key == "commit"
    assert not hasattr(stored.cells[0], "forecast_name")


async def test_snapshot_stores_the_whole_forecast_code_list_as_columns(env: DealEnv) -> None:
    codes = await env.uow.codes.list(CodeKind.FORECAST)

    await _use_case(env).execute()

    stored = await _stored(env)
    assert stored is not None
    assert [(c.key, c.name, c.outcome, c.order) for c in stored.columns] == [
        (code.key.value, code.name, code.outcome, code.order) for code in codes
    ]
    outcomes = {c.key: c.outcome for c in stored.columns}
    assert outcomes["won"] is ForecastOutcome.WON
    assert outcomes["lost"] is ForecastOutcome.LOST
    assert outcomes["commit"] is ForecastOutcome.OPEN


async def test_codes_without_any_deal_are_stored_as_columns_too(env: DealEnv) -> None:
    await new_deal(env, "pipeline", 100)

    await _use_case(env).execute()

    stored = await _stored(env)
    assert stored is not None
    assert cell_keys(stored.cells) == {(2026, 8, OWNER_ID, "pipeline", 1, 100)}
    assert {"pipeline", "best", "most_likely", "commit", "won", "lost"} <= {
        c.key for c in stored.columns
    }


async def test_a_code_added_before_the_run_is_stored_as_a_column(env: DealEnv) -> None:
    await env.uow.codes.add(make_code(CodeKind.FORECAST, key="verbal", name="Verbal", order=99))

    await _use_case(env).execute()

    stored = await _stored(env)
    assert stored is not None
    assert {c.key: c.name for c in stored.columns}["verbal"] == "Verbal"


async def test_names_and_order_in_the_snapshot_are_those_at_the_time_of_the_run(
    env: DealEnv,
) -> None:
    await new_deal(env, "commit", 10)
    codes = {c.key.value: c for c in await env.uow.codes.list(CodeKind.FORECAST)}
    commit = codes["commit"]
    commit.rename("확정", env.clock.now())
    await env.uow.codes.update(commit)

    await _use_case(env).execute()
    commit.rename("다시 바꿈", env.clock.now())  # 스냅숏 이후의 이름 변경은 저장된 값에 영향이 없다
    await env.uow.codes.update(commit)

    stored = await _stored(env)
    assert stored is not None
    by_key = {c.key: c for c in stored.columns}
    assert by_key["commit"].name == "확정"
    assert by_key["commit"].order == commit.order
    assert by_key["won"].name == codes["won"].name


async def test_a_run_without_deals_still_stores_the_columns_and_no_cells(env: DealEnv) -> None:
    result = await _use_case(env).execute()

    stored = await _stored(env)
    assert stored is not None
    assert list(stored.cells) == []
    assert len(stored.columns) >= 6
    assert result.cell_count == 0


async def test_first_run_is_not_a_replacement_and_reports_the_run_time(env: DealEnv) -> None:
    result = await _use_case(env).execute()

    assert result.replaced is False
    assert result.taken_at == RUN_AT


async def test_rerun_replaces_cells_of_the_same_month(env: DealEnv) -> None:
    await new_deal(env, "pipeline", 100)
    first_run = _use_case(env)
    await first_run.execute()
    await new_deal(env, "commit", 7)
    later = FixedClock(local(2026, 10, 1, 9, 0))

    result = await _use_case(env, later).execute()

    stored = await _stored(env)
    assert stored is not None
    assert cell_keys(stored.cells) == {
        (2026, 8, OWNER_ID, "pipeline", 1, 100),
        (2026, 8, OWNER_ID, "commit", 1, 7),
    }
    assert stored.taken_at == later.now()
    assert result.replaced is True


async def test_rerun_replaces_the_stored_columns_with_the_current_code_list(
    env: DealEnv,
) -> None:
    await _use_case(env).execute()
    commit = next(c for c in await env.uow.codes.list(CodeKind.FORECAST) if c.key.value == "commit")
    commit.rename("확정", env.clock.now())
    await env.uow.codes.update(commit)

    await _use_case(env, FixedClock(local(2026, 10, 1, 9, 0))).execute()

    stored = await _stored(env)
    assert stored is not None
    assert {c.key: c.name for c in stored.columns}["commit"] == "확정"
    assert len([c for c in stored.columns if c.key == "commit"]) == 1


async def test_rerun_keeps_a_single_snapshot_for_the_month(env: DealEnv) -> None:
    await _use_case(env).execute()
    await _use_case(env, FixedClock(local(2026, 10, 1, 9, 0))).execute()

    periods = await env.uow.forecast_snapshots.list_periods()

    assert [info.period for info in periods] == [SEPT]


async def test_rerun_drops_cells_of_deals_that_no_longer_exist(env: DealEnv) -> None:
    view = await env.new_deal(
        forecast_key="pipeline",
        status_key="prospecting",
        revenue_amount=100,
        revenue_date=date(2026, 8, 15),
    )
    await _use_case(env).execute()
    await env.uow.deals.delete(view.item.deal.id)

    await _use_case(env).execute()

    stored = await _stored(env)
    assert stored is not None
    assert list(stored.cells) == []


@pytest.mark.parametrize("target", [YearMonth(2026, 9), YearMonth(2026, 10)])
async def test_previous_and_current_month_can_be_taken_explicitly(
    env: DealEnv, target: YearMonth
) -> None:
    result = await _use_case(env, FixedClock(local(2026, 10, 15, 12, 0))).execute(target)

    assert result.period == target
    assert await _stored(env, target) is not None


async def test_an_older_month_is_refused_and_nothing_is_written(env: DealEnv) -> None:
    await new_deal(env, "pipeline", 100)

    with pytest.raises(InvalidValueError) as caught:
        await _use_case(env, FixedClock(local(2026, 10, 15, 12, 0))).execute(YearMonth(2026, 8))

    assert "다시 계산할 수 없습니다" in str(caught.value)
    assert list(await env.uow.forecast_snapshots.list_periods()) == []


async def test_a_future_month_is_refused_and_nothing_is_written(env: DealEnv) -> None:
    with pytest.raises(InvalidValueError):
        await _use_case(env, FixedClock(local(2026, 10, 15, 12, 0))).execute(YearMonth(2026, 11))

    assert list(await env.uow.forecast_snapshots.list_periods()) == []


async def test_a_refused_month_leaves_the_existing_snapshot_untouched(env: DealEnv) -> None:
    taken = local(2026, 9, 1, 0, 5)
    await store_snapshot(env, YearMonth(2026, 8), taken)

    with pytest.raises(InvalidValueError):
        await _use_case(env, FixedClock(local(2026, 10, 15))).execute(YearMonth(2026, 8))

    stored = await _stored(env, YearMonth(2026, 8))
    assert stored is not None
    assert stored.taken_at == taken


async def test_an_error_while_saving_keeps_the_previous_snapshot(
    env: DealEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    await new_deal(env, "pipeline", 100)
    await _use_case(env).execute()
    await new_deal(env, "commit", 7)
    repository = env.uow.forecast_snapshots
    original = repository.replace

    async def replace_then_fail(snapshot: ForecastSnapshot) -> None:
        await original(snapshot)
        msg = "disk full (test double)"
        raise RuntimeError(msg)

    monkeypatch.setattr(repository, "replace", replace_then_fail)

    with pytest.raises(RuntimeError, match="disk full"):
        await _use_case(env, FixedClock(local(2026, 10, 1, 9, 0))).execute()

    stored = await _stored(env)
    assert stored is not None
    assert stored.taken_at == RUN_AT
    assert cell_keys(stored.cells) == {(2026, 8, OWNER_ID, "pipeline", 1, 100)}
