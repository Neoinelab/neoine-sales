"""GetForecastSnapshotSummary(P6 R2 AC-17): 저장된 스냅숏을 실시간 요약과 같은 모양으로 읽는다.

현재 Deal이 아니라 스냅숏 당시 값이다. 열·이름은 저장된 값, 담당자 표시는 지금의 사용자 정보다.
스냅숏에는 Vendor가 없어 Vendor 조건은 받지 않는다(웹이 막고, 유스케이스도 방어한다).
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.forecast.get_snapshot_summary import GetForecastSnapshotSummary
from app.application.forecast.views import SummaryBasis
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.common.errors import NotFoundError
from app.domain.forecast.period import ForecastPeriod
from app.domain.forecast.snapshot import YearMonth
from app.domain.forecast.summary import Tally
from app.domain.vendor.values import VendorId
from tests.support.ids import new_id
from tests.support.user_ids import OWNER_ID
from tests.unit.application.forecast_snapshot_env import (
    cell,
    column,
    local,
    new_deal,
    new_owner,
    resign,
    store_snapshot,
)

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

SEPT = YearMonth(2026, 9)
TAKEN_AT = local(2026, 10, 1, 0, 5)
Q3 = ForecastPeriod(year=2026, quarter=3)


def _use_case(env: DealEnv) -> GetForecastSnapshotSummary:
    return GetForecastSnapshotSummary(env.uow_factory)


async def test_missing_snapshot_raises_not_found(env: DealEnv) -> None:
    with pytest.raises(NotFoundError):
        await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))


async def test_another_month_is_not_found_even_if_a_snapshot_exists(env: DealEnv) -> None:
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8))

    with pytest.raises(NotFoundError):
        await _use_case(env).execute(YearMonth(2026, 8), ForecastCriteria(period=Q3))


async def test_view_is_a_snapshot_basis_taken_at_and_period(env: DealEnv) -> None:
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8))

    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    assert view.basis is SummaryBasis.SNAPSHOT
    assert view.as_of == TAKEN_AT
    assert str(view.snapshot_period) == "2026-09"
    assert view.period == Q3


async def test_quarter_summary_sums_the_stored_months(env: DealEnv) -> None:
    await store_snapshot(
        env,
        SEPT,
        TAKEN_AT,
        cell(2026, 7, amount=10),
        cell(2026, 8, amount=20),
        cell(2026, 10, amount=999),
    )

    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    assert view.rows[0].cells["pipeline"] == Tally(2, 30)
    assert view.total.open_total == Tally(2, 30)


async def test_summary_reads_the_snapshot_not_the_live_deals(env: DealEnv) -> None:
    await new_deal(env, "commit", 777, date(2026, 8, 15))
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8, amount=5))

    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    assert view.total.open_total == Tally(1, 5)
    assert view.total.cells["commit"] == Tally.ZERO


async def test_columns_carry_the_stored_names_not_the_current_code_names(env: DealEnv) -> None:
    await store_snapshot(
        env,
        SEPT,
        TAKEN_AT,
        cell(2026, 8, "commit"),
        columns=[column("commit", "구 확정")],
    )

    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    assert [(c.key, c.name) for c in view.columns] == [("commit", "구 확정")]


async def test_columns_are_the_stored_code_list_in_stored_order_including_zero_columns(
    env: DealEnv,
) -> None:
    stored = [column("commit", "확정"), column("pipeline"), column("won"), column("lost")]
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8, "pipeline", amount=5), columns=stored)

    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    assert [(c.key, c.name) for c in view.columns] == [
        ("pipeline", "Pipeline"),
        ("commit", "확정"),
        ("won", "Won"),
    ]
    assert view.total.cells["commit"] == Tally.ZERO
    assert view.total.cells["won"] == Tally.ZERO


async def test_a_month_without_any_deal_in_the_selected_period_still_shows_every_column(
    env: DealEnv,
) -> None:
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 1, "pipeline"))

    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    assert [c.key for c in view.columns] == ["pipeline", "best", "most_likely", "commit", "won"]
    assert list(view.rows) == []
    assert view.total.open_total == Tally.ZERO


async def test_lost_cells_are_left_out_of_the_view(env: DealEnv) -> None:
    await store_snapshot(
        env, SEPT, TAKEN_AT, cell(2026, 8, "lost", amount=999), cell(2026, 8, "pipeline", amount=5)
    )

    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    assert "lost" not in [c.key for c in view.columns]
    assert view.total.open_total == Tally(1, 5)


async def test_owner_filter_keeps_only_that_owner(env: DealEnv) -> None:
    other = await new_owner(env, "other")
    await store_snapshot(
        env, SEPT, TAKEN_AT, cell(2026, 8, amount=1), cell(2026, 8, amount=2, owner=other)
    )

    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3, owner_user_id=other))

    assert [row.owner.id for row in view.rows if row.owner] == [other]
    assert view.total.open_total == Tally(1, 2)


async def test_rows_resolve_current_owner_refs_ordered_active_first_then_name(
    env: DealEnv,
) -> None:
    gone = await new_owner(env, "aaa-gone")
    zed = await new_owner(env, "zed")
    amy = await new_owner(env, "amy")
    await store_snapshot(
        env, SEPT, TAKEN_AT, *(cell(2026, 8, owner=owner) for owner in (gone, zed, amy))
    )
    await resign(env, gone)

    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    assert [row.owner.id for row in view.rows if row.owner] == [amy, zed, gone]
    resigned = view.rows[-1].owner
    assert resigned is not None
    assert resigned.resigned is True
    assert resigned.label.endswith("(퇴사)")


async def test_total_row_has_no_owner(env: DealEnv) -> None:
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8, owner=OWNER_ID))

    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    assert view.total.owner is None


async def test_a_vendor_condition_is_refused(env: DealEnv) -> None:
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8))
    criteria = ForecastCriteria(period=Q3, vendor_id=VendorId(new_id()))

    with pytest.raises(ValueError, match=r"\S"):
        await _use_case(env).execute(SEPT, criteria)
