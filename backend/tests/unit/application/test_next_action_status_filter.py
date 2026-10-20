"""NextActionStatusFilter(AC-18·19): 4개 값, closed는 done과 not_done으로 펼쳐진다."""

import pytest
from app.domain.deal_action.next_action_status import NextActionStatus

from app.application.ports.deal_action_repository import NextActionStatusFilter


def test_filter_values_are_the_wire_values() -> None:
    assert [f.value for f in NextActionStatusFilter] == ["open", "done", "not_done", "closed"]


def test_status_filter_closed_expands_to_done_and_not_done() -> None:
    assert set(NextActionStatusFilter.CLOSED.statuses()) == {
        NextActionStatus.DONE,
        NextActionStatus.NOT_DONE,
    }


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
    assert value.statuses() == expected


def test_next_action_status_input_defaults_to_an_empty_memo() -> None:
    from app.application.deal_action.inputs import NextActionStatusInput  # noqa: PLC0415

    data = NextActionStatusInput(status=NextActionStatus.DONE)

    assert (data.status, data.memo) == (NextActionStatus.DONE, "")
