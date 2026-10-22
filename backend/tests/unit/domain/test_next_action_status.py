"""Next Action 상태(AC-8·9·11·12): 종료 메모 덧붙임, 같은 상태·Next Action 없음 거절, 되돌리기."""

from datetime import timedelta

import pytest

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal_action.next_action_status import (
    NextActionState,
    NextActionStatus,
    NextActionStatusChange,
)
from tests.factories import NOW, later, make_deal_action
from tests.support.expect import raises_with

NO_NEXT_ACTION = "Next Action이 없는 Action은 상태를 바꿀 수 없습니다."


class TestStatusValues:
    def test_only_closed_statuses_are_closed(self) -> None:
        assert [s.is_closed for s in NextActionStatus] == [False, True, True]

    def test_sort_rank_orders_open_then_done_then_not_done(self) -> None:
        ranks = [NextActionStatus.OPEN, NextActionStatus.DONE, NextActionStatus.NOT_DONE]

        assert [s.sort_rank for s in ranks] == sorted(s.sort_rank for s in ranks)
        assert len({s.sort_rank for s in ranks}) == 3

    def test_values_and_labels(self) -> None:
        assert [(s.value, s.label) for s in NextActionStatus] == [
            ("open", "Open"),
            ("done", "종료(수행)"),
            ("not_done", "종료(미수행)"),
        ]

    def test_state_closed_without_time_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            NextActionState(status=NextActionStatus.DONE, closed_at=None)

    def test_state_open_with_time_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            NextActionState(status=NextActionStatus.OPEN, closed_at=NOW)

    def test_state_closed_with_naive_time_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            NextActionState(status=NextActionStatus.DONE, closed_at=NOW.replace(tzinfo=None))


class TestClose:
    def test_close_done_appends_note_to_memo(self) -> None:
        action = make_deal_action(memo="기존 메모")

        change = action.change_next_action_status(
            NextActionStatus.DONE, "견적 전달 완료", later(10)
        )

        assert action.content.memo == "기존 메모\n견적 전달 완료"
        assert change == NextActionStatusChange(
            before=NextActionStatus.OPEN, after=NextActionStatus.DONE, note="견적 전달 완료"
        )

    def test_close_stores_the_status_and_closed_time_and_touches_updated_at(self) -> None:
        action = make_deal_action()

        action.change_next_action_status(NextActionStatus.NOT_DONE, "", later(10))

        assert action.next_action_state == NextActionState(
            status=NextActionStatus.NOT_DONE, closed_at=later(10)
        )
        assert action.updated_at == later(10)

    def test_close_with_empty_memo_uses_note_only(self) -> None:
        action = make_deal_action(memo="")

        action.change_next_action_status(NextActionStatus.DONE, "  마무리  ", later(10))

        assert action.content.memo == "마무리"

    def test_close_with_blank_note_keeps_memo(self) -> None:
        action = make_deal_action(memo="기존 메모")

        change = action.change_next_action_status(NextActionStatus.DONE, " \n ", later(10))

        assert action.content.memo == "기존 메모"
        assert change.note == ""

    def test_close_does_not_touch_other_content(self) -> None:
        action = make_deal_action()
        before = action.content

        action.change_next_action_status(NextActionStatus.DONE, "", later(10))

        assert action.content == before
        assert action.acted_at == NOW

    def test_done_to_not_done_updates_closed_at(self) -> None:
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))

        change = action.change_next_action_status(NextActionStatus.NOT_DONE, "취소됨", later(20))

        assert change.before is NextActionStatus.DONE
        assert action.next_action_state == NextActionState(
            status=NextActionStatus.NOT_DONE, closed_at=later(20)
        )
        assert action.content.memo.endswith("\n취소됨")

    def test_note_with_nul_raises_invalid_value(self) -> None:
        action = make_deal_action()

        with pytest.raises(InvalidValueError, match="NUL"):
            action.change_next_action_status(NextActionStatus.DONE, "가\x00나", later(10))

        assert action.next_action_state == NextActionState.open()


class TestReopen:
    def test_reopen_clears_closed_at_and_keeps_memo(self) -> None:
        action = make_deal_action(memo="기존")
        action.change_next_action_status(NextActionStatus.DONE, "종료 메모", later(10))

        change = action.change_next_action_status(NextActionStatus.OPEN, "", later(20))

        assert action.next_action_state == NextActionState.open()
        assert action.content.memo == "기존\n종료 메모"
        assert change == NextActionStatusChange(
            before=NextActionStatus.DONE, after=NextActionStatus.OPEN, note=""
        )

    def test_reopen_with_note_raises_invalid_value(self) -> None:
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))

        with pytest.raises(InvalidValueError):
            action.change_next_action_status(NextActionStatus.OPEN, "메모", later(20))

        assert action.next_action_state is not None
        assert action.next_action_state.status is NextActionStatus.DONE

    def test_reopen_with_blank_note_is_allowed(self) -> None:
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.NOT_DONE, "", later(10))

        action.change_next_action_status(NextActionStatus.OPEN, "   ", later(20))

        assert action.next_action_state == NextActionState.open()


class TestRejections:
    def test_same_status_raises_invalid_state(self) -> None:
        action = make_deal_action()

        with raises_with(InvalidStateError, "이미 Open 상태입니다."):
            action.change_next_action_status(NextActionStatus.OPEN, "", later(10))

        assert action.updated_at == NOW

    def test_same_closed_status_raises_with_its_label(self) -> None:
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))

        with raises_with(InvalidStateError, "이미 종료(수행) 상태입니다."):
            action.change_next_action_status(NextActionStatus.DONE, "또", later(20))

        assert action.content.memo == "요구사항 정리"
        assert action.updated_at == later(10)

    def test_change_without_next_action_raises_invalid_state(self) -> None:
        action = make_deal_action(next_action="", due_date=None)

        with raises_with(InvalidStateError, NO_NEXT_ACTION):
            action.change_next_action_status(NextActionStatus.DONE, "", later(10))

        assert action.next_action_state is None

    def test_open_with_note_is_reported_before_missing_next_action(self) -> None:
        action = make_deal_action(next_action="", due_date=None)

        with pytest.raises(InvalidValueError):
            action.change_next_action_status(NextActionStatus.OPEN, "메모", later(10))

    def test_nul_note_is_reported_before_state_errors(self) -> None:
        action = make_deal_action(next_action="", due_date=None)

        with pytest.raises(InvalidValueError, match="NUL"):
            action.change_next_action_status(NextActionStatus.DONE, "\x00", later(10))

    def test_closing_requires_an_aware_time(self) -> None:
        action = make_deal_action()

        with pytest.raises(InvalidValueError):
            action.change_next_action_status(
                NextActionStatus.DONE, "", (NOW + timedelta(minutes=1)).replace(tzinfo=None)
            )
