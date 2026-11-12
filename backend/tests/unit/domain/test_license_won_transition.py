"""Won 전이 판정(AC6~AC8): 신규 등록·Won 진입·Won 이탈·그 밖."""

import pytest

from app.domain.license_contract.won import WonTransition, won_transition
from tests.factories import make_sync

WON = ("contract_completed", "won")
PIPELINE = ("prospecting", "pipeline")
LOST = ("lost", "lost")


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (None, WON, WonTransition.ENTERED),  # 처음부터 Won으로 등록
        (None, PIPELINE, WonTransition.NONE),
        (PIPELINE, WON, WonTransition.ENTERED),
        (LOST, WON, WonTransition.ENTERED),
        (WON, LOST, WonTransition.LEFT),
        (WON, PIPELINE, WonTransition.LEFT),
        (WON, WON, WonTransition.NONE),
        (PIPELINE, LOST, WonTransition.NONE),
        (PIPELINE, PIPELINE, WonTransition.NONE),
    ],
)
def test_won_transition_entered_left_none(
    before: tuple[str, str] | None, after: tuple[str, str], expected: WonTransition
) -> None:
    """Won 진입·이탈·무관은 변경 전후의 Won 여부만 비교한다.

    테스트 코드: LC-003, LC-004
    """
    # given: 변경 전 상태(없을 수 있음)와 변경 후 상태
    before_state = None if before is None else make_sync(*before)

    # when: Won 전환을 판정한다
    actual = won_transition(before_state, make_sync(*after))
    # then: 진입·이탈·없음 중 기대한 값이다
    assert actual is expected


def test_the_transition_values_are_the_documented_words() -> None:
    """전환 값은 entered·left·none 세 단어다."""
    # when: WonTransition 값을 모은다
    actual = {t.value for t in WonTransition}
    # then: 세 단어뿐이다
    assert actual == {"entered", "left", "none"}
