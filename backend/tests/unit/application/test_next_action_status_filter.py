"""NextActionStatusFilter: 4개 값, closed는 done과 not_done으로 펼쳐진다."""

import pytest

from app.application.ports.deal_action_repository import NextActionStatusFilter
from app.domain.deal_action.next_action_status import NextActionStatus


def test_filter_values_are_the_wire_values() -> None:
    """상태 필터의 허용 값은 open·done·not_done·closed 넷이다.

    테스트 코드: NA-033, NA-035
    """
    # when: 필터 값을 나열한다
    values = [f.value for f in NextActionStatusFilter]
    # then: 네 값이다
    assert values == ["open", "done", "not_done", "closed"]


def test_status_filter_closed_expands_to_done_and_not_done() -> None:
    """closed는 종료(수행)와 종료(미수행) 둘로 펼쳐진다.

    테스트 코드: NA-033
    """
    # when: closed가 거르는 상태를 구한다
    statuses = NextActionStatusFilter.CLOSED.statuses()
    # then: done과 not_done이다
    assert set(statuses) == {NextActionStatus.DONE, NextActionStatus.NOT_DONE}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (NextActionStatusFilter.OPEN, (NextActionStatus.OPEN,)),
        (NextActionStatusFilter.DONE, (NextActionStatus.DONE,)),
        (NextActionStatusFilter.NOT_DONE, (NextActionStatus.NOT_DONE,)),
    ],
)
def test_single_status_filters_expand_to_themselves(
    value: NextActionStatusFilter, expected: tuple[NextActionStatus, ...]
) -> None:
    """open·done·not_done 필터는 같은 상태 하나로 펼쳐진다.

    테스트 코드: NA-033
    """
    # when: 필터가 거르는 상태를 구한다
    statuses = value.statuses()
    # then: 같은 상태 하나다
    assert statuses == expected


def test_next_action_status_input_defaults_to_an_empty_memo() -> None:
    """상태 변경 입력에서 메모를 생략하면 빈 문자열이다.

    테스트 코드: NA-003
    """
    from app.application.deal_action.inputs import NextActionStatusInput  # noqa: PLC0415

    # when: 메모 없이 상태 변경 입력을 만든다
    data = NextActionStatusInput(status=NextActionStatus.DONE)
    # then: 메모는 빈 문자열이다
    assert (data.status, data.memo) == (NextActionStatus.DONE, "")
