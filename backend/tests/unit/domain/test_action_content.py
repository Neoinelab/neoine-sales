"""ActionContent: 진행사항·Next Action은 각각 선택(둘 다 비면 거절).

Due Date는 Next Action이 있을 때만 필수이고 없으면 금지다. trim, 길이 상한 없음, NUL 거부.
"""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal_action.value_objects import ActionContent
from tests.factories import make_action_content
from tests.factories_action_type import make_type_ref
from tests.support.expect import raises_with

ACTION_OR_NEXT_REQUIRED = "진행사항 또는 Next Action을 입력하세요."
DUE_DATE_REQUIRED = "Due Date를 입력하세요."
DUE_WITHOUT_NEXT = "Next Action 없이 Due Date를 입력할 수 없습니다."


def _parse(**overrides: Any) -> ActionContent:  # noqa: ANN401
    values: dict[str, Any] = {
        "action_type": make_type_ref("미팅"),
        "action": "킥오프",
        "next_action": "견적 전달",
        "due_date": date(2026, 2, 1),
        "memo": "",
    }
    return ActionContent.parse(**{**values, **overrides})


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        pytest.param(
            {"action": "   ", "next_action": "", "due_date": None},
            ACTION_OR_NEXT_REQUIRED,
            id="both-blank",
        ),
        pytest.param(
            {"action": "", "next_action": "  \n", "due_date": None},
            ACTION_OR_NEXT_REQUIRED,
            id="both-empty-or-whitespace",
        ),
        pytest.param({"action": "ok", "due_date": None}, DUE_DATE_REQUIRED, id="next-without-due"),
        pytest.param(
            {"action": "", "due_date": None}, DUE_DATE_REQUIRED, id="next-only-without-due"
        ),
        pytest.param(
            {"action": "ok", "next_action": "   ", "due_date": date(2026, 2, 1)},
            DUE_WITHOUT_NEXT,
            id="due-without-next",
        ),
        pytest.param(
            {"action": "", "next_action": "", "due_date": date(2026, 2, 1)},
            ACTION_OR_NEXT_REQUIRED,
            id="both-blank-reports-before-due",
        ),
    ],
)
def test_validation_reports_the_first_failing_rule_in_order(
    overrides: dict[str, object], message: str
) -> None:
    """내용 검증은 둘 다 빔 → Due 필수 → Due 금지 순서로 첫 위반만 알린다.

    테스트 코드: AC-008, AC-009, AC-010, AC-011
    """
    # when·then: 위반 조합으로 만들면 가장 앞선 규칙의 문구로 거절된다
    with raises_with(InvalidValueError, message):
        _parse(**overrides)


def test_progress_only_content_has_no_next_action() -> None:
    """진행사항만 있는 내용은 Next Action·Due가 없다.

    테스트 코드: AC-006
    """
    # when: Next Action이 공백뿐인 내용을 만든다
    content = _parse(next_action="  ", due_date=None)

    # then: Next Action·Due가 없고 Next Action 있음이 거짓이다
    assert content.action == "킥오프"
    assert content.next_action is None
    assert content.due_date is None
    assert content.has_next_action is False


def test_next_only_content_has_no_progress() -> None:
    """Next Action만 있는 내용은 진행사항이 없다.

    테스트 코드: AC-007
    """
    # when: 진행사항이 공백뿐인 내용을 만든다
    content = _parse(action="   ")

    # then: 진행사항이 없고 Next Action과 Due가 있다
    assert content.action is None
    assert content.next_action == "견적 전달"
    assert content.due_date == date(2026, 2, 1)
    assert content.has_next_action is True


def test_content_with_both_parts_has_a_next_action() -> None:
    """진행사항과 Next Action이 모두 있으면 Next Action이 있는 내용이다.

    테스트 코드: AC-001
    """
    # when: 진행사항과 Next Action이 모두 있는 기본 내용을 만든다
    content = _parse()
    # then: Next Action이 있는 내용이다
    assert content.has_next_action is True


def test_blank_parts_are_never_stored_as_empty_strings() -> None:
    """비어 있는 부분은 빈 문자열이 아니라 없음으로 저장된다.

    테스트 코드: AC-006, AC-007
    """
    # when: 진행사항만, Next Action만 있는 내용을 만든다
    progress_only = _parse(action="진행", next_action="\t", due_date=None)
    next_only = _parse(action="", next_action="계획")

    # then: 빈 쪽은 없음이다
    assert progress_only.next_action is None
    assert next_only.action is None


def test_memo_alone_does_not_satisfy_action_or_next() -> None:
    """Memo만 있어서는 진행사항·Next Action 조건을 채우지 못한다.

    테스트 코드: AC-008
    """
    # when·then: 진행사항·Next Action 없이 Memo만 주면 거절된다
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        _parse(action="", next_action="", due_date=None, memo="메모만 있음")


def test_text_fields_have_no_length_limit() -> None:
    """세 텍스트에는 길이 상한이 없다.

    테스트 코드: AC-004
    """
    # given: 5,000자·5,000자·20,000자 이상 텍스트
    long_progress = "가" * 5_000
    long_next = "😀" * 5_000
    long_memo = "memo 메모 😀 " * 2_001  # 반복 단위 10자, trim 후에도 20,000자 이상

    # when: 그 텍스트로 내용을 만든다
    content = _parse(action=long_progress, next_action=long_next, memo=long_memo)

    # then: 잘리지 않고 그대로다
    assert content.action == long_progress
    assert content.next_action == long_next
    assert content.memo == long_memo.strip()
    assert len(content.memo) >= 20_000


def test_texts_are_trimmed_on_both_ends() -> None:
    """세 텍스트의 앞뒤 공백을 지운다.

    테스트 코드: AC-003
    """
    # when: 앞뒤 공백이 낀 텍스트로 내용을 만든다
    content = _parse(action="  킥오프  ", next_action="\t견적 전달\n", memo="  메모  ")

    # then: 공백이 지워진 값이다
    assert (content.action, content.next_action, content.memo) == ("킥오프", "견적 전달", "메모")


def test_a_blank_memo_is_an_empty_string() -> None:
    """공백뿐인 Memo는 빈 문자열이 된다.

    테스트 코드: AC-005
    """
    # when: 공백뿐인 Memo로 내용을 만든다
    content = _parse(memo="   \n ")
    # then: Memo는 빈 문자열이다
    assert content.memo == ""


def test_a_past_due_date_is_allowed() -> None:
    """지난 Due Date도 받는다.

    테스트 코드: AC-003
    """
    # when: 2000-01-01 Due로 내용을 만든다
    content = _parse(due_date=date(2000, 1, 1))
    # then: Due를 그대로 받는다
    assert content.due_date == date(2000, 1, 1)


def test_a_datetime_due_date_is_rejected_because_it_is_not_a_calendar_date() -> None:
    """시각이 있는 값은 날짜가 아니므로 거절한다."""
    # when·then: datetime을 Due로 주면 값 오류다
    with pytest.raises(InvalidValueError):
        _parse(due_date=datetime(2026, 2, 1, 9, 0, tzinfo=UTC))


@pytest.mark.parametrize(
    ("field", "label"), [("action", "진행사항"), ("next_action", "Next Action"), ("memo", "Memo")]
)
def test_nul_characters_are_rejected_in_every_text_field(field: str, label: str) -> None:
    """진행사항·Next Action·Memo의 NUL 문자는 이름이 든 문구로 거절한다.

    테스트 코드: AC-011
    """
    # when·then: 한 칸에 NUL을 넣으면 그 칸 이름이 든 NUL 문구다
    with raises_with(InvalidValueError, f"{label}에는 NUL 문자를 쓸 수 없습니다"):
        _parse(**{field: "가\x00나"})


def test_contents_with_the_same_trimmed_values_are_equal() -> None:
    """공백을 지운 값이 같은 내용은 같다."""
    # when: 공백만 다른 내용, 진행사항이 다른 내용, Due가 다른 내용을 만든다
    padded = _parse(action=" 킥오프 ")
    plain = _parse(action="킥오프")
    other_action = _parse(action="미팅 후속")
    due_feb_1 = _parse(due_date=date(2026, 2, 1))
    due_feb_2 = _parse(due_date=date(2026, 2, 2))
    # then: 공백만 다른 내용은 같고 값이 다르면 다르다
    assert padded == plain
    assert plain != other_action
    assert due_feb_1 != due_feb_2


def test_the_action_type_reference_is_part_of_the_content() -> None:
    """유형 참조는 내용의 일부다."""
    # given: 통화·이메일 유형 참조
    call = make_type_ref("통화")

    # when: 같은 유형의 내용과 다른 유형(이메일)의 내용을 만든다
    with_call = make_action_content(action_type=call)
    with_email = make_action_content(action_type=make_type_ref("이메일"))
    # then: 내용이 유형 참조를 가지고, 유형이 다르면 내용도 다르다
    assert with_call.action_type == call
    assert with_call != with_email


def test_the_type_is_kept_as_given_and_is_not_validated_here() -> None:
    """유형 참조는 이 곳에서 검증하지 않고 준 그대로 둔다."""
    # given: 새 유형 참조
    ref = make_type_ref("웨비나")

    # when: 그 참조로 내용을 만든다
    content = _parse(action_type=ref)
    # then: 준 참조를 그대로 가진다
    assert content.action_type is ref


def test_nul_is_reported_before_the_both_blank_rule() -> None:
    """NUL 검사가 둘 다 빔 검사보다 먼저다.

    테스트 코드: AC-011
    """
    # when·then: 진행사항·Next Action이 비고 Memo에 NUL이 있으면 NUL 문구다
    with raises_with(InvalidValueError, "Memo에는 NUL 문자를 쓸 수 없습니다"):
        _parse(action="", next_action="", due_date=None, memo="가\x00나")
