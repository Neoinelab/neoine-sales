"""Next Action 기준 행 선택(RK-R1): 지난 Open 우선(Due 오름차순·id 내림차순), 없으면 가장 최근 행.

기준 행의 정본은 domain `pick_next_action_basis`이고 Fake 저장소와 SQL이 같은 결과를 내야 한다
(SQL과의 일치는 `tests/unit/repositories/test_deal_next_action_basis_contract.py`).
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest
from app.domain.deal_action.next_action_basis import is_past_due_open, pick_next_action_basis

from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import make_deal_action

if TYPE_CHECKING:
    from app.domain.deal_action.entities import DealAction

TODAY = date(2026, 1, 10)


def _row(
    row_id: int,
    *,
    acted_on: date,
    due: date | None,
    status: NextActionStatus = NextActionStatus.OPEN,
) -> DealAction:
    """Next Action이 있는 행(due가 None이면 진행사항만 있는 행)."""
    action = make_deal_action(
        acted_on=acted_on,
        entity_id=DealActionId(row_id),
        action="진행",
        next_action="" if due is None else f"다음-{row_id}",
        due_date=due,
    )
    if due is not None and status is not NextActionStatus.OPEN:
        action.change_next_action_status(status, "", action.created_at)
    return action


def _ids(*actions: DealAction | None) -> list[int | None]:
    return [None if a is None else int(a.id) for a in actions]


def test_the_earliest_due_past_open_row_wins_even_when_it_is_not_the_most_recent() -> None:
    """지난 Open 행이 있으면 Due가 가장 이른 행이고 더 최근 행·미래 Due 행보다 앞선다.

    테스트 코드: RK-086
    """
    # given: 지난 Open 세 행(Due 01-05 id 3·7, 01-08), Due 오늘 Open 행, 지난 done 행, 진행사항만 행
    rows = [
        _row(3, acted_on=date(2026, 1, 1), due=date(2026, 1, 5)),
        _row(7, acted_on=date(2026, 1, 2), due=date(2026, 1, 5)),
        _row(5, acted_on=date(2026, 1, 3), due=date(2026, 1, 8)),
        _row(8, acted_on=date(2026, 1, 4), due=TODAY),
        _row(9, acted_on=date(2026, 1, 6), due=date(2026, 1, 4), status=NextActionStatus.DONE),
        _row(10, acted_on=date(2026, 1, 9), due=None),
    ]

    # when: 오늘 2026-01-10 기준으로 기준 행을 고른다
    basis = pick_next_action_basis(rows, TODAY)

    # then: Due가 가장 이른 01-05 행들 중 id가 큰 7이다
    assert _ids(basis) == [7]


def test_the_basis_without_past_open_rows_is_the_latest_acted_on_then_larger_id() -> None:
    """지난 Open 행이 없으면 Next Action이 있는 행 중 수행일이 가장 늦은 행, 같으면 id가 큰 행이다.

    테스트 코드: RK-086
    """
    # given: 지난 Open 행이 없다(Due 오늘 Open, 지난 done·not_done, 수행일이 같은 두 행)
    rows = [
        _row(1, acted_on=date(2026, 1, 2), due=TODAY),
        _row(2, acted_on=date(2026, 1, 5), due=date(2026, 1, 4), status=NextActionStatus.DONE),
        _row(4, acted_on=date(2026, 1, 9), due=date(2026, 1, 3), status=NextActionStatus.NOT_DONE),
        _row(6, acted_on=date(2026, 1, 9), due=date(2026, 1, 20)),
        _row(9, acted_on=date(2026, 1, 9), due=None),  # 진행사항만: 후보가 아니다
    ]

    # when: 기준 행을 고른다
    basis = pick_next_action_basis(rows, TODAY)

    # then: 수행일 01-09 행 중 id가 큰 6이다(진행사항만 있는 9가 아니다)
    assert _ids(basis) == [6]


def test_a_closed_row_is_the_basis_when_it_is_the_latest_and_nothing_is_past_open() -> None:
    """종료된 행도 지난 Open이 없으면 가장 최근 행으로 기준 행이 된다.

    테스트 코드: RK-086
    """
    # given: 오래된 Open(Due 미래)과 더 최근에 종료한 행
    rows = [
        _row(1, acted_on=date(2026, 1, 1), due=date(2026, 2, 1)),
        _row(2, acted_on=date(2026, 1, 8), due=date(2026, 1, 20), status=NextActionStatus.DONE),
    ]

    # when·then: 종료된 최근 행이 기준 행이다
    assert _ids(pick_next_action_basis(rows, TODAY)) == [2]


def test_no_next_action_rows_means_no_basis_and_the_input_is_not_mutated() -> None:
    """Next Action 행이 없으면 None이고 입력 목록은 바뀌지 않는다.

    테스트 코드: RK-086
    """
    # given: 진행사항만 있는 행들과 빈 목록
    rows = [
        _row(1, acted_on=date(2026, 1, 1), due=None),
        _row(2, acted_on=date(2026, 1, 2), due=None),
    ]
    snapshot = list(rows)

    # when·then: 기준 행이 없다
    assert pick_next_action_basis(rows, TODAY) is None
    assert pick_next_action_basis([], TODAY) is None
    # then: 입력 순서와 내용이 그대로다
    assert rows == snapshot


def test_the_result_does_not_depend_on_the_input_order() -> None:
    """입력 순서를 뒤집어도 같은 기준 행이다.

    테스트 코드: RK-086
    """
    # given: 지난 Open 두 행과 최근 행
    rows = [
        _row(1, acted_on=date(2026, 1, 1), due=date(2026, 1, 6)),
        _row(2, acted_on=date(2026, 1, 2), due=date(2026, 1, 4)),
        _row(3, acted_on=date(2026, 1, 9), due=date(2026, 1, 30)),
    ]

    # when·then: 정방향·역방향 모두 Due가 가장 이른 2다
    assert _ids(pick_next_action_basis(rows, TODAY)) == [2]
    assert _ids(pick_next_action_basis(list(reversed(rows)), TODAY)) == [2]


@pytest.mark.parametrize(
    ("status", "due", "expected"),
    [
        (NextActionStatus.OPEN, date(2026, 1, 9), True),
        (NextActionStatus.OPEN, TODAY, False),  # Due가 오늘이면 지난 행이 아니다
        (NextActionStatus.OPEN, date(2026, 1, 11), False),
        (NextActionStatus.DONE, date(2026, 1, 9), False),
        (NextActionStatus.NOT_DONE, date(2026, 1, 9), False),
        (None, None, False),  # 진행사항만 있는 행
        (NextActionStatus.OPEN, None, False),
    ],
)
def test_past_due_open_needs_open_status_and_a_due_before_today(
    status: NextActionStatus | None, due: date | None, expected: bool
) -> None:
    """지난 Open 판정은 상태가 open이고 Due가 오늘보다 앞일 때만 참이다(오늘은 제외).

    테스트 코드: RK-086
    """
    # when·then: 상태·Due 조합에 따라 판정된다
    assert is_past_due_open(status, due, TODAY) is expected
