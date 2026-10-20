"""순차 동기화(`finalize_sequence`, AC-01~07): 두 번째 변경은 첫 변경 적용 후 상태로 판정한다."""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.sync import (
    SYNC_CONFLICT_MESSAGE,
    SYNC_DUPLICATE_MESSAGE,
    CoChange,
    SyncChange,
    SyncField,
    SyncResolution,
    SyncState,
    SyncStep,
    finalize_plan,
    finalize_sequence,
    plan_change,
)
from tests.support.expect import raises_with
from tests.support.sync_catalog import WON, default_catalog

CATALOG = default_catalog()
START = SyncState("prospecting", "pipeline")
LOST = SyncState("prospecting", "lost")
CLOSING = SyncResolution(revenue_amount=900_000_000, revenue_date=date(2026, 10, 20))
REVENUE_REQUIRED = "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."
CHOICE_REQUIRED = "함께 바꿀 값을 선택하세요."


def _status(value: str, resolution: SyncResolution | None = None) -> SyncStep:
    return SyncStep(SyncChange(SyncField.STATUS, value), resolution)


def _forecast(value: str, resolution: SyncResolution | None = None) -> SyncStep:
    return SyncStep(SyncChange(SyncField.FORECAST, value), resolution)


def test_no_steps_returns_nothing() -> None:
    assert finalize_sequence(START, [], CATALOG) == ()


def test_a_single_step_equals_finalize_plan() -> None:
    step = _status("contract_completed", CLOSING)
    plan = plan_change(START, step.change, CATALOG)

    applied = finalize_sequence(START, [step], CATALOG)

    assert applied == (finalize_plan(START, plan, CLOSING, CATALOG),)


def test_two_independent_steps_accumulate_states() -> None:
    applied = finalize_sequence(START, [_status("introduction"), _forecast("best")], CATALOG)

    assert [a.state for a in applied] == [
        SyncState("introduction", "pipeline"),
        SyncState("introduction", "best"),
    ]
    assert [a.co_changed for a in applied] == [(), ()]


def test_the_second_step_is_judged_after_the_first() -> None:
    steps = [
        _forecast("commit", SyncResolution(status_key="poc_completed")),
        _status("introduction"),
    ]

    applied = finalize_sequence(WON, steps, CATALOG)

    assert applied[1].state == SyncState("introduction", "commit")
    assert applied[1].co_changed == ()
    assert applied[1].notice is None


def test_the_second_step_may_change_a_co_changed_field() -> None:
    steps = [_status("poc_completed", SyncResolution(forecast_key="commit")), _forecast("best")]

    applied = finalize_sequence(WON, steps, CATALOG)

    assert applied[1].state == SyncState("poc_completed", "best")
    assert applied[0].co_changed == (CoChange(SyncField.FORECAST, "won", "commit"),)
    assert applied[1].co_changed == ()


def test_closing_after_a_status_change_is_a_conflict() -> None:
    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        finalize_sequence(START, [_status("introduction"), _forecast("won", CLOSING)], CATALOG)


def test_reopening_after_closing_is_a_conflict() -> None:
    steps = [
        _status("contract_completed", CLOSING),
        _forecast("commit", SyncResolution(status_key="poc_completed")),
    ]

    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        finalize_sequence(START, steps, CATALOG)


def test_closing_by_status_after_a_forecast_change_is_a_conflict() -> None:
    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        finalize_sequence(
            START, [_forecast("best"), _status("contract_completed", CLOSING)], CATALOG
        )


def test_leaving_won_after_choosing_won_is_a_conflict() -> None:
    steps = [
        _forecast("won", CLOSING),
        _status("poc_completed", SyncResolution(forecast_key="commit")),
    ]

    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        finalize_sequence(START, steps, CATALOG)


def test_choosing_the_first_value_again_in_a_lost_reopen_is_allowed() -> None:
    steps = [
        _status("introduction"),
        _forecast("commit", SyncResolution(status_key="introduction")),
    ]

    applied = finalize_sequence(LOST, steps, CATALOG)

    assert applied[1].state == SyncState("introduction", "commit")


def test_choosing_another_status_in_a_lost_reopen_is_a_conflict() -> None:
    steps = [_status("introduction"), _forecast("commit", SyncResolution(status_key="prospecting"))]

    with raises_with(InvalidValueError, SYNC_CONFLICT_MESSAGE):
        finalize_sequence(LOST, steps, CATALOG)


def test_a_missing_answer_in_the_second_step_is_reported() -> None:
    with raises_with(InvalidValueError, CHOICE_REQUIRED):
        finalize_sequence(LOST, [_status("introduction"), _forecast("commit")], CATALOG)


def test_a_missing_revenue_in_the_first_step_is_reported_first() -> None:
    with raises_with(InvalidValueError, REVENUE_REQUIRED):
        finalize_sequence(START, [_status("contract_completed"), _forecast("best")], CATALOG)


def test_duplicate_fields_are_rejected() -> None:
    with raises_with(InvalidValueError, SYNC_DUPLICATE_MESSAGE):
        finalize_sequence(START, [_status("introduction"), _status("poc_completed")], CATALOG)


def test_more_than_two_steps_are_rejected() -> None:
    steps = [_status("introduction"), _forecast("best"), _status("poc_completed")]

    with raises_with(InvalidValueError, SYNC_DUPLICATE_MESSAGE):
        finalize_sequence(START, steps, CATALOG)


def test_each_step_uses_only_its_own_resolution() -> None:
    steps = [
        _forecast("commit"),
        _status("introduction", SyncResolution(status_key="poc_completed")),
    ]

    with raises_with(InvalidValueError, CHOICE_REQUIRED):
        finalize_sequence(WON, steps, CATALOG)


def test_same_value_second_step_is_a_no_op() -> None:
    applied = finalize_sequence(START, [_status("introduction"), _forecast("pipeline")], CATALOG)

    assert applied[1].state == applied[0].state == SyncState("introduction", "pipeline")
    assert applied[1].co_changed == ()


@pytest.mark.parametrize("message", [SYNC_CONFLICT_MESSAGE, SYNC_DUPLICATE_MESSAGE])
def test_error_messages_match_the_agreed_wording(message: str) -> None:
    assert message in {
        "먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요.",
        "Status와 Forecast는 한 번에 각각 한 번만 바꿀 수 있습니다.",
    }
