"""Next Action 상태: 종료 Comment 전달(내용 불변), 같은 상태·Next Action 없음 거절, 되돌리기."""

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal_action.next_action_status import (
    NextActionState,
    NextActionStatus,
    NextActionStatusChange,
)
from tests.factories import NOW, later, make_deal_action
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from collections.abc import Callable

TODAY = date(2026, 1, 1)  # NOW(UTC 09:00)의 서울 업무 날짜
NEXT_DAY = date(2026, 1, 2)


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


NO_NEXT_ACTION = "Next Action이 없는 Action은 상태를 바꿀 수 없습니다."


class TestStatusValues:
    def test_only_closed_statuses_are_closed(self) -> None:
        """done과 not_done만 종료 상태다."""
        # when: 상태마다 종료 여부를 구한다
        flags = [s.is_closed for s in NextActionStatus]
        # then: open은 아니고 done·not_done은 종료다
        assert flags == [False, True, True]

    def test_sort_rank_orders_open_then_done_then_not_done(self) -> None:
        """정렬 순위는 Open, 종료(수행), 종료(미수행) 순이고 서로 다르다."""
        # when: 세 상태의 순위를 구한다
        ranks = [NextActionStatus.OPEN, NextActionStatus.DONE, NextActionStatus.NOT_DONE]
        # then: 오름차순이고 값이 모두 다르다
        assert [s.sort_rank for s in ranks] == sorted(s.sort_rank for s in ranks)
        assert len({s.sort_rank for s in ranks}) == 3

    def test_values_and_labels(self) -> None:
        """상태 값과 화면 라벨이 정해진 대로다."""
        # when: 값과 라벨을 나열한다
        pairs = [(s.value, s.label) for s in NextActionStatus]
        # then: open/Open, done/종료(수행), not_done/종료(미수행)이다
        assert pairs == [
            ("open", "Open"),
            ("done", "종료(수행)"),
            ("not_done", "종료(미수행)"),
        ]

    def test_state_closed_without_date_raises(self) -> None:
        """종료 상태에 종료일이 없으면 InvalidValueError다."""
        # when·then: 종료일 없이 종료 상태를 만든다
        with pytest.raises(InvalidValueError):
            NextActionState(status=NextActionStatus.DONE, closed_on=None)

    def test_state_open_with_date_raises(self) -> None:
        """Open 상태에 종료일이 있으면 InvalidValueError다."""
        # when·then: 종료일이 있는 Open 상태를 만든다
        with pytest.raises(InvalidValueError):
            NextActionState(status=NextActionStatus.OPEN, closed_on=TODAY)


class TestClose:
    def test_close_returns_the_trimmed_comment_as_the_note_and_leaves_the_content(self) -> None:
        """종료 Comment를 주면 앞뒤 공백을 지운 값이 변경 결과의 note로 나가고 내용은 그대로다.

        테스트 코드: CM-031
        """
        # given: Open Action
        action = make_deal_action()
        before = action.content
        # when: Comment "  견적 전달 완료  "로 종료(수행)한다
        change = action.change_next_action_status(
            NextActionStatus.DONE, "  견적 전달 완료  ", later(10)
        )
        # then: 변경 결과의 note는 trim한 Comment이고 Action 내용은 바뀌지 않는다
        assert action.content == before
        assert change == NextActionStatusChange(
            before=NextActionStatus.OPEN, after=NextActionStatus.DONE, note="견적 전달 완료"
        )

    def test_close_stores_the_status_and_closed_date_and_touches_updated_at(self) -> None:
        """종료하면 상태와 종료일(요청의 업무 날짜)이 남고 Action 수정 시각이 바뀐다.

        테스트 코드: NA-004
        """
        # given: Open Action
        action = make_deal_action()
        # when: 시각 T에 종료(미수행)한다
        action.change_next_action_status(NextActionStatus.NOT_DONE, "", later(10))
        # then: 종료일은 T의 업무 날짜이고 수정 시각이 T다
        assert action.next_action_state == NextActionState(
            status=NextActionStatus.NOT_DONE, closed_on=TODAY
        )
        assert action.updated_at == later(10)

    def test_close_with_blank_comment_has_an_empty_note(self) -> None:
        """공백뿐인 종료 Comment는 note를 비운다(Comment를 만들지 않는다는 뜻).

        테스트 코드: CM-033
        """
        # given: Open Action
        action = make_deal_action()
        # when: 공백과 줄바꿈뿐인 Comment로 종료한다
        change = action.change_next_action_status(NextActionStatus.DONE, " \n ", later(10))
        # then: 변경 결과의 note는 비어 있다
        assert change.note == ""

    def test_close_does_not_touch_other_content(self) -> None:
        """종료해도 진행사항·Next Action·Due·유형과 수행일은 바뀌지 않는다.

        테스트 코드: NA-011
        """
        # given: Open Action의 내용
        action = make_deal_action()
        before = action.content
        # when: Comment 없이 종료한다
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))
        # then: 내용과 수행일이 그대로다
        assert action.content == before
        assert action.acted_on == TODAY

    def test_done_to_not_done_updates_closed_on(self) -> None:
        """종료(수행)에서 종료(미수행)으로 바로 바꾸면 종료일이 새로 정해진다.

        테스트 코드: NA-004
        """
        # given: 1월 1일에 종료(수행)된 Action
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))
        # when: 다음 날(1월 2일)에 not_done, Comment "취소됨"으로 바꾼다
        change = action.change_next_action_status(
            NextActionStatus.NOT_DONE, "취소됨", later(86400 + 10)
        )
        # then: 이전 상태는 done, 종료일은 1월 2일이고 note는 "취소됨"이다
        assert change.before is NextActionStatus.DONE
        assert change.note == "취소됨"
        assert action.next_action_state == NextActionState(
            status=NextActionStatus.NOT_DONE, closed_on=NEXT_DAY
        )

    def test_note_with_nul_raises_invalid_value(self) -> None:
        """종료 Comment에 NUL 문자가 있으면 InvalidValueError이고 상태가 그대로다.

        테스트 코드: NA-009
        """
        # given: Open Action
        action = make_deal_action()
        # when·then: Comment "가\x00나"로 종료하면 NUL 문구의 InvalidValueError다
        with raises_with(InvalidValueError, "Comment에는 NUL 문자를 쓸 수 없습니다"):
            action.change_next_action_status(NextActionStatus.DONE, "가\x00나", later(10))
        # then: 상태가 Open 그대로다
        assert action.next_action_state == NextActionState.open()


class TestReopen:
    def test_reopen_clears_closed_on_and_leaves_the_content(self) -> None:
        """Open으로 되돌리면 종료일이 없어지고 내용은 그대로다(만든 Comment는 별도 엔티티라 남는다).

        테스트 코드: NA-005
        """
        # given: Comment "종료 Comment"로 종료(수행)한 Action
        action = make_deal_action()
        content = action.content
        action.change_next_action_status(NextActionStatus.DONE, "종료 Comment", later(10))
        # when: open으로 되돌린다
        change = action.change_next_action_status(NextActionStatus.OPEN, "", later(20))
        # then: Open이고 종료일이 없으며 내용이 그대로다
        assert action.next_action_state == NextActionState.open()
        assert action.content == content
        assert change == NextActionStatusChange(
            before=NextActionStatus.DONE, after=NextActionStatus.OPEN, note=""
        )

    def test_reopen_with_note_raises_invalid_value(self) -> None:
        """Open으로 되돌리며 Comment를 보내면 InvalidValueError이고 종료 상태가 그대로다.

        테스트 코드: NA-006
        """
        # given: 종료(수행)된 Action
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))
        # when·then: Comment "메모"와 함께 open으로 바꾸면 해당 문구의 InvalidValueError다
        with raises_with(InvalidValueError, "Open으로 되돌릴 때는 Comment를 남길 수 없습니다."):
            action.change_next_action_status(NextActionStatus.OPEN, "메모", later(20))
        # then: 종료(수행) 상태가 그대로다
        assert action.next_action_state is not None
        assert action.next_action_state.status is NextActionStatus.DONE

    def test_reopen_with_blank_note_is_allowed(self) -> None:
        """Open으로 되돌릴 때 공백뿐인 Comment는 허용된다.

        테스트 코드: NA-006
        """
        # given: 종료(미수행)된 Action
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.NOT_DONE, "", later(10))
        # when: 공백뿐인 Comment와 함께 open으로 바꾼다
        action.change_next_action_status(NextActionStatus.OPEN, "   ", later(20))
        # then: Open이 된다
        assert action.next_action_state == NextActionState.open()


class TestRejections:
    def test_same_status_raises_invalid_state(self) -> None:
        """Open Action을 open으로 바꾸면 InvalidStateError이고 수정 시각이 그대로다.

        테스트 코드: NA-007
        """
        # given: Open Action
        action = make_deal_action()
        # when·then: open으로 바꾸면 "이미 Open 상태입니다."다
        with raises_with(InvalidStateError, "이미 Open 상태입니다."):
            action.change_next_action_status(NextActionStatus.OPEN, "", later(10))
        # then: 수정 시각이 그대로다
        assert action.updated_at == NOW

    def test_same_closed_status_raises_with_its_label(self) -> None:
        """종료(수행) Action을 Comment와 함께 done으로 바꾸면 InvalidStateError이고 상태가 그대로다.

        테스트 코드: NA-007
        """
        # given: 종료(수행)된 Action
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))
        # when·then: done, Comment "또"로 바꾸면 "이미 종료(수행) 상태입니다."다
        with raises_with(InvalidStateError, "이미 종료(수행) 상태입니다."):
            action.change_next_action_status(NextActionStatus.DONE, "또", later(20))
        # then: 수정 시각이 그대로다
        assert action.updated_at == later(10)

    def test_change_without_next_action_raises_invalid_state(self) -> None:
        """Next Action이 없는 Action의 상태를 바꾸면 InvalidStateError이다.

        테스트 코드: NA-008
        """
        # given: 진행사항만 Action
        action = make_deal_action(next_action="", due_date=None)
        # when·then: done으로 바꾸면 Next Action 없음 문구다
        with raises_with(InvalidStateError, NO_NEXT_ACTION):
            action.change_next_action_status(NextActionStatus.DONE, "", later(10))
        # then: 상태는 없는 그대로다
        assert action.next_action_state is None

    def test_open_with_note_is_reported_before_missing_next_action(self) -> None:
        """Open+Comment 검사가 Next Action 없음 검사보다 먼저다.

        테스트 코드: NA-010
        """
        # given: 진행사항만 Action
        action = make_deal_action(next_action="", due_date=None)
        # when·then: open+Comment를 보내면 409가 아니라 InvalidValueError(Open+Comment)다
        with raises_with(InvalidValueError, "Open으로 되돌릴 때는 Comment를 남길 수 없습니다."):
            action.change_next_action_status(NextActionStatus.OPEN, "메모", later(10))

    def test_nul_note_is_reported_before_same_status(self) -> None:
        """NUL 검사가 같은 상태 검사보다 먼저다.

        테스트 코드: NA-010
        """
        # given: Open Action
        action = make_deal_action()
        # when·then: open+NUL Comment를 보내면 409가 아니라 NUL 문구의 InvalidValueError다
        with raises_with(InvalidValueError, "Comment에는 NUL 문자를 쓸 수 없습니다"):
            action.change_next_action_status(NextActionStatus.OPEN, "\x00", later(10))

    def test_nul_note_is_reported_before_state_errors(self) -> None:
        """NUL 검사가 Next Action 없음 검사보다 먼저다.

        테스트 코드: NA-010
        """
        # given: 진행사항만 Action
        action = make_deal_action(next_action="", due_date=None)
        # when·then: NUL Comment로 done을 보내면 409가 아니라 NUL 문구의 InvalidValueError다
        with raises_with(InvalidValueError, "Comment에는 NUL 문자를 쓸 수 없습니다"):
            action.change_next_action_status(NextActionStatus.DONE, "\x00", later(10))

    def test_closing_requires_an_aware_time(self) -> None:
        """시간대가 없는 시각으로 상태를 바꾸면 InvalidValueError다."""
        # given: Open Action
        action = make_deal_action()
        # when·then: 시간대 없는 시각으로 종료한다
        with pytest.raises(InvalidValueError):
            action.change_next_action_status(
                NextActionStatus.DONE, "", (NOW + timedelta(minutes=1)).replace(tzinfo=None)
            )
