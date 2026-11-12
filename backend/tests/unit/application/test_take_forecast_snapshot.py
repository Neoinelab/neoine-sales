"""TakeForecastSnapshot: 월말 스냅숏을 한 트랜잭션에서 저장하거나 대체한다.

Fake UoW 위에서 결과(저장된 스냅숏)를 본다. 기준 월은 서버 OS 로컬 시간대의 달력 날짜로
정한다(2026-10-01 00:05 실행 → 기준 월 2026-09).
"""

from datetime import date, datetime
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
    cell,
    cell_keys,
    given_kim_and_lee_deals,
    local,
    new_deal,
    store_snapshot,
)

if TYPE_CHECKING:
    from app.domain.forecast.snapshot import ForecastSnapshot
    from tests.unit.application.deal_env import DealEnv

RUN_AT = local(2026, 10, 1, 0, 5)
SEPT = YearMonth(2026, 9)
REFUSED_AUG = "2026-08 기준 월은 다시 계산할 수 없습니다. 전월과 당월만 가능합니다."
REFUSED_NOV = "2026-11 기준 월은 다시 계산할 수 없습니다. 전월과 당월만 가능합니다."


def _use_case(env: DealEnv, clock: FixedClock | None = None) -> TakeForecastSnapshot:
    return TakeForecastSnapshot(env.uow_factory, clock or FixedClock(RUN_AT))


async def _stored(env: DealEnv, period: YearMonth = SEPT) -> ForecastSnapshot | None:
    return await env.uow.forecast_snapshots.get(period)


async def test_default_target_is_the_previous_month_of_the_local_business_date(
    env: DealEnv,
) -> None:
    """기준 월을 정하지 않으면 서버 로컬 업무 날짜의 전월로 저장하고 실행 시각을 기록한다"""
    # when: 2026-10-01 00:05에 기준 월 없이 저장한다
    result = await _use_case(env).execute()

    # then: 저장된 스냅숏의 기준 월은 2026-09이고 생성 시각은 실행 시각이다
    assert result.period == SEPT
    stored = await _stored(env)
    assert stored is not None
    assert stored.period == SEPT
    assert stored.taken_at == RUN_AT


@pytest.mark.parametrize(
    ("run_at", "expected"),
    [
        (local(2026, 10, 1, 0, 5), YearMonth(2026, 9)),
        (local(2026, 10, 31, 23, 30), YearMonth(2026, 9)),
        (local(2027, 1, 1, 0, 5), YearMonth(2026, 12)),
    ],
)
async def test_default_target_is_the_previous_month_of_the_business_date(
    env: DealEnv, run_at: datetime, expected: YearMonth
) -> None:
    """대상 기준 월을 정하지 않으면 업무 날짜의 전월이다

    테스트 코드: FC-019
    """
    # given: 월초·말일 밤·연초의 실행 시각(서버 로컬)
    clock = FixedClock(run_at)
    # when: 기준 월 없이 저장한다
    result = await _use_case(env, clock).execute()
    # then: 기준 월은 업무 날짜의 전월이다
    assert result.period == expected


async def test_cells_group_every_deal_by_revenue_year_month_owner_and_forecast(
    env: DealEnv,
) -> None:
    """스냅숏 셀은 모든 Deal을 연·월·담당자·Forecast key로 묶고 Lost도 담는다.

    테스트 코드: FC-017
    """
    # given: KIM·LEE의 여러 달 Deal(Lost, 기간 밖, 2025년 8월 포함)
    kim, lee = await given_kim_and_lee_deals(env)
    # when: RUN 시각에 기준 월을 정하지 않고 저장한다
    result = await _use_case(env).execute()
    # then: 연·월·담당자·key별 셀이 따로 있고(Lost, 2025-08 포함) 셀에는 코드 이름이 없다
    stored = await _stored(env)
    assert stored is not None
    assert cell_keys(stored.cells) == {
        (2026, 8, kim, "pipeline", 2, 140),
        (2026, 8, kim, "won", 1, 500),
        (2026, 8, kim, "lost", 1, 999),
        (2026, 9, kim, "commit", 1, 7),
        (2026, 11, kim, "pipeline", 1, 5000),
        (2026, 9, lee, "best", 1, 30),
        (2025, 8, kim, "pipeline", 1, 1),
    }
    assert result.cell_count == 7
    assert not hasattr(stored.cells[0], "forecast_name")


async def test_columns_are_every_forecast_code_at_the_time_of_the_run(env: DealEnv) -> None:
    """스냅숏 열은 실행 시점의 Forecast 코드 전부(Lost·Deal 없는 코드 포함)다.

    테스트 코드: FC-018
    """
    # given: 코드 "Verbal"을 추가하고 commit 이름·순서를 바꾼 뒤 Deal은 pipeline 1건뿐
    await env.uow.codes.add(make_code(CodeKind.FORECAST, key="verbal", name="Verbal", order=99))
    commit = next(c for c in await env.uow.codes.list(CodeKind.FORECAST) if c.key.value == "commit")
    commit.rename("확정", env.clock.now())
    commit.place(10, env.clock.now())
    await env.uow.codes.update(commit)
    await new_deal(env, "pipeline", 1)
    # when: 스냅숏을 저장한다
    await _use_case(env).execute()
    # then: 열은 lost·Verbal을 포함한 모든 코드의 key·실행 시점 이름·outcome·order다
    stored = await _stored(env)
    assert stored is not None
    codes = await env.uow.codes.list(CodeKind.FORECAST)
    assert [(c.key, c.name, c.outcome, c.order) for c in stored.columns] == [
        (code.key.value, code.name, code.outcome, code.order) for code in codes
    ]
    by_key = {c.key: c for c in stored.columns}
    assert by_key["commit"].name == "확정"
    assert by_key["verbal"].outcome is ForecastOutcome.OPEN
    assert by_key["lost"].outcome is ForecastOutcome.LOST
    assert by_key["best"].name == "Best"  # Deal이 없는 코드도 열이다


async def test_rerun_replaces_the_whole_snapshot_of_the_month_and_keeps_other_months(
    env: DealEnv,
) -> None:
    """같은 기준 월을 다시 저장하면 통째로 바꾸고 다른 기준 월은 그대로다.

    테스트 코드: FC-020
    """
    # given: RUN 시각의 2026-09 스냅숏과 2026-08 스냅숏, 그 뒤 Deal 삭제·추가와 코드 이름 변경
    aug_taken = local(2026, 9, 1, 0, 5)
    await store_snapshot(env, YearMonth(2026, 8), aug_taken, cell(2026, 7, amount=3))
    removed = await env.new_deal(
        forecast_key="pipeline",
        status_key="prospecting",
        revenue_amount=100,
        revenue_date=date(2026, 8, 15),
    )
    first = await _use_case(env).execute()
    await env.uow.deals.delete(removed.item.deal.id)
    await new_deal(env, "commit", 7)
    commit = next(c for c in await env.uow.codes.list(CodeKind.FORECAST) if c.key.value == "commit")
    commit.rename("확정", env.clock.now())
    await env.uow.codes.update(commit)
    # when: LATER 시각에 기준 월 2026-09를 다시 저장한다
    later = FixedClock(local(2026, 10, 1, 9, 0))
    result = await _use_case(env, later).execute(SEPT)
    # then: 첫 결과는 replaced false·RUN, 이번은 replaced true이고 2026-09는 새 값 하나뿐이다
    assert (first.replaced, first.taken_at) == (False, RUN_AT)
    assert result.replaced is True
    stored = await _stored(env)
    assert stored is not None
    assert [info.period for info in await env.uow.forecast_snapshots.list_periods()] == [
        SEPT,
        YearMonth(2026, 8),
    ]
    assert stored.taken_at == later.now()
    assert cell_keys(stored.cells) == {(2026, 8, OWNER_ID, "commit", 1, 7)}
    assert {c.key: c.name for c in stored.columns}["commit"] == "확정"
    # then: 2026-08 스냅숏은 그대로다
    august = await _stored(env, YearMonth(2026, 8))
    assert august is not None
    assert august.taken_at == aug_taken
    assert cell_keys(august.cells) == {(2026, 7, OWNER_ID, "pipeline", 1, 3)}


async def test_snapshot_includes_lost_cells(env: DealEnv) -> None:
    """Lost Deal도 셀로 저장한다"""
    # given: Lost Deal 1건
    await new_deal(env, "lost", 999, date(2026, 11, 1))

    # when: 스냅숏을 저장한다
    await _use_case(env).execute()

    # then: Lost 셀이 저장돼 있다
    stored = await _stored(env)
    assert stored is not None
    assert cell_keys(stored.cells) == {(2026, 11, OWNER_ID, "lost", 1, 999)}


async def test_cells_carry_no_code_attributes_only_the_key(env: DealEnv) -> None:
    """셀에는 코드 key만 있고 이름 같은 코드 속성은 없다"""
    # given: commit Deal 1건
    await new_deal(env, "commit", 10)

    # when: 스냅숏을 저장한다
    await _use_case(env).execute()

    # then: 셀에 forecast_key만 있고 이름 속성은 없다
    stored = await _stored(env)
    assert stored is not None
    assert stored.cells[0].forecast_key == "commit"
    assert not hasattr(stored.cells[0], "forecast_name")


async def test_snapshot_stores_the_whole_forecast_code_list_as_columns(env: DealEnv) -> None:
    """열은 저장 시점의 Forecast 코드 목록 전체(outcome 포함)다"""
    # given: 기본 Forecast 코드 목록
    codes = await env.uow.codes.list(CodeKind.FORECAST)

    # when: 스냅숏을 저장한다
    await _use_case(env).execute()

    # then: 열이 코드 목록과 같고 won·lost·commit의 outcome이 맞다
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
    """Deal이 없는 코드도 열로 저장한다"""
    # given: pipeline Deal 1건만 있다
    await new_deal(env, "pipeline", 100)

    # when: 스냅숏을 저장한다
    await _use_case(env).execute()

    # then: 셀은 pipeline 하나이고 열에는 모든 기본 코드가 있다
    stored = await _stored(env)
    assert stored is not None
    assert cell_keys(stored.cells) == {(2026, 8, OWNER_ID, "pipeline", 1, 100)}
    assert {"pipeline", "best", "most_likely", "commit", "won", "lost"} <= {
        c.key for c in stored.columns
    }


async def test_a_code_added_before_the_run_is_stored_as_a_column(env: DealEnv) -> None:
    """실행 전에 추가한 코드도 열로 저장한다"""
    # given: 실행 전에 추가한 코드 "Verbal"
    await env.uow.codes.add(make_code(CodeKind.FORECAST, key="verbal", name="Verbal", order=99))

    # when: 스냅숏을 저장한다
    await _use_case(env).execute()

    # then: verbal 열이 이름과 함께 저장된다
    stored = await _stored(env)
    assert stored is not None
    assert {c.key: c.name for c in stored.columns}["verbal"] == "Verbal"


async def test_names_and_order_in_the_snapshot_are_those_at_the_time_of_the_run(
    env: DealEnv,
) -> None:
    """저장된 열의 이름·순서는 실행 시점 값이고 이후 변경에 영향받지 않는다"""
    # given: commit 이름을 "확정"으로 바꾼 상태
    await new_deal(env, "commit", 10)
    codes = {c.key.value: c for c in await env.uow.codes.list(CodeKind.FORECAST)}
    commit = codes["commit"]
    commit.rename("확정", env.clock.now())
    await env.uow.codes.update(commit)

    # when: 스냅숏을 저장한다
    await _use_case(env).execute()
    # when: 저장 뒤 commit 이름을 다시 바꾼다
    commit.rename("다시 바꿈", env.clock.now())  # 스냅숏 이후의 이름 변경은 저장된 값에 영향이 없다
    await env.uow.codes.update(commit)

    # then: 저장된 commit 열 이름은 "확정"이고 순서·다른 열은 그대로다
    stored = await _stored(env)
    assert stored is not None
    by_key = {c.key: c for c in stored.columns}
    assert by_key["commit"].name == "확정"
    assert by_key["commit"].order == commit.order
    assert by_key["won"].name == codes["won"].name


async def test_a_run_without_deals_still_stores_the_columns_and_no_cells(env: DealEnv) -> None:
    """Deal이 하나도 없으면 열만 저장하고 셀은 없다

    테스트 코드: FC-018
    """
    # when: Deal이 없는 상태에서 스냅숏을 저장한다
    result = await _use_case(env).execute()

    # then: 셀은 없고 열은 코드 목록만큼 있으며 셀 수는 0이다
    stored = await _stored(env)
    assert stored is not None
    assert list(stored.cells) == []
    assert len(stored.columns) >= 6
    assert result.cell_count == 0


async def test_first_run_is_not_a_replacement_and_reports_the_run_time(env: DealEnv) -> None:
    """처음 저장은 대체가 아니고 실행 시각을 돌려준다"""
    # when: 처음 저장한다
    result = await _use_case(env).execute()

    # then: replaced false이고 taken_at이 실행 시각이다
    assert result.replaced is False
    assert result.taken_at == RUN_AT


async def test_rerun_replaces_cells_of_the_same_month(env: DealEnv) -> None:
    """다시 저장하면 같은 기준 월의 셀을 새 Deal로 바꾼다"""
    # given: pipeline Deal로 한 번 저장한 뒤 commit Deal 추가
    await new_deal(env, "pipeline", 100)
    first_run = _use_case(env)
    await first_run.execute()
    await new_deal(env, "commit", 7)
    # when: 더 늦은 시각에 다시 저장한다
    later = FixedClock(local(2026, 10, 1, 9, 0))

    result = await _use_case(env, later).execute()

    # then: 셀이 두 Deal이고 생성 시각이 새 시각이며 replaced true다
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
    """다시 저장하면 열도 지금의 코드 목록으로 바뀐다"""
    # given: 한 번 저장한 뒤 commit 이름을 "확정"으로 바꾼 상태
    await _use_case(env).execute()
    commit = next(c for c in await env.uow.codes.list(CodeKind.FORECAST) if c.key.value == "commit")
    commit.rename("확정", env.clock.now())
    await env.uow.codes.update(commit)

    # when: 다시 저장한다
    await _use_case(env, FixedClock(local(2026, 10, 1, 9, 0))).execute()

    # then: commit 열은 하나뿐이고 새 이름이다
    stored = await _stored(env)
    assert stored is not None
    assert {c.key: c.name for c in stored.columns}["commit"] == "확정"
    assert len([c for c in stored.columns if c.key == "commit"]) == 1


async def test_rerun_keeps_a_single_snapshot_for_the_month(env: DealEnv) -> None:
    """같은 기준 월의 스냅숏은 하나만 남는다"""
    # given: 한 번 저장한 상태
    await _use_case(env).execute()
    # when: 같은 기준 월로 다시 저장한다
    await _use_case(env, FixedClock(local(2026, 10, 1, 9, 0))).execute()

    # then: 목록에는 2026-09 하나뿐이다
    periods = await env.uow.forecast_snapshots.list_periods()

    assert [info.period for info in periods] == [SEPT]


async def test_rerun_drops_cells_of_deals_that_no_longer_exist(env: DealEnv) -> None:
    """다시 저장하면 지워진 Deal의 셀은 사라진다"""
    # given: Deal 1건으로 스냅숏을 저장한 뒤 그 Deal을 삭제한 상태
    view = await env.new_deal(
        forecast_key="pipeline",
        status_key="prospecting",
        revenue_amount=100,
        revenue_date=date(2026, 8, 15),
    )
    await _use_case(env).execute()
    await env.uow.deals.delete(view.item.deal.id)

    # when: 다시 저장한다
    await _use_case(env).execute()

    # then: 셀이 없다
    stored = await _stored(env)
    assert stored is not None
    assert list(stored.cells) == []


@pytest.mark.parametrize("target", [YearMonth(2026, 9), YearMonth(2026, 10)])
async def test_previous_and_current_month_can_be_taken_explicitly(
    env: DealEnv, target: YearMonth
) -> None:
    """지정 기준 월은 전월·당월이면 저장된다

    테스트 코드: FC-021
    """
    # when: 업무 날짜 2026-10-15에 전월·당월을 지정해 저장한다
    result = await _use_case(env, FixedClock(local(2026, 10, 15, 12, 0))).execute(target)

    # then: 지정한 기준 월로 저장된다
    assert result.period == target
    assert await _stored(env, target) is not None


async def test_an_older_month_is_refused_and_nothing_is_written(env: DealEnv) -> None:
    """전전월 이전의 지정 기준 월은 거절하고 아무것도 쓰지 않는다

    테스트 코드: FC-021
    """
    # given: Deal 1건
    await new_deal(env, "pipeline", 100)

    # when: 2026-08을 지정해 저장한다
    with pytest.raises(InvalidValueError) as caught:
        await _use_case(env, FixedClock(local(2026, 10, 15, 12, 0))).execute(YearMonth(2026, 8))

    # then: "다시 계산할 수 없습니다" 오류이고 저장된 스냅숏이 없다
    assert str(caught.value) == REFUSED_AUG
    assert list(await env.uow.forecast_snapshots.list_periods()) == []


async def test_a_future_month_is_refused_and_nothing_is_written(env: DealEnv) -> None:
    """다음 달 이후의 지정 기준 월은 거절하고 아무것도 쓰지 않는다

    테스트 코드: FC-021
    """
    # when: 2026-11을 지정해 저장한다
    with pytest.raises(InvalidValueError) as caught:
        await _use_case(env, FixedClock(local(2026, 10, 15, 12, 0))).execute(YearMonth(2026, 11))

    # then: "다시 계산할 수 없습니다" 오류이고 저장된 스냅숏이 없다
    assert str(caught.value) == REFUSED_NOV
    assert list(await env.uow.forecast_snapshots.list_periods()) == []


async def test_a_refused_month_leaves_the_existing_snapshot_untouched(env: DealEnv) -> None:
    """거절된 기준 월의 기존 스냅숏은 그대로다

    테스트 코드: FC-021
    """
    # given: 2026-08 스냅숏이 이미 있다
    taken = local(2026, 9, 1, 0, 5)
    await store_snapshot(env, YearMonth(2026, 8), taken)

    # when: 2026-08을 다시 저장하려 한다
    with pytest.raises(InvalidValueError):
        await _use_case(env, FixedClock(local(2026, 10, 15))).execute(YearMonth(2026, 8))

    # then: 기존 스냅숏의 생성 시각이 그대로다
    stored = await _stored(env, YearMonth(2026, 8))
    assert stored is not None
    assert stored.taken_at == taken


async def test_an_error_while_saving_keeps_the_previous_snapshot(
    env: DealEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    """저장 중 오류가 나면 이전 스냅숏이 그대로 남는다

    테스트 코드: FC-022
    """
    # given: pipeline Deal로 저장한 스냅숏, 그 뒤 commit Deal 추가, 저장 도중 오류를 내는 저장소
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

    # when: 다시 저장한다
    with pytest.raises(RuntimeError, match="disk full"):
        await _use_case(env, FixedClock(local(2026, 10, 1, 9, 0))).execute()

    # then: 오류가 전파되고 스냅숏은 이전 생성 시각·셀 그대로다
    stored = await _stored(env)
    assert stored is not None
    assert stored.taken_at == RUN_AT
    assert cell_keys(stored.cells) == {(2026, 8, OWNER_ID, "pipeline", 1, 100)}
