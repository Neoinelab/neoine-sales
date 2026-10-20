"""ActionContent(AC-1~4): 진행사항·Next Action은 각각 선택(둘 다 비면 거절).

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
    with raises_with(InvalidValueError, message):
        _parse(**overrides)


def test_progress_only_content_has_no_next_action() -> None:
    content = _parse(next_action="  ", due_date=None)

    assert content.action == "킥오프"
    assert content.next_action is None
    assert content.due_date is None
    assert content.has_next_action is False


def test_next_only_content_has_no_progress() -> None:
    content = _parse(action="   ")

    assert content.action is None
    assert content.next_action == "견적 전달"
    assert content.due_date == date(2026, 2, 1)
    assert content.has_next_action is True


def test_content_with_both_parts_has_a_next_action() -> None:
    assert _parse().has_next_action is True


def test_blank_parts_are_never_stored_as_empty_strings() -> None:
    progress_only = _parse(action="진행", next_action="\t", due_date=None)
    next_only = _parse(action="", next_action="계획")

    assert progress_only.next_action is None
    assert next_only.action is None


def test_memo_alone_does_not_satisfy_action_or_next() -> None:
    with raises_with(InvalidValueError, ACTION_OR_NEXT_REQUIRED):
        _parse(action="", next_action="", due_date=None, memo="메모만 있음")


def test_text_fields_have_no_length_limit() -> None:
    long_progress = "가" * 5_000
    long_next = "😀" * 5_000
    long_memo = "memo 메모 😀 " * 2_001  # 반복 단위 10자, trim 후에도 20,000자 이상

    content = _parse(action=long_progress, next_action=long_next, memo=long_memo)

    assert content.action == long_progress
    assert content.next_action == long_next
    assert content.memo == long_memo.strip()
    assert len(content.memo) >= 20_000


def test_texts_are_trimmed_on_both_ends() -> None:
    content = _parse(action="  킥오프  ", next_action="\t견적 전달\n", memo="  메모  ")

    assert (content.action, content.next_action, content.memo) == ("킥오프", "견적 전달", "메모")


def test_a_blank_memo_is_an_empty_string() -> None:
    assert _parse(memo="   \n ").memo == ""


def test_a_past_due_date_is_allowed() -> None:
    assert _parse(due_date=date(2000, 1, 1)).due_date == date(2000, 1, 1)


def test_a_datetime_due_date_is_rejected_because_it_is_not_a_calendar_date() -> None:
    with pytest.raises(InvalidValueError):
        _parse(due_date=datetime(2026, 2, 1, 9, 0, tzinfo=UTC))


@pytest.mark.parametrize("field", ["action", "next_action", "memo"])
def test_nul_characters_are_rejected_in_every_text_field(field: str) -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        _parse(**{field: "가\x00나"})


def test_contents_with_the_same_trimmed_values_are_equal() -> None:
    assert _parse(action=" 킥오프 ") == _parse(action="킥오프")
    assert _parse(action="킥오프") != _parse(action="미팅 후속")
    assert _parse(due_date=date(2026, 2, 1)) != _parse(due_date=date(2026, 2, 2))


def test_the_action_type_reference_is_part_of_the_content() -> None:
    call = make_type_ref("통화")

    assert make_action_content(action_type=call).action_type == call
    assert make_action_content(action_type=call) != make_action_content(
        action_type=make_type_ref("이메일")
    )


def test_the_type_is_kept_as_given_and_is_not_validated_here() -> None:
    ref = make_type_ref("웨비나")

    assert _parse(action_type=ref).action_type is ref
