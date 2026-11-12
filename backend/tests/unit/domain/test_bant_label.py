"""BANT Label 도메인: 구분, 이름 규칙, 엔티티, 중복 규칙, 오류.

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
    """구분은 화면 표시 순서(예산, 권한, 필요, 시기)로 선언돼 있다."""
    # when·then: 구분 값을 선언 순서대로 나열하면 표시 순서와 같다
    assert [c.value for c in BantCategory] == ["budget", "authority", "need", "timeline"]


def test_label_name_limit_is_50() -> None:
    """Label 이름 최대 길이는 50이다."""
    # when·then: 상수가 50이다
    assert LABEL_NAME_MAX == 50


# --- 이름 규칙 ---


def test_label_name_trims_surrounding_spaces() -> None:
    """Label 이름의 앞뒤 공백은 제거한다."""
    # when: 앞뒤에 공백이 있는 이름을 정규화한다
    name = normalize_label_name("  단독 예산  ")
    # then: 공백이 제거된다
    assert name == "단독 예산"


@pytest.mark.parametrize("raw", ["", "   ", "\t"], ids=["empty", "spaces", "tab"])
def test_label_name_rejects_blank(raw: str) -> None:
    """빈 이름이나 공백뿐인 이름은 거부한다."""
    # when·then: 빈 이름을 정규화하면 값 오류다
    with pytest.raises(InvalidValueError) as raised:
        normalize_label_name(raw)
    # then: 입력 안내 문구다
    assert str(raised.value) == "Label 이름을 입력하세요."


def test_label_name_accepts_50_code_points_even_when_they_are_emoji() -> None:
    """이모지여도 50 코드 포인트까지는 허용한다."""
    # when: 이모지 50개로 정규화한다
    name = normalize_label_name("😀" * 50)
    # then: 그대로 통과한다
    assert name == "😀" * 50


def test_label_name_rejects_51_code_points() -> None:
    """51 코드 포인트는 거부한다."""
    # when·then: 이모지 51개로 정규화하면 값 오류다
    with pytest.raises(InvalidValueError) as raised:
        normalize_label_name("😀" * 51)
    # then: 길이 안내 문구다
    assert str(raised.value) == "Label 이름은 50자 이내로 입력하세요."


# --- 엔티티 ---


def test_create_makes_a_custom_label_with_the_creator() -> None:
    """create는 생성자를 기록한 사용자 정의 Label을 만든다."""
    # when: Label을 생성한다
    label = BantLabel.create(
        entity_id=BantLabelId(new_id()),
        category=BantCategory.NEED,
        name="규제 대응",
        created_by=CREATOR,
        now=NOW,
    )
    # then: 사용자 정의 Label이며 생성자와 시각이 기록된다
    assert label.category is BantCategory.NEED
    assert label.name == "규제 대응"
    assert label.is_default is False
    assert label.default_order is None
    assert label.created_by_user_id == CREATOR
    assert label.created_at == label.updated_at == NOW


def test_rename_changes_the_name_and_touches_updated_at() -> None:
    """이름을 바꾸면 수정 시각만 갱신된다."""
    # given: 예산 구분 Label
    label = make_label(BantCategory.BUDGET, name="예산 없음")
    # when: 이름을 바꾼다
    label.rename("예산 미확보", later(60))
    # then: 이름과 수정 시각만 바뀐다
    assert label.name == "예산 미확보"
    assert label.category is BantCategory.BUDGET
    assert label.created_at == NOW
    assert label.updated_at == later(60)


def test_label_in_use_cannot_be_deleted_and_message_has_the_count() -> None:
    """사용 중인 Label은 삭제할 수 없고 문구에 건수가 들어간다."""
    # given: Label 하나
    label = make_label()
    # when·then: 2건이 쓰는 상태로 삭제 가능 여부를 확인하면 사용 중 오류다
    with pytest.raises(LabelInUseError) as raised:
        label.ensure_deletable(2)
    # then: 문구에 Deal 건수가 있다
    assert str(raised.value) == "사용 중인 Label은 삭제할 수 없습니다. (Deal 2건)"


def test_unused_label_is_deletable_even_when_it_is_a_default() -> None:
    """쓰이지 않는 Label은 기본 Label이어도 삭제할 수 있다."""
    # when·then: 사용 0건인 기본 Label의 삭제 가능 확인은 오류 없이 끝난다
    make_label(is_default=True, default_order=1).ensure_deletable(0)


# --- 같은 구분 안의 이름 중복 ---


def test_unique_label_name_is_case_insensitive_within_the_category() -> None:
    """같은 구분 안에서는 대소문자를 무시하고 이름이 중복된다."""
    # given: 같은 구분의 Label
    siblings = [make_label(BantCategory.AUTHORITY, name="CEO 보고 완료")]
    # when·then: 대소문자만 다른 이름을 검사하면 중복 오류다
    with pytest.raises(DuplicateLabelNameError):
        ensure_unique_label_name(siblings, "ceo 보고 완료")


def test_unique_label_name_accepts_a_different_name() -> None:
    """다른 이름은 중복이 아니다."""
    # given: 같은 구분의 Label
    siblings = [make_label(BantCategory.AUTHORITY, name="CEO 보고 완료")]
    # when·then: 다른 이름을 검사하면 오류 없이 끝난다
    ensure_unique_label_name(siblings, "CFO 보고 완료")


def test_unique_label_name_ignores_the_label_itself() -> None:
    """자기 자신과 같은 이름은 중복으로 보지 않는다."""
    # given: Label 하나
    label = make_label(BantCategory.AUTHORITY, name="CEO 보고 완료")
    # when·then: 자기 id를 주고 같은 이름을 검사하면 오류 없이 끝난다
    ensure_unique_label_name([label], "ceo 보고 완료", self_id=label.id)


def test_unique_label_name_still_conflicts_with_other_labels_when_self_is_given() -> None:
    """자기 id를 줘도 다른 Label과 같은 이름이면 중복이다."""
    # given: 같은 구분의 Label 두 개
    mine = make_label(BantCategory.NEED, name="가")
    other = make_label(BantCategory.NEED, name="나")
    # when·then: 내 id를 주고 다른 Label의 이름을 검사하면 중복 오류다
    with pytest.raises(DuplicateLabelNameError):
        ensure_unique_label_name([mine, other], "나", self_id=mine.id)


# --- 오류 종류와 문구 ---


def test_label_errors_map_to_not_found_conflict_and_invalid_state() -> None:
    """Label 오류는 없음·충돌·상태 오류 계열로 매핑된다."""
    # when·then: 각 오류의 상위 계열을 확인한다
    assert issubclass(BantLabelNotFoundError, NotFoundError)
    assert issubclass(DuplicateLabelNameError, AlreadyExistsError)
    assert issubclass(LabelInUseError, InvalidStateError)


def test_duplicate_label_name_error_message_is_the_user_text() -> None:
    """이름 중복 오류의 메시지는 사용자용 문구다."""
    # when: 중복 오류를 만든다
    error = DuplicateLabelNameError("모름")
    # then: 고정된 사용자 문구다
    assert str(error) == "같은 구분에 이미 있는 Label 이름입니다."


def test_label_not_found_error_keeps_the_identifier() -> None:
    """Label 없음 오류는 식별자를 보존한다."""
    # given: Label id
    label_id = BantLabelId(new_id())
    # when: 없음 오류를 만든다
    error = BantLabelNotFoundError(label_id)
    # then: 식별자가 보존된다
    assert error.identifier == label_id
