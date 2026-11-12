"""GetForecastSnapshotSummary: 저장된 스냅숏을 실시간 요약과 같은 모양으로 읽는다.

현재 Deal이 아니라 스냅숏 당시 값이다. 열·이름은 저장된 값, 담당자 표시는 지금의 사용자 정보다.
스냅숏에는 Vendor가 없어 Vendor 조건은 받지 않는다(웹이 막고, 유스케이스도 방어한다).
"""

from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from app.application.forecast.get_snapshot_summary import GetForecastSnapshotSummary
from app.application.forecast.get_summary import GetForecastSummary
from app.application.forecast.take_snapshot import TakeForecastSnapshot
from app.application.forecast.views import SummaryBasis
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.code.entities import Code
from app.domain.code.values import CodeId, CodeKey, CodeKind
from app.domain.common.errors import NotFoundError
from app.domain.forecast.period import ForecastPeriod
from app.domain.forecast.snapshot import YearMonth
from app.domain.forecast.summary import Tally
from app.domain.vendor.values import VendorId
from tests.fakes.unit_of_work import FixedClock
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
    from app.application.deal.dto import DealView
    from app.application.forecast.views import ForecastSummaryView
    from app.domain.user.value_objects import UserId
    from tests.unit.application.deal_env import DealEnv

SEPT = YearMonth(2026, 9)
TAKEN_AT = local(2026, 10, 1, 0, 5)
Q3 = ForecastPeriod(year=2026, quarters=frozenset({3}))


DEFAULT_KEYS = ["pipeline", "best", "most_likely", "commit", "won"]


def _use_case(env: DealEnv) -> GetForecastSnapshotSummary:
    return GetForecastSnapshotSummary(env.uow_factory)


async def _take_september(env: DealEnv) -> None:
    """실제 저장 유스케이스로 RUN 시각(2026-10-01 00:05)에 2026-09 스냅숏을 만든다."""
    await TakeForecastSnapshot(env.uow_factory, FixedClock(TAKEN_AT)).execute()


async def _given_kim_and_lee_september_snapshot(
    env: DealEnv,
) -> tuple[UserId, UserId, DealView, DealView]:
    """KIM: pipeline 100(08-15)·commit 7(09-30), LEE: best 30(09-02)로 2026-09 스냅숏을 만든다."""
    kim = await new_owner(env, "kim")
    lee = await new_owner(env, "lee")
    pipeline = await env.new_deal(**_fields("pipeline", 100, date(2026, 8, 15), kim))
    commit = await env.new_deal(**_fields("commit", 7, date(2026, 9, 30), kim))
    await env.new_deal(**_fields("best", 30, date(2026, 9, 2), lee))
    await _take_september(env)
    return kim, lee, pipeline, commit


def _fields(forecast: str, amount: int, day: date, owner: UserId) -> dict[str, Any]:
    return {
        "forecast_key": forecast,
        "status_key": "prospecting",
        "revenue_amount": amount,
        "revenue_date": day,
        "owner_user_id": owner,
    }


def _row_cells(view: ForecastSummaryView, owner: UserId) -> dict[str, Tally]:
    row = next(r for r in view.rows if r.owner and r.owner.id == owner)
    return {key: tally for key, tally in row.cells.items() if tally != Tally.ZERO}


async def test_snapshot_summary_has_the_live_shape_with_snapshot_basis(env: DealEnv) -> None:
    """스냅숏 요약은 실시간과 같은 모양이고 basis snapshot·생성 시각·기준 월을 담는다.

    테스트 코드: FC-026
    """
    # given: RUN 시각에 만든 2026-09 스냅숏(KIM pipeline 100·commit 7, LEE best 30)
    kim, lee, _, _ = await _given_kim_and_lee_september_snapshot(env)
    # when: 2026 Q3로 요약을 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))
    # then: basis snapshot, 기준 월·생성 시각, 기본 열 5개, 행은 KIM·LEE이고 KIM 셀이 저장값이다
    assert view.basis is SummaryBasis.SNAPSHOT
    assert str(view.snapshot_period) == "2026-09"
    assert view.as_of == TAKEN_AT
    assert [c.key for c in view.columns] == DEFAULT_KEYS
    assert [row.owner.id for row in view.rows if row.owner] == [kim, lee]
    assert _row_cells(view, kim) == {"pipeline": Tally(1, 100), "commit": Tally(1, 7)}
    assert view.rows[0].open_total == Tally(2, 107)
    assert view.total.owner is None


async def test_snapshot_values_do_not_follow_deals_added_or_deleted_after_saving(
    env: DealEnv,
) -> None:
    """스냅숏 값은 저장 뒤 Deal을 추가·삭제해도 바뀌지 않는다.

    테스트 코드: FC-027
    """
    # given: 2026-09 스냅숏 저장 뒤 KIM pipeline 900(08-20) 추가와 기존 commit Deal 삭제
    kim, _, _, commit = await _given_kim_and_lee_september_snapshot(env)
    await env.new_deal(**_fields("pipeline", 900, date(2026, 8, 20), kim))
    await env.uow.deals.delete(commit.item.deal.id)
    # when: 스냅숏 요약과 실시간 요약을 2026 Q3로 읽는다
    snapshot = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))
    live = await GetForecastSummary(env.uow_factory, env.clock).execute(ForecastCriteria(period=Q3))
    # then: 스냅숏 KIM 행은 저장 당시 값 그대로이고 실시간 KIM 행은 추가·삭제가 반영된다
    assert _row_cells(snapshot, kim) == {"pipeline": Tally(1, 100), "commit": Tally(1, 7)}
    assert _row_cells(live, kim) == {"pipeline": Tally(2, 1000)}


async def test_snapshot_columns_are_the_stored_code_list_not_the_current_codes(
    env: DealEnv,
) -> None:
    """스냅숏 열은 저장된 코드 목록이다(옛 이름, 뒤에 추가한 코드 없음, 0건 열 포함).

    테스트 코드: FC-028
    """
    # given: KIM pipeline 5만으로 저장한 뒤 commit을 "확정"으로 바꾸고 코드 "Verbal" 추가
    kim = await new_owner(env, "kim")
    await env.new_deal(**_fields("pipeline", 5, date(2026, 8, 15), kim))
    await _take_september(env)
    commit = next(c for c in await env.uow.codes.list(CodeKind.FORECAST) if c.key.value == "commit")
    commit.rename("확정", env.clock.now())
    await env.uow.codes.update(commit)
    await env.uow.codes.add(
        Code.create(
            entity_id=CodeId(new_id()),
            kind=CodeKind.FORECAST,
            name="Verbal",
            key=CodeKey("verbal"),
            order=99,
            probability_hint=None,
            now=env.clock.now(),
        )
    )
    # when: 스냅숏 요약과 실시간 요약을 읽는다
    snapshot = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))
    live = await GetForecastSummary(env.uow_factory, env.clock).execute(ForecastCriteria(period=Q3))
    # then: 스냅숏 열은 저장 순서이고 commit은 옛 이름, Verbal은 없으며 Deal 없던 열도 0건으로 있다
    assert [c.key for c in snapshot.columns] == DEFAULT_KEYS
    assert {c.key: c.name for c in snapshot.columns}["commit"] == "Commit"
    assert snapshot.total.cells["commit"] == Tally.ZERO
    assert snapshot.total.cells["best"] == Tally.ZERO
    # then: 실시간 commit 이름은 "확정"이다
    assert {c.key: c.name for c in live.columns}["commit"] == "확정"


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        (ForecastPeriod(year=2026, quarters=frozenset({3})), Tally(3, 137)),
        (ForecastPeriod(year=2026, month=8), Tally(1, 100)),
        (ForecastPeriod(year=2026, month=9), Tally(2, 37)),
        (ForecastPeriod(year=2026, quarters=frozenset({4})), Tally.ZERO),
        (ForecastPeriod(year=2025), Tally.ZERO),
        (ForecastPeriod(year=2026, quarters=frozenset({1})), Tally.ZERO),
    ],
)
async def test_snapshot_summary_collects_the_stored_monthly_cells_by_period(
    env: DealEnv, period: ForecastPeriod, expected: Tally
) -> None:
    """스냅숏 요약은 저장된 월별 셀을 기간으로 모으고 비어도 열은 모두 나온다.

    테스트 코드: FC-029
    """
    # given: KIM pipeline 100(8월)·commit 7(9월), LEE best 30(9월)의 2026-09 스냅숏
    await _given_kim_and_lee_september_snapshot(env)
    # when: 연·분기·월 기간으로 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=period))
    # then: Open 합계가 기간에 드는 셀의 합이고 열은 모두 나오며 비면 행이 없다
    assert view.total.open_total == expected
    assert [c.key for c in view.columns] == DEFAULT_KEYS
    assert (list(view.rows) == []) is (expected == Tally.ZERO)


async def test_snapshot_summary_owner_condition_keeps_only_that_owner(env: DealEnv) -> None:
    """스냅숏 요약의 owner_user_id는 그 담당자 행만 남긴다.

    테스트 코드: FC-030
    """
    # given: KIM·LEE의 2026-09 스냅숏
    _, lee, _, _ = await _given_kim_and_lee_september_snapshot(env)
    # when: 담당자 LEE 조건으로 읽는다
    view = await _use_case(env).execute(
        SEPT, ForecastCriteria(period=ForecastPeriod(year=2026), owner_user_id=lee)
    )
    # then: 행은 LEE 하나이고 Open 합계는 (1, 30)이다
    assert [row.owner.id for row in view.rows if row.owner] == [lee]
    assert view.total.open_total == Tally(1, 30)


async def test_snapshot_summary_leaves_out_lost_cells_columns_and_owners(env: DealEnv) -> None:
    """스냅숏의 Lost 셀은 열·합계·행에 나오지 않는다.

    테스트 코드: FC-031
    """
    # given: KIM pipeline 5·lost 999, PARK lost 77(모두 2026-08)로 만든 2026-09 스냅숏
    kim = await new_owner(env, "kim")
    park = await new_owner(env, "park")
    await env.new_deal(**_fields("pipeline", 5, date(2026, 8, 15), kim))
    await env.new_deal(**_fields("lost", 999, date(2026, 8, 16), kim))
    await env.new_deal(**_fields("lost", 77, date(2026, 8, 17), park))
    await _take_september(env)
    # when: 2026년 스냅숏 요약을 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=ForecastPeriod(year=2026)))
    # then: 행은 KIM 하나, 열에 lost가 없고 Open 합계는 (1, 5)다
    assert [row.owner.id for row in view.rows if row.owner] == [kim]
    assert "lost" not in [c.key for c in view.columns]
    assert view.total.open_total == Tally(1, 5)


async def test_snapshot_rows_show_current_user_info_active_first_then_name(env: DealEnv) -> None:
    """스냅숏 행의 담당자는 지금 사용자 정보이고 재직자 먼저 이름 순이다.

    테스트 코드: FC-032
    """
    # given: KIM·LEE 셀이 있는 스냅숏, 그 뒤 LEE가 퇴사 처리됨
    kim, lee, _, _ = await _given_kim_and_lee_september_snapshot(env)
    await resign(env, lee)
    # when: 스냅숏 요약을 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))
    # then: 행 순서는 KIM, LEE이고 LEE는 resigned·"(퇴사)" 라벨이다
    assert [row.owner.id for row in view.rows if row.owner] == [kim, lee]
    lee_ref = view.rows[1].owner
    assert lee_ref is not None
    assert lee_ref.resigned is True
    assert lee_ref.label.endswith("(퇴사)")


async def test_missing_snapshot_raises_not_found(env: DealEnv) -> None:
    """저장된 스냅숏이 없으면 NotFoundError다

    테스트 코드: FC-033
    """
    # when·then: 스냅숏이 없는 기준 월을 읽으면 NotFoundError다
    with pytest.raises(NotFoundError):
        await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))


async def test_another_month_is_not_found_even_if_a_snapshot_exists(env: DealEnv) -> None:
    """다른 기준 월의 스냅숏만 있으면 요청한 기준 월은 NotFoundError다

    테스트 코드: FC-033
    """
    # given: 2026-09 스냅숏만 있다
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8))

    # when·then: 2026-08을 읽으면 NotFoundError다
    with pytest.raises(NotFoundError):
        await _use_case(env).execute(YearMonth(2026, 8), ForecastCriteria(period=Q3))


async def test_view_is_a_snapshot_basis_taken_at_and_period(env: DealEnv) -> None:
    """요약은 snapshot 기준이고 생성 시각·기준 월·요청 기간을 담는다"""
    # given: 8월 셀이 있는 2026-09 스냅숏
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8))

    # when: Q3로 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    # then: basis snapshot, as_of는 생성 시각, 기준 월 2026-09, 기간은 요청한 Q3다
    assert view.basis is SummaryBasis.SNAPSHOT
    assert view.as_of == TAKEN_AT
    assert str(view.snapshot_period) == "2026-09"
    assert view.period == Q3


async def test_quarter_summary_sums_the_stored_months(env: DealEnv) -> None:
    """분기 요약은 그 분기의 저장된 월 셀만 합친다"""
    # given: 7월·8월·10월 셀이 있는 스냅숏
    await store_snapshot(
        env,
        SEPT,
        TAKEN_AT,
        cell(2026, 7, amount=10),
        cell(2026, 8, amount=20),
        cell(2026, 10, amount=999),
    )

    # when: Q3로 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    # then: 7·8월 셀만 합쳐 (2, 30)이다
    assert view.rows[0].cells["pipeline"] == Tally(2, 30)
    assert view.total.open_total == Tally(2, 30)


async def test_summary_reads_the_snapshot_not_the_live_deals(env: DealEnv) -> None:
    """요약은 현재 Deal이 아니라 저장된 셀을 읽는다"""
    # given: 현재 commit Deal 777원과 저장된 pipeline 셀 5원
    await new_deal(env, "commit", 777, date(2026, 8, 15))
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8, amount=5))

    # when: 스냅숏 요약을 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    # then: 저장된 값 (1, 5)이고 commit 셀은 0이다
    assert view.total.open_total == Tally(1, 5)
    assert view.total.cells["commit"] == Tally.ZERO


async def test_columns_carry_the_stored_names_not_the_current_code_names(env: DealEnv) -> None:
    """열 이름은 저장된 이름이다"""
    # given: commit 이름이 "구 확정"으로 저장된 스냅숏
    await store_snapshot(
        env,
        SEPT,
        TAKEN_AT,
        cell(2026, 8, "commit"),
        columns=[column("commit", "구 확정")],
    )

    # when: 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    # then: 열 이름이 저장된 "구 확정"이다
    assert [(c.key, c.name) for c in view.columns] == [("commit", "구 확정")]


async def test_columns_are_the_stored_code_list_in_stored_order_including_zero_columns(
    env: DealEnv,
) -> None:
    """열은 저장된 코드 목록을 저장 order 순으로 보이고 Deal 없던 열도 0건으로 포함한다"""
    # given: commit·pipeline·won·lost 열만 저장된 스냅숏(셀은 pipeline뿐)
    stored = [column("commit", "확정"), column("pipeline"), column("won"), column("lost")]
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8, "pipeline", amount=5), columns=stored)

    # when: 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    # then: Lost를 뺀 pipeline·commit·won 순이고 Deal 없던 열은 0건이다
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
    """선택 기간에 셀이 없어도 열은 모두 나오고 행은 없다"""
    # given: 1월 셀만 있는 스냅숏
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 1, "pipeline"))

    # when: Q3로 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    # then: 열은 기본 5개이고 행·Open 합계는 비어 있다
    assert [c.key for c in view.columns] == ["pipeline", "best", "most_likely", "commit", "won"]
    assert list(view.rows) == []
    assert view.total.open_total == Tally.ZERO


async def test_lost_cells_are_left_out_of_the_view(env: DealEnv) -> None:
    """Lost 셀은 열과 합계에서 빠진다"""
    # given: Lost 999원과 pipeline 5원 셀이 있는 스냅숏
    await store_snapshot(
        env, SEPT, TAKEN_AT, cell(2026, 8, "lost", amount=999), cell(2026, 8, "pipeline", amount=5)
    )

    # when: 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    # then: lost 열이 없고 Open 합계는 (1, 5)다
    assert "lost" not in [c.key for c in view.columns]
    assert view.total.open_total == Tally(1, 5)


async def test_owner_filter_keeps_only_that_owner(env: DealEnv) -> None:
    """담당자 조건은 그 담당자 셀만 남긴다"""
    # given: 기본 담당자와 다른 담당자의 셀
    other = await new_owner(env, "other")
    await store_snapshot(
        env, SEPT, TAKEN_AT, cell(2026, 8, amount=1), cell(2026, 8, amount=2, owner=other)
    )

    # when: 다른 담당자 조건으로 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3, owner_user_id=other))

    # then: 그 담당자 행만 있고 합계는 (1, 2)다
    assert [row.owner.id for row in view.rows if row.owner] == [other]
    assert view.total.open_total == Tally(1, 2)


async def test_rows_resolve_current_owner_refs_ordered_active_first_then_name(
    env: DealEnv,
) -> None:
    """행은 지금 사용자 정보를 붙이고 재직자 먼저 이름 순이다"""
    # given: 퇴사한 "aaa-gone"과 재직자 zed·amy의 셀
    gone = await new_owner(env, "aaa-gone")
    zed = await new_owner(env, "zed")
    amy = await new_owner(env, "amy")
    await store_snapshot(
        env, SEPT, TAKEN_AT, *(cell(2026, 8, owner=owner) for owner in (gone, zed, amy))
    )
    await resign(env, gone)

    # when: 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    # then: amy, zed, gone 순이고 퇴사자는 "(퇴사)" 라벨이다
    assert [row.owner.id for row in view.rows if row.owner] == [amy, zed, gone]
    resigned = view.rows[-1].owner
    assert resigned is not None
    assert resigned.resigned is True
    assert resigned.label.endswith("(퇴사)")


async def test_total_row_has_no_owner(env: DealEnv) -> None:
    """합계 행에는 담당자가 없다"""
    # given: 셀 1개의 스냅숏
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8, owner=OWNER_ID))

    # when: 읽는다
    view = await _use_case(env).execute(SEPT, ForecastCriteria(period=Q3))

    # then: 합계 행 owner가 없다
    assert view.total.owner is None


async def test_a_vendor_condition_is_refused(env: DealEnv) -> None:
    """스냅숏에는 Vendor가 없어 Vendor 조건은 거절한다"""
    # given: 셀 1개의 스냅숏과 Vendor 조건
    await store_snapshot(env, SEPT, TAKEN_AT, cell(2026, 8))
    criteria = ForecastCriteria(period=Q3, vendor_id=VendorId(new_id()))

    # when·then: Vendor 조건으로 읽으면 ValueError다
    with pytest.raises(ValueError, match=r"\S"):
        await _use_case(env).execute(SEPT, criteria)
