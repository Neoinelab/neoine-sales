"""BANT Label 도메인: 구분, 이름 규칙, 엔티티, 중복 규칙, 오류 (AC-10~14).

점수는 없다(LB-01): Label은 구분과 이름만 가진다.
"""

import pytest

from app.domain.bant.entities import BantLabel
from app.domain.bant.errors import (
    BantLabelNotFoundError,
    DuplicateLabelNameError,
    LabelInUseError,
)
from app.domain.bant.rules import ensure_unique_label_name
from app.domain.bant.values import LABEL_NAME_MAX, BantCategory, BantLabelId, normalize_label_name
from app.domain.common.errors import (
    AlreadyExistsError,
    InvalidStateError,
    InvalidValueError,
    NotFoundError,
)
from app.domain.user.value_objects import UserId
from tests.factories import NOW, later
from tests.factories_catalog import make_label
from tests.support.ids import new_id

CREATOR = UserId(new_id())


# --- 구분 ---


def test_categories_are_declared_in_display_order() -> None:
    assert [c.value for c in BantCategory] == ["budget", "authority", "need", "timeline"]


def test_label_name_limit_is_50() -> None:
    assert LABEL_NAME_MAX == 50


# --- 이름 규칙 (AC-12) ---


def test_label_name_trims_surrounding_spaces() -> None:
    assert normalize_label_name("  단독 예산  ") == "단독 예산"


@pytest.mark.parametrize("raw", ["", "   ", "\t"], ids=["empty", "spaces", "tab"])
def test_label_name_rejects_blank(raw: str) -> None:
    with pytest.raises(InvalidValueError) as raised:
        normalize_label_name(raw)

    assert str(raised.value) == "Label 이름을 입력하세요."


def test_label_name_accepts_50_code_points_even_when_they_are_emoji() -> None:
    assert normalize_label_name("😀" * 50) == "😀" * 50


def test_label_name_rejects_51_code_points() -> None:
    with pytest.raises(InvalidValueError) as raised:
        normalize_label_name("😀" * 51)

    assert str(raised.value) == "Label 이름은 50자 이내로 입력하세요."


# --- 엔티티 ---


def test_create_makes_a_custom_label_with_the_creator() -> None:
    label = BantLabel.create(
        entity_id=BantLabelId(new_id()),
        category=BantCategory.NEED,
        name="규제 대응",
        created_by=CREATOR,
        now=NOW,
    )

    assert label.category is BantCategory.NEED
    assert label.name == "규제 대응"
    assert label.is_default is False
    assert label.default_order is None
    assert label.created_by_user_id == CREATOR
    assert label.created_at == label.updated_at == NOW


def test_rename_changes_the_name_and_touches_updated_at() -> None:
    label = make_label(BantCategory.BUDGET, name="예산 없음")

    label.rename("예산 미확보", later(60))

    assert label.name == "예산 미확보"
    assert label.category is BantCategory.BUDGET
    assert label.created_at == NOW
    assert label.updated_at == later(60)


def test_label_in_use_cannot_be_deleted_and_message_has_the_count() -> None:
    label = make_label()

    with pytest.raises(LabelInUseError) as raised:
        label.ensure_deletable(2)

    assert str(raised.value) == "사용 중인 Label은 삭제할 수 없습니다. (Deal 2건)"


def test_unused_label_is_deletable_even_when_it_is_a_default() -> None:
    make_label(is_default=True, default_order=1).ensure_deletable(0)


# --- 같은 구분 안의 이름 중복 (AC-12) ---


def test_unique_label_name_is_case_insensitive_within_the_category() -> None:
    siblings = [make_label(BantCategory.AUTHORITY, name="CEO 보고 완료")]

    with pytest.raises(DuplicateLabelNameError):
        ensure_unique_label_name(siblings, "ceo 보고 완료")


def test_unique_label_name_accepts_a_different_name() -> None:
    siblings = [make_label(BantCategory.AUTHORITY, name="CEO 보고 완료")]

    ensure_unique_label_name(siblings, "CFO 보고 완료")


def test_unique_label_name_ignores_the_label_itself() -> None:
    label = make_label(BantCategory.AUTHORITY, name="CEO 보고 완료")

    ensure_unique_label_name([label], "ceo 보고 완료", self_id=label.id)


def test_unique_label_name_still_conflicts_with_other_labels_when_self_is_given() -> None:
    mine = make_label(BantCategory.NEED, name="가")
    other = make_label(BantCategory.NEED, name="나")

    with pytest.raises(DuplicateLabelNameError):
        ensure_unique_label_name([mine, other], "나", self_id=mine.id)


# --- 오류 종류와 문구 ---


def test_label_errors_map_to_not_found_conflict_and_invalid_state() -> None:
    assert issubclass(BantLabelNotFoundError, NotFoundError)
    assert issubclass(DuplicateLabelNameError, AlreadyExistsError)
    assert issubclass(LabelInUseError, InvalidStateError)


def test_duplicate_label_name_error_message_is_the_user_text() -> None:
    assert str(DuplicateLabelNameError("모름")) == "같은 구분에 이미 있는 Label 이름입니다."


def test_label_not_found_error_keeps_the_identifier() -> None:
    label_id = BantLabelId(new_id())

    assert BantLabelNotFoundError(label_id).identifier == label_id
