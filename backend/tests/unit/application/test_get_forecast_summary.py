"""GetForecastSummary(P6 R1 AC-1~9): 실시간 집계 유스케이스. Fake UoW 위에서 결과(상태)를 본다.

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
from app.domain.code.values import CodeId, CodeKey, CodeKind
from app.domain.forecast.period import ForecastPeriod
from app.domain.forecast.summary import Tally
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


async def test_summary_uses_forecast_codes_in_order(env: DealEnv) -> None:
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    assert [c.key for c in view.columns] == ["pipeline", "best", "most_likely", "commit", "won"]
    assert [c.order for c in view.columns] == sorted(c.order for c in view.columns)


async def test_summary_columns_follow_a_renamed_code_and_keep_the_cell_key(env: DealEnv) -> None:
    await _deal(env, "commit", 50)
    commit = next(c for c in await env.uow.codes.list(CodeKind.FORECAST) if c.key.value == "commit")
    commit.rename("확정", env.clock.now())
    await env.uow.codes.update(commit)

    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    assert {c.key: c.name for c in view.columns}["commit"] == "확정"
    assert view.rows[0].cells["commit"] == Tally(1, 50)


async def test_summary_has_a_column_for_an_added_open_code(env: DealEnv) -> None:
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

    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    assert "verbal" in [c.key for c in view.columns]
    assert [c.key for c in view.columns][-1] == "verbal"
    assert view.total.cells["verbal"] == Tally.ZERO


async def test_summary_counts_deals_by_owner_and_forecast(env: DealEnv) -> None:
    await _deal(env, "pipeline", 100)
    await _deal(env, "pipeline", 40)
    await _deal(env, "won", 500)

    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    row = view.rows[0]
    assert row.owner is not None
    assert row.owner.id == OWNER_ID
    assert row.cells["pipeline"] == Tally(2, 140)
    assert row.cells["won"] == Tally(1, 500)
    assert row.open_total == Tally(2, 140)
    assert view.total.open_total == Tally(2, 140)


async def test_summary_ignores_lost_deals(env: DealEnv) -> None:
    await _deal(env, "commit", 10)
    await _deal(env, "lost", 999)

    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    assert view.total.open_total == Tally(1, 10)
    assert "lost" not in [c.key for c in view.columns]


async def test_summary_resolves_owner_refs_including_resigned(env: DealEnv) -> None:
    gone = await _owner(env, "gone")
    await _deal(env, "commit", 10, owner_user_id=gone)
    await _resign(env, gone)

    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    assert view.rows[0].owner is not None
    assert view.rows[0].owner.resigned is True
    assert view.rows[0].owner.label.endswith("(퇴사)")


async def test_summary_rows_order_active_first_then_name(env: DealEnv) -> None:
    gone = await _owner(env, "aaa-gone")
    zed = await _owner(env, "zed")
    amy = await _owner(env, "amy")
    for owner in (gone, zed, amy):
        await _deal(env, "commit", 10, owner_user_id=owner)
    await _resign(env, gone)

    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    assert [row.owner.id for row in view.rows if row.owner] == [amy, zed, gone]


async def test_summary_total_has_no_owner(env: DealEnv) -> None:
    await _deal(env, "commit", 10)

    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    assert view.total.owner is None


async def test_summary_as_of_is_clock_now_and_basis_is_live(env: DealEnv) -> None:
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    assert view.as_of == env.clock.now()
    assert view.basis is SummaryBasis.LIVE
    assert view.snapshot_period is None
    assert view.period == Q4


async def test_summary_excludes_deals_outside_the_period(env: DealEnv) -> None:
    await _deal(env, "commit", 10, revenue_date=date(2026, 9, 30))
    await _deal(env, "commit", 20, revenue_date=date(2026, 12, 31))
    await _deal(env, "commit", 40, revenue_date=date(2027, 1, 1))

    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    assert view.total.open_total == Tally(1, 20)


async def test_summary_passes_the_owner_filter_to_the_tally(env: DealEnv) -> None:
    other = await _owner(env, "other")
    await _deal(env, "commit", 10)
    await _deal(env, "commit", 20, owner_user_id=other)

    view = await _use_case(env).execute(ForecastCriteria(period=Q4, owner_user_id=other))

    assert [row.owner.id for row in view.rows if row.owner] == [other]
    assert view.total.open_total == Tally(1, 20)


async def test_summary_passes_the_vendor_filter_to_the_tally(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP")
    await _deal(env, "commit", 10, vendor_id=sap.id)
    await _deal(env, "commit", 20)

    view = await _use_case(env).execute(ForecastCriteria(period=Q4, vendor_id=sap.id))

    assert view.total.open_total == Tally(1, 10)


async def test_summary_passes_the_month_period_to_the_tally(env: DealEnv) -> None:
    await _deal(env, "commit", 10, revenue_date=date(2026, 10, 31))
    await _deal(env, "commit", 20, revenue_date=date(2026, 11, 1))

    view = await _use_case(env).execute(
        ForecastCriteria(period=ForecastPeriod(year=2026, month=11))
    )

    assert view.total.open_total == Tally(1, 20)


async def test_summary_with_no_deals_has_zero_cells_and_no_rows(env: DealEnv) -> None:
    view = await _use_case(env).execute(ForecastCriteria(period=Q4))

    assert list(view.rows) == []
    assert set(view.total.cells) == {c.key for c in view.columns}
    assert view.total.open_total == Tally.ZERO
