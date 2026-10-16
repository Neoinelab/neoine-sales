"""계획 확정(`finalize_plan`, AC-19·20, R-1): 프런트 `sync.test.ts` T-SYNC-09 이식.

사용자의 답(resolution)을 같은 규칙으로 재검증하고, 함께 바뀐 값과 notice를 만든다.
"""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.sync import (
    CoChange,
    SyncChange,
    SyncField,
    SyncPlan,
    SyncResolution,
    SyncState,
    finalize_plan,
    plan_change,
)
from app.domain.deal.values import RevenueAmount
from tests.support.expect import raises_with
from tests.support.sync_catalog import LOST, OPEN, WON, default_catalog

CATALOG = default_catalog()
REVENUE_REQUIRED = "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."
CHOICE_REQUIRED = "함께 바꿀 값을 선택하세요."
DAY = date(2026, 10, 20)


def _to_contract_completed(current: SyncState = OPEN) -> SyncPlan:
    return plan_change(current, SyncChange(SyncField.STATUS, "contract_completed"), CATALOG)


@pytest.mark.parametrize(
    "resolution",
    [
        None,
        SyncResolution(),
        SyncResolution(revenue_amount=0, revenue_date=DAY),
        SyncResolution(revenue_amount=-5, revenue_date=DAY),
        SyncResolution(revenue_amount=2**53, revenue_date=DAY),
        SyncResolution(revenue_amount=1000),
        SyncResolution(revenue_date=DAY),
    ],
)
def test_closing_without_a_valid_amount_and_date_is_rejected(
    resolution: SyncResolution | None,
) -> None:
    plan = _to_contract_completed()

    with raises_with(InvalidValueError, REVENUE_REQUIRED):
        finalize_plan(OPEN, plan, resolution, CATALOG)


def test_closing_applies_both_values_the_revenue_and_reports_the_co_change() -> None:
    plan = _to_contract_completed()

    applied = finalize_plan(
        OPEN,
        plan,
        SyncResolution(revenue_amount=900_000_000, revenue_date=DAY),
        CATALOG,
    )

    assert applied.state == WON
    assert applied.revenue == (RevenueAmount(900_000_000), DAY)
    assert applied.co_changed == (CoChange(SyncField.FORECAST, "commit", "won"),)
    assert applied.notice == "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."


def test_closing_from_the_forecast_side_reports_the_status_as_the_co_change() -> None:
    plan = plan_change(OPEN, SyncChange(SyncField.FORECAST, "won"), CATALOG)

    applied = finalize_plan(OPEN, plan, SyncResolution(revenue_amount=1, revenue_date=DAY), CATALOG)

    assert applied.state == WON
    assert applied.co_changed == (
        CoChange(SyncField.STATUS, "price_negotiation", "contract_completed"),
    )
    assert applied.notice == "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."


def test_reopening_a_won_deal_requires_a_status_from_the_options() -> None:
    plan = plan_change(WON, SyncChange(SyncField.FORECAST, "commit"), CATALOG)

    for resolution in (None, SyncResolution(), SyncResolution(status_key="contract_completed")):
        with raises_with(InvalidValueError, CHOICE_REQUIRED):
            finalize_plan(WON, plan, resolution, CATALOG)
    with raises_with(InvalidValueError, CHOICE_REQUIRED):
        finalize_plan(WON, plan, SyncResolution(status_key="no_such_status"), CATALOG)


def test_reopening_a_won_deal_changes_the_status_together() -> None:
    plan = plan_change(WON, SyncChange(SyncField.FORECAST, "commit"), CATALOG)

    applied = finalize_plan(WON, plan, SyncResolution(status_key="poc_completed"), CATALOG)

    assert applied.state == SyncState(status_key="poc_completed", forecast_key="commit")
    assert applied.revenue is None
    assert applied.co_changed == (
        CoChange(SyncField.STATUS, "contract_completed", "poc_completed"),
    )
    assert applied.notice == "Status가 'POC완료'로 함께 변경되었습니다."


def test_leaving_contract_completed_requires_a_forecast_other_than_won() -> None:
    plan = plan_change(WON, SyncChange(SyncField.STATUS, "poc_completed"), CATALOG)

    for resolution in (
        None,
        SyncResolution(forecast_key="won"),
        SyncResolution(forecast_key="zzz"),
    ):
        with raises_with(InvalidValueError, CHOICE_REQUIRED):
            finalize_plan(WON, plan, resolution, CATALOG)


def test_leaving_contract_completed_changes_the_forecast_together() -> None:
    plan = plan_change(WON, SyncChange(SyncField.STATUS, "poc_completed"), CATALOG)

    applied = finalize_plan(WON, plan, SyncResolution(forecast_key="best"), CATALOG)

    assert applied.state == SyncState(status_key="poc_completed", forecast_key="best")
    assert applied.co_changed == (CoChange(SyncField.FORECAST, "won", "best"),)
    assert applied.notice == "Forecast가 'Best'로 함께 변경되었습니다."


def test_picking_the_current_status_again_when_leaving_lost_changes_nothing_together() -> None:
    plan = plan_change(LOST, SyncChange(SyncField.FORECAST, "best"), CATALOG)

    applied = finalize_plan(LOST, plan, SyncResolution(status_key="price_negotiation"), CATALOG)

    assert applied.state == SyncState(status_key="price_negotiation", forecast_key="best")
    assert applied.co_changed == ()
    assert applied.notice is None


def test_an_independent_change_ignores_the_resolution() -> None:
    plan = plan_change(OPEN, SyncChange(SyncField.FORECAST, "best"), CATALOG)

    applied = finalize_plan(OPEN, plan, SyncResolution(revenue_amount=5), CATALOG)

    assert applied.state == SyncState(status_key="price_negotiation", forecast_key="best")
    assert (applied.revenue, applied.co_changed, applied.notice) == (None, (), None)


def test_the_same_value_changes_nothing() -> None:
    plan = plan_change(WON, SyncChange(SyncField.FORECAST, "won"), CATALOG)

    applied = finalize_plan(WON, plan, None, CATALOG)

    assert (applied.state, applied.revenue, applied.co_changed, applied.notice) == (
        WON,
        None,
        (),
        None,
    )


def test_the_notice_uses_the_current_code_names_and_their_josa() -> None:
    renamed = default_catalog(contract_completed="수주확정", won="성사")
    plan = plan_change(OPEN, SyncChange(SyncField.STATUS, "contract_completed"), renamed)

    applied = finalize_plan(OPEN, plan, SyncResolution(revenue_amount=1, revenue_date=DAY), renamed)

    assert applied.notice == "Status가 '수주확정'으로, Forecast가 '성사'로 함께 변경되었습니다."
