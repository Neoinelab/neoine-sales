"""GetForecastSummary: 실시간 집계 유스케이스. Fake UoW 위에서 결과(상태)를 본다.

집계 규칙 자체(Lost 제외·Total 정의)는 도메인 테스트가, 저장소 묶음은 저장소 계약이 검증한다.
여기서는 코드 목록에서 열을 만들고, 조건을 저장소에 전달하고, 담당자 표시 정보를 붙여 정렬하고,
기준 시각·기준(live)을 채우는지 본다.
"""

from datetime import date
from typing import TYPE_CHECKING, Any

from app.application.forecast.get_summary import GetForecastSummary
from app.application.forecast.views import SummaryBasis
from app.application.ports.forecast_repository import ForecastCriteria
from app.domain.code.entities import Code
from app.domain.code.values import CodeId, CodeKey, CodeKind, ForecastOutcome
from app.domain.forecast.period import ForecastPeriod
from app.domain.forecast.summary import Tally
from app.domain.vendor.values import VendorId
from tests.factories_auth import make_user
from tests.support.ids import new_id
from tests.support.user_ids import OWNER_ID, uid

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId
    from tests.unit.application.deal_env import DealEnv

Q4 = ForecastPeriod(year=2026, quarters=frozenset({4}))
IN_Q4 = date(2026, 11, 15)


def _status_for(forecast_key: str) -> str:
    return "contract_completed" if forecast_key == "won" else "prospecting"


async def _deal(
    env: DealEnv,
    forecast: str = "pipeline",
    amount: int = 100,
    **overrides: Any,  # noqa: ANN401
) -> None:
    await env.new_deal(
        forecast_key=forecast,
        status_key=_status_for(forecast),
        revenue_amount=amount,
        revenue_date=overrides.pop("revenue_date", IN_Q4),
        **overrides,
    )


async def _owner(env: DealEnv, login: str) -> UserId:
    owner = uid(login)
    await env.uow.users.add(make_user(login, entity_id=owner))
    return owner


async def _resign(env: DealEnv, owner: UserId) -> None:
    """Deal은 재직자만 담당자로 지정할 수 있으므로 등록한 뒤에 퇴사 처리한다."""
    user = await env.uow.users.get(owner)
    user.resign(env.clock.now())
    await env.uow.users.update(user)


def _use_case(env: DealEnv) -> GetForecastSummary:
    return GetForecastSummary(env.uow_factory, env.clock)


async def _given_kim_lee_park_deals(env: DealEnv) -> tuple[UserId, UserId, UserId]:
    """KIM·LEE·PARK의 2026 Q4 전후 Deal(Lost·기간 밖 포함)을 만든다."""
    kim = await _owner(env, "kim")
    lee = await _owner(env, "lee")
    park = await _owner(env, "park")
    for forecast, amount, day in (
        ("pipeline", 100, date(2026, 11, 15)),
        ("pipeline", 40, date(2026, 10, 1)),
        ("commit", 7, date(2026, 12, 31)),
        ("won", 500, date(2026, 11, 20)),
        ("lost", 999, date(2026, 11, 1)),
        ("pipeline", 5000, date(2026, 9, 30)),
    ):
        await _deal(env, forecast, amount, revenue_date=day, owner_user_id=kim)
    await _deal(env, "most_likely", 30, revenue_date=date(2026, 11, 2), owner_user_id=lee)
    await _deal(env, "lost", 77, revenue_date=date(2026, 11, 3), owner_user_id=park)
    return kim, lee, park


async def test_summary_uses_forecast_codes_in_order(env: DealEnv) -> None:
    """열은 Forecast 코드를 order 순으로 만든다 (Lost 제외)"""
    # when: 2026 Q4 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: 열 key가 기본 코드 순이고 order가 오름차순이다
    assert [c.key for c in view.columns] == ["pipeline", "best", "most_likely", "commit", "won"]
    assert [c.order for c in view.columns] == sorted(c.order for c in view.columns)


async def test_summary_columns_follow_a_renamed_code_and_keep_the_cell_key(env: DealEnv) -> None:
    """코드 이름을 바꿔도 열은 새 이름을 쓰고 셀 key는 그대로다"""
    # given: commit Deal 1건과 commit을 "확정"으로 바꾼 코드
    await _deal(env, "commit", 50)
    commit = next(c for c in await env.uow.codes.list(CodeKind.FORECAST) if c.key.value == "commit")
    commit.rename("확정", env.clock.now())
    await env.uow.codes.update(commit)

    # when: 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: commit 열 이름은 "확정"이고 셀은 그대로 (1, 50)이다
    assert {c.key: c.name for c in view.columns}["commit"] == "확정"
    assert view.rows[0].cells["commit"] == Tally(1, 50)


async def test_summary_has_a_column_for_an_added_open_code(env: DealEnv) -> None:
    """추가한 Open 코드도 마지막 열이 되고 합계 셀은 0이다"""
    # given: order 99의 Open 코드 "Verbal"
    extra = Code.create(
        entity_id=CodeId(new_id()),
        kind=CodeKind.FORECAST,
        name="Verbal",
        key=CodeKey("verbal"),
        order=99,
        probability_hint=None,
        now=env.clock.now(),
    )
    await env.uow.codes.add(extra)

    # when: 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: verbal 열이 마지막이고 합계 셀이 0이다
    assert "verbal" in [c.key for c in view.columns]
    assert [c.key for c in view.columns][-1] == "verbal"
    assert view.total.cells["verbal"] == Tally.ZERO


async def test_summary_counts_deals_by_owner_and_forecast(env: DealEnv) -> None:
    """같은 담당자·코드의 Deal을 건수와 금액으로 합친다"""
    # given: 같은 담당자의 pipeline 2건과 won 1건
    await _deal(env, "pipeline", 100)
    await _deal(env, "pipeline", 40)
    await _deal(env, "won", 500)

    # when: 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: pipeline (2, 140)·won (1, 500)이고 Open 합계는 pipeline 값이다
    row = view.rows[0]
    assert row.owner is not None
    assert row.owner.id == OWNER_ID
    assert row.cells["pipeline"] == Tally(2, 140)
    assert row.cells["won"] == Tally(1, 500)
    assert row.open_total == Tally(2, 140)
    assert view.total.open_total == Tally(2, 140)


async def test_summary_ignores_lost_deals(env: DealEnv) -> None:
    """Lost Deal은 Open 합계에도 열에도 없다"""
    # given: commit 10원과 lost 999원
    await _deal(env, "commit", 10)
    await _deal(env, "lost", 999)

    # when: 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: Open 합계는 (1, 10)이고 lost 열은 없다
    assert view.total.open_total == Tally(1, 10)
    assert "lost" not in [c.key for c in view.columns]


async def test_summary_resolves_owner_refs_including_resigned(env: DealEnv) -> None:
    """퇴사한 담당자도 "(퇴사)" 이름으로 행에 남는다"""
    # given: Deal을 등록한 뒤 퇴사한 담당자
    gone = await _owner(env, "gone")
    await _deal(env, "commit", 10, owner_user_id=gone)
    await _resign(env, gone)

    # when: 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: 행 owner가 resigned이고 라벨이 "(퇴사)"로 끝난다
    assert view.rows[0].owner is not None
    assert view.rows[0].owner.resigned is True
    assert view.rows[0].owner.label.endswith("(퇴사)")


async def test_summary_rows_order_active_first_then_name(env: DealEnv) -> None:
    """행은 재직자 먼저 이름 순, 퇴사자는 마지막이다"""
    # given: 퇴사한 "aaa-gone"과 재직자 zed·amy의 Deal
    gone = await _owner(env, "aaa-gone")
    zed = await _owner(env, "zed")
    amy = await _owner(env, "amy")
    for owner in (gone, zed, amy):
        await _deal(env, "commit", 10, owner_user_id=owner)
    await _resign(env, gone)

    # when: 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: amy, zed, gone 순이다
    assert [row.owner.id for row in view.rows if row.owner] == [amy, zed, gone]


async def test_summary_total_has_no_owner(env: DealEnv) -> None:
    """합계 행에는 담당자가 없다"""
    # given: Deal 1건
    await _deal(env, "commit", 10)

    # when: 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: 합계 행 owner가 없다
    assert view.total.owner is None


async def test_summary_as_of_is_clock_now_and_basis_is_live(env: DealEnv) -> None:
    """실시간 요약은 basis live이고 as_of는 현재 시각이며 기간을 돌려준다

    테스트 코드: FC-010
    """
    # when: Deal이 없는 서버에서 2026 Q4 요약을 읽는다 (전제: 고정 시계)
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: as_of는 시계 현재 시각, basis live, snapshot_period 없음, 기간은 요청한 Q4다
    assert view.as_of == env.clock.now()
    assert view.basis is SummaryBasis.LIVE
    assert view.snapshot_period is None
    assert view.period == Q4


async def test_summary_excludes_deals_outside_the_period(env: DealEnv) -> None:
    """기간 밖 Deal은 양끝을 포함해 이웃 기간을 뺀다"""
    # given: 9/30·12/31·다음 해 1/1의 commit Deal
    await _deal(env, "commit", 10, revenue_date=date(2026, 9, 30))
    await _deal(env, "commit", 20, revenue_date=date(2026, 12, 31))
    await _deal(env, "commit", 40, revenue_date=date(2027, 1, 1))

    # when: 2026 Q4로 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: 12/31 Deal만 (1, 20)으로 들어온다
    assert view.total.open_total == Tally(1, 20)


async def test_summary_passes_the_owner_filter_to_the_tally(env: DealEnv) -> None:
    """담당자 조건은 그 담당자 Deal만 센다"""
    # given: 기본 담당자와 다른 담당자의 commit Deal
    other = await _owner(env, "other")
    await _deal(env, "commit", 10)
    await _deal(env, "commit", 20, owner_user_id=other)

    # when: 다른 담당자 조건으로 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4, owner_user_id=other))

    # then: 그 담당자 행만 있고 합계는 (1, 20)이다
    assert [row.owner.id for row in view.rows if row.owner] == [other]
    assert view.total.open_total == Tally(1, 20)


async def test_summary_passes_the_vendor_filter_to_the_tally(env: DealEnv) -> None:
    """Vendor 조건은 그 Vendor의 Deal만 센다"""
    # given: SAP Deal 10원과 Vendor 없는 Deal 20원
    sap = await env.new_vendor("SAP")
    await _deal(env, "commit", 10, vendor_id=sap.id)
    await _deal(env, "commit", 20)

    # when: SAP 조건으로 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4, vendor_id=sap.id))

    # then: 합계는 (1, 10)이다
    assert view.total.open_total == Tally(1, 10)


async def test_summary_passes_the_month_period_to_the_tally(env: DealEnv) -> None:
    """월 기간은 그 달 Deal만 센다"""
    # given: 10/31과 11/1의 commit Deal
    await _deal(env, "commit", 10, revenue_date=date(2026, 10, 31))
    await _deal(env, "commit", 20, revenue_date=date(2026, 11, 1))

    # when: 2026년 11월로 읽는다
    view = await _use_case(env).execute(
        ForecastCriteria(period=ForecastPeriod(year=2026, month=11))
    )

    # then: 11/1 Deal만 (1, 20)이다
    assert view.total.open_total == Tally(1, 20)


async def test_summary_with_no_deals_has_zero_cells_and_no_rows(env: DealEnv) -> None:
    """Deal이 없으면 모든 열이 0인 합계와 빈 행을 돌려준다

    테스트 코드: FC-009
    """
    # when: Deal이 없는 서버에서 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    # then: 행이 없고 합계 셀·Open 합계가 모두 0이다
    assert list(view.rows) == []
    assert set(view.total.cells) == {c.key for c in view.columns}
    assert view.total.open_total == Tally.ZERO


async def test_summary_groups_cells_by_owner_and_forecast_leaving_out_lost_and_other_periods(
    env: DealEnv,
) -> None:
    """실시간 요약은 담당자·Forecast 코드별 건수·금액이고 Lost와 기간 밖 Deal은 빠진다.

    테스트 코드: FC-002
    """
    # given: KIM·LEE·PARK의 Deal(Lost와 Q4 밖 Deal 포함)
    kim, lee, _ = await _given_kim_lee_park_deals(env)
    # when: 2026 Q4로 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))
    # then: KIM·LEE 행의 셀에 Q4 Open·Won Deal만 들어가고 5000원·Lost 금액은 어디에도 없다
    by_owner = {row.owner.id: row for row in view.rows if row.owner}
    assert {key: (t.count, t.amount) for key, t in by_owner[kim].cells.items()} == {
        "pipeline": (2, 140),
        "best": (0, 0),
        "most_likely": (0, 0),
        "commit": (1, 7),
        "won": (1, 500),
    }
    assert by_owner[lee].cells["most_likely"] == Tally(1, 30)
    assert by_owner[lee].cells["pipeline"] == Tally.ZERO


async def test_summary_totals_open_columns_only_and_the_total_row_sums_the_owner_rows(
    env: DealEnv,
) -> None:
    """Total(Open)은 Open 열 합이고 Won·Lost를 빼며 합계 행은 담당자 행의 합이다.

    테스트 코드: FC-003
    """
    # given: KIM·LEE·PARK의 Deal
    kim, lee, _ = await _given_kim_lee_park_deals(env)
    # when: 2026 Q4로 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))
    # then: 행별 Open 합계, 합계 행 셀·Open 합계가 문서와 같고 합계 행 owner는 없다
    by_owner = {row.owner.id: row for row in view.rows if row.owner}
    assert by_owner[kim].open_total == Tally(3, 147)
    assert by_owner[lee].open_total == Tally(1, 30)
    assert view.total.cells["pipeline"] == Tally(2, 140)
    assert view.total.cells["commit"] == Tally(1, 7)
    assert view.total.cells["most_likely"] == Tally(1, 30)
    assert view.total.cells["won"] == Tally(1, 500)
    assert view.total.open_total == Tally(4, 177)
    assert view.total.owner is None


async def test_summary_has_no_row_for_an_owner_with_only_lost_deals(env: DealEnv) -> None:
    """Lost만 있는 담당자는 행이 없다.

    테스트 코드: FC-004
    """
    # given: KIM·LEE의 Open Deal과 Lost Deal만 가진 PARK
    kim, lee, park = await _given_kim_lee_park_deals(env)
    # when: 2026 Q4로 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))
    # then: 행의 담당자는 KIM·LEE뿐이고 PARK 행이 없다
    owners = {row.owner.id for row in view.rows if row.owner}
    assert owners == {kim, lee}
    assert park not in owners


async def test_summary_keeps_a_resigned_owner_after_the_active_ones(env: DealEnv) -> None:
    """퇴사한 담당자도 행에 남고 재직자 다음에 이름 순으로 온다.

    테스트 코드: FC-005
    """
    # given: 이름이 사전순으로 앞서는 "aaa-gone"과 KIM의 Deal, 그 뒤 "aaa-gone" 퇴사
    gone = await _owner(env, "aaa-gone")
    kim = await _owner(env, "kim")
    await _deal(env, "commit", 10, owner_user_id=gone)
    await _deal(env, "commit", 20, owner_user_id=kim)
    await _resign(env, gone)
    # when: 2026 Q4로 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))
    # then: 행 순서는 KIM, aaa-gone이고 퇴사자는 resigned·"(퇴사)" 라벨이다
    owners = [row.owner for row in view.rows]
    assert [o.id for o in owners if o] == [kim, gone]
    assert owners[0] is not None
    assert owners[0].resigned is False
    assert owners[1] is not None
    assert owners[1].resigned is True
    assert owners[1].label == "aaa-gone(퇴사)"


async def test_summary_columns_follow_renamed_and_added_codes_and_cells_follow_the_columns(
    env: DealEnv,
) -> None:
    """열은 Lost를 뺀 코드 order 순이고 바꾼 이름·추가한 Open 코드를 따르며 셀은 열 순서의 목록이다.

    테스트 코드: FC-006
    """
    # given: 코드 "Verbal"(Open)을 추가하고 commit 이름을 "확정"으로 바꾼 뒤 KIM의 commit 7·Verbal 3
    kim = await _owner(env, "kim")
    verbal = Code.create(
        entity_id=CodeId(new_id()),
        kind=CodeKind.FORECAST,
        name="Verbal",
        key=CodeKey("verbal"),
        order=99,
        probability_hint=None,
        now=env.clock.now(),
    )
    await env.uow.codes.add(verbal)
    commit = next(c for c in await env.uow.codes.list(CodeKind.FORECAST) if c.key.value == "commit")
    commit.rename("확정", env.clock.now())
    await env.uow.codes.update(commit)
    await _deal(env, "commit", 7, owner_user_id=kim)
    await _deal(env, "verbal", 3, owner_user_id=kim)
    # when: 2026 Q4로 요약을 읽는다
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))
    # then: 열은 order 순·Lost 없음·새 이름·Open 열이고, KIM 행 셀 순서는 열 순서와 같다
    assert [c.key for c in view.columns] == [
        "pipeline",
        "best",
        "most_likely",
        "commit",
        "won",
        "verbal",
    ]
    by_key = {c.key: c for c in view.columns}
    assert by_key["commit"].name == "확정"
    assert by_key["verbal"].outcome is ForecastOutcome.OPEN
    row = view.rows[0]
    assert (row.cells["commit"], row.cells["verbal"]) == (Tally(1, 7), Tally(1, 3))
    assert row.open_total == Tally(2, 10)
    assert list(row.cells) == [c.key for c in view.columns]
    assert list(view.total.cells) == [c.key for c in view.columns]


async def test_summary_filters_by_owner_and_vendor_conditions(env: DealEnv) -> None:
    """owner_user_id·vendor_id는 그 담당자·Vendor의 Deal만 센다.

    테스트 코드: FC-008
    """
    # given: Vendor SAP, KIM의 SAP Deal 1원·Vendor 없는 Deal 2원, LEE의 SAP Deal 4원
    sap = await env.new_vendor("SAP")
    kim = await _owner(env, "kim")
    lee = await _owner(env, "lee")
    year = ForecastPeriod(year=2026)
    await _deal(env, "pipeline", 1, owner_user_id=kim, vendor_id=sap.id)
    await _deal(env, "pipeline", 2, owner_user_id=kim)
    await _deal(env, "pipeline", 4, owner_user_id=lee, vendor_id=sap.id)
    # when: KIM+SAP 조건으로 읽는다
    by_owner_and_vendor = await _use_case(env).execute(
        ForecastCriteria(period=year, owner_user_id=kim, vendor_id=sap.id)
    )
    # then: 행은 KIM 하나이고 pipeline (1, 1)이다
    assert [row.owner.id for row in by_owner_and_vendor.rows if row.owner] == [kim]
    assert by_owner_and_vendor.total.cells["pipeline"] == Tally(1, 1)
    # when: 없는 Vendor id로 읽는다
    unknown_vendor = await _use_case(env).execute(
        ForecastCriteria(period=year, vendor_id=VendorId(new_id()))
    )
    # then: 행이 없고 합계가 0이다
    assert list(unknown_vendor.rows) == []
    assert unknown_vendor.total.open_total == Tally.ZERO
    # when: Vendor 조건 없이 읽는다
    everything = await _use_case(env).execute(ForecastCriteria(period=year))
    # then: Vendor 없는 Deal도 세어 합계 금액이 7이다
    assert everything.total.open_total == Tally(3, 7)
