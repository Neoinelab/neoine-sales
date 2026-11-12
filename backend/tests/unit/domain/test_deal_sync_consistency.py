"""Status⇄Forecast 불변식: `contract_completed` ⇔ `won`. 프런트 `isSyncConsistent`와 같다.

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
    """동기화 상수는 시스템 키와 고정 문구다."""
    # when·then: 상수를 읽는다 → 시스템 키와 동기화 불일치 문구다
    assert STATUS_PROSPECTING == "prospecting"
    assert STATUS_CONTRACT_COMPLETED == "contract_completed"
    assert (FORECAST_PIPELINE, FORECAST_WON, FORECAST_LOST) == ("pipeline", "won", "lost")
    assert SYNC_MISMATCH_MESSAGE == "Status와 Forecast의 동기화가 맞지 않습니다."


@pytest.mark.parametrize(("status_key", "forecast_key"), CONSISTENT)
def test_contract_completed_with_won_or_neither_is_consistent(
    status_key: str, forecast_key: str
) -> None:
    """계약완료와 Won이 함께이거나 둘 다 아니면 일관적이다.

    테스트 코드: DD-008
    """
    # given: (계약완료, Won) 또는 둘 다 아닌 조합
    state = SyncState(status_key=status_key, forecast_key=forecast_key)

    # when: 일관성을 판정한다
    assert is_sync_consistent(state) is True
    # then: 일관적이고 확인 함수가 예외를 내지 않는다
    ensure_sync_consistent(state)  # 예외 없음


@pytest.mark.parametrize(("status_key", "forecast_key"), INCONSISTENT)
def test_exactly_one_of_contract_completed_and_won_is_inconsistent(
    status_key: str, forecast_key: str
) -> None:
    """계약완료와 Won 중 하나만 있으면 불일치이고 동기화 문구의 오류다.

    테스트 코드: DD-008
    """
    # given: 한쪽만 계약완료 또는 Won인 조합
    state = SyncState(status_key=status_key, forecast_key=forecast_key)

    # when: 일관성을 판정한다
    assert is_sync_consistent(state) is False
    # then: 불일치이고 확인 함수는 동기화 오류를 낸다
    with raises_with(SyncMismatchError, SYNC_MISMATCH_MESSAGE):
        ensure_sync_consistent(state)


def test_sync_mismatch_is_an_invalid_value_for_the_422_mapping() -> None:
    """동기화 불일치 오류는 값 오류의 하위 형식이라 422 invalid-value로 매핑된다.

    테스트 코드: DD-008
    """
    # when·then: 오류 종류를 확인한다 → 값 오류(InvalidValueError)의 하위 클래스다
    assert issubclass(SyncMismatchError, InvalidValueError)


def test_sync_state_is_a_frozen_value() -> None:
    """SyncState는 값이 같으면 같고 바꿀 수 없다."""
    # given: Status·Forecast가 든 SyncState
    state = SyncState(status_key="prospecting", forecast_key="pipeline")

    assert state == SyncState(status_key="prospecting", forecast_key="pipeline")
    # when·then: 같은 값과 비교하고 값을 바꾸려 한다 → 같은 값끼리 같고 바꾸면 FrozenInstanceError다
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.status_key = "x"  # type: ignore[misc]
