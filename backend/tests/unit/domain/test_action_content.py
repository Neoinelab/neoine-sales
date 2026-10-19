"""ActionContent(AC-02): 검증 순서·문구·trim·필수, 길이 상한 없음(Q6), NUL 거부.

문구와 순서는 프런트 목업 `validateFields`와 같다(R-11). 서버는 길이를 검사하지 않는다.
"""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal_action.value_objects import ActionContent
from tests.factories import make_action_content
from tests.factories_action_type import make_type_ref
from tests.support.expect import raises_with

PROGRESS_REQUIRED = "진행사항을 입력하세요."
NEXT_ACTION_REQUIRED = "Next Action을 입력하세요."
DUE_DATE_REQUIRED = "Due Date를 입력하세요."


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
        pytest.param({"action": "   ", "next_action": ""}, PROGRESS_REQUIRED, id="progress-first"),
        pytest.param({"action": "", "next_action": "ok"}, PROGRESS_REQUIRED, id="progress-empty"),
        pytest.param({"action": "ok", "next_action": "   "}, NEXT_ACTION_REQUIRED, id="next-blank"),
        pytest.param({"action": "ok", "next_action": ""}, NEXT_ACTION_REQUIRED, id="next-empty"),
        pytest.param({"action": "ok", "due_date": None}, DUE_DATE_REQUIRED, id="due-missing"),
        pytest.param(
            {"action": " ", "next_action": " ", "due_date": None},
            PROGRESS_REQUIRED,
            id="all-missing-reports-progress",
        ),
        pytest.param(
            {"next_action": " ", "due_date": None},
            NEXT_ACTION_REQUIRED,
            id="next-before-due",
        ),
    ],
)
def test_validation_reports_the_first_failing_rule_in_the_mock_order(
    overrides: dict[str, object], message: str
) -> None:
    with raises_with(InvalidValueError, message):
        _parse(**overrides)


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
