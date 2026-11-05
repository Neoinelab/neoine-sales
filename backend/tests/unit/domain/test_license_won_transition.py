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
    before_state = None if before is None else make_sync(*before)

    assert won_transition(before_state, make_sync(*after)) is expected


def test_the_transition_values_are_the_documented_words() -> None:
    assert {t.value for t in WonTransition} == {"entered", "left", "none"}
