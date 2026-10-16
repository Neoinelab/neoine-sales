"""Status/Forecast 변경 계획(`plan_change`, AC-19, R-1): 프런트 `sync.test.ts` T-SYNC-01~08 이식.

계획은 부수효과가 없고, 서버는 prompt 문구를 만들지 않는다(Q4).
"""

from app.domain.deal.sync import (
    AskForecast,
    AskStatus,
    Independent,
    NeedRevenue,
    SyncChange,
    SyncField,
    SyncPatch,
    plan_change,
)
from tests.support.sync_catalog import LOST, OPEN, WON, default_catalog

CATALOG = default_catalog()
CLOSING = SyncPatch(status_key="contract_completed", forecast_key="won")


def _status(value: str) -> SyncChange:
    return SyncChange(SyncField.STATUS, value)


def _forecast(value: str) -> SyncChange:
    return SyncChange(SyncField.FORECAST, value)


def test_status_to_contract_completed_also_sets_won_and_needs_revenue() -> None:
    plan = plan_change(OPEN, _status("contract_completed"), CATALOG)

    assert plan == NeedRevenue(patch=CLOSING, requested=SyncField.STATUS)


def test_forecast_to_won_also_sets_contract_completed_and_needs_revenue() -> None:
    plan = plan_change(OPEN, _forecast("won"), CATALOG)

    assert plan == NeedRevenue(patch=CLOSING, requested=SyncField.FORECAST)


def test_lost_to_won_needs_revenue_too() -> None:
    plan = plan_change(LOST, _forecast("won"), CATALOG)

    assert isinstance(plan, NeedRevenue)
    assert plan.patch == CLOSING


def test_forecast_to_lost_keeps_the_status() -> None:
    plan = plan_change(OPEN, _forecast("lost"), CATALOG)

    assert plan == Independent(patch=SyncPatch(forecast_key="lost"))


def test_leaving_won_asks_for_a_status_without_a_default() -> None:
    plan = plan_change(WON, _forecast("commit"), CATALOG)

    assert isinstance(plan, AskStatus)
    assert plan.default_key is None
    assert plan.patch == SyncPatch(forecast_key="commit")
    assert "contract_completed" not in plan.options
    assert len(plan.options) == 6


def test_won_to_lost_also_asks_for_a_status() -> None:
    assert isinstance(plan_change(WON, _forecast("lost"), CATALOG), AskStatus)


def test_leaving_lost_asks_for_a_status_defaulting_to_the_current_one() -> None:
    plan = plan_change(LOST, _forecast("best"), CATALOG)

    assert isinstance(plan, AskStatus)
    assert plan.default_key == "price_negotiation"
    assert "contract_completed" not in plan.options


def test_the_status_options_follow_the_catalog_order() -> None:
    plan = plan_change(WON, _forecast("commit"), CATALOG)

    assert isinstance(plan, AskStatus)
    assert plan.options == (
        "prospecting",
        "introduction",
        "poc_preparation",
        "poc_completed",
        "technical_evaluation",
        "price_negotiation",
    )


def test_leaving_contract_completed_asks_for_a_forecast_without_won() -> None:
    plan = plan_change(WON, _status("poc_completed"), CATALOG)

    assert plan == AskForecast(
        options=("pipeline", "best", "most_likely", "commit", "lost"),
        patch=SyncPatch(status_key="poc_completed"),
    )


def test_other_changes_are_independent() -> None:
    assert plan_change(OPEN, _status("poc_completed"), CATALOG) == Independent(
        patch=SyncPatch(status_key="poc_completed")
    )
    assert plan_change(OPEN, _forecast("best"), CATALOG) == Independent(
        patch=SyncPatch(forecast_key="best")
    )


def test_the_same_value_is_an_independent_change_with_an_empty_patch() -> None:
    assert plan_change(WON, _forecast("won"), CATALOG) == Independent(patch=SyncPatch())
    assert plan_change(WON, _status("contract_completed"), CATALOG) == Independent(
        patch=SyncPatch()
    )
    assert plan_change(LOST, _forecast("lost"), CATALOG) == Independent(patch=SyncPatch())


def test_renamed_codes_do_not_change_the_rules_because_they_work_on_keys() -> None:
    renamed = default_catalog(contract_completed="수주확정", won="성사")

    assert isinstance(plan_change(OPEN, _status("contract_completed"), renamed), NeedRevenue)
    assert isinstance(plan_change(WON, _forecast("best"), renamed), AskStatus)
