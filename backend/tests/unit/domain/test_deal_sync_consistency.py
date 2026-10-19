"""Status⇄Forecast 불변식(AC-18): `contract_completed` ⇔ `won`. 프런트 `isSyncConsistent`와 같다.

단일 변경(applyChange)의 계획·확정 규칙은 R3 범위다(`sync.test.ts` 사례 이식).
"""

import dataclasses

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import SyncMismatchError
from app.domain.deal.sync import (
    FORECAST_LOST,
    FORECAST_PIPELINE,
    FORECAST_WON,
    STATUS_CONTRACT_COMPLETED,
    STATUS_PROSPECTING,
    SYNC_MISMATCH_MESSAGE,
    SyncState,
    ensure_sync_consistent,
    is_sync_consistent,
)
from tests.support.expect import raises_with

CONSISTENT = [
    ("prospecting", "pipeline"),
    ("price_negotiation", "commit"),
    ("price_negotiation", "lost"),  # Lost는 Status를 유지한다
    ("contract_completed", "won"),
]
INCONSISTENT = [
    ("contract_completed", "best"),
    ("contract_completed", "lost"),
    ("prospecting", "won"),
    ("price_negotiation", "won"),
]


def test_constants_are_the_system_keys_and_message() -> None:
    assert STATUS_PROSPECTING == "prospecting"
    assert STATUS_CONTRACT_COMPLETED == "contract_completed"
    assert (FORECAST_PIPELINE, FORECAST_WON, FORECAST_LOST) == ("pipeline", "won", "lost")
    assert SYNC_MISMATCH_MESSAGE == "Status와 Forecast의 동기화가 맞지 않습니다."


@pytest.mark.parametrize(("status_key", "forecast_key"), CONSISTENT)
def test_contract_completed_with_won_or_neither_is_consistent(
    status_key: str, forecast_key: str
) -> None:
    state = SyncState(status_key=status_key, forecast_key=forecast_key)

    assert is_sync_consistent(state) is True
    ensure_sync_consistent(state)  # 예외 없음


@pytest.mark.parametrize(("status_key", "forecast_key"), INCONSISTENT)
def test_exactly_one_of_contract_completed_and_won_is_inconsistent(
    status_key: str, forecast_key: str
) -> None:
    state = SyncState(status_key=status_key, forecast_key=forecast_key)

    assert is_sync_consistent(state) is False
    with raises_with(SyncMismatchError, SYNC_MISMATCH_MESSAGE):
        ensure_sync_consistent(state)


def test_sync_mismatch_is_an_invalid_value_for_the_422_mapping() -> None:
    assert issubclass(SyncMismatchError, InvalidValueError)


def test_sync_state_is_a_frozen_value() -> None:
    state = SyncState(status_key="prospecting", forecast_key="pipeline")

    assert state == SyncState(status_key="prospecting", forecast_key="pipeline")
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.status_key = "x"  # type: ignore[misc]
