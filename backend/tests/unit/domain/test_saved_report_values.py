"""저장 리포트 값 규칙: 이름 1~100자, 설명 0~1,000자, 공개 범위 두 값, NUL 거절."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.saved_report.values import (
    REPORT_DESCRIPTION_MAX,
    REPORT_NAME_MAX,
    ReportVisibility,
    normalize_report_description,
    normalize_report_name,
)
from tests.support.expect import raises_with


def test_report_limits_are_100_and_1000() -> None:
    """이름은 100자, 설명은 1,000자까지라는 상수가 명세와 같다."""
    # when: 상수를 읽는다
    name_max, description_max = REPORT_NAME_MAX, REPORT_DESCRIPTION_MAX
    # then: 100과 1000이다
    assert name_max == 100
    assert description_max == 1000


def test_report_name_is_trimmed() -> None:
    """이름은 앞뒤 공백을 지운다."""
    # when: 앞뒤 공백이 있는 이름을 정규화한다
    name = normalize_report_name("  a  ")
    # then: 앞뒤 공백이 지워진다
    assert name == "a"


def test_report_name_of_100_characters_is_accepted() -> None:
    """100자 이름은 받는다."""
    # when: 100자 이름을 정규화한다
    name = normalize_report_name("가" * 100)
    # then: 그대로 나온다
    assert name == "가" * 100


def test_report_name_length_is_counted_after_trimming() -> None:
    """이름 길이는 공백을 지운 뒤 센다."""
    # when: 공백을 붙인 100자 이름을 정규화한다
    name = normalize_report_name(" " + "가" * 100 + " ")
    # then: 공백이 지워져 100자 이름으로 받는다
    assert name == "가" * 100


def test_report_name_of_101_characters_is_rejected_with_the_user_message() -> None:
    """101자 이름은 사용자 문구로 거절한다."""
    # when·then: 101자 이름을 정규화하면 값 오류와 문구다
    with raises_with(InvalidValueError, "리포트 이름은 100자 이내로 입력하세요."):
        normalize_report_name("가" * 101)


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"], ids=["empty", "spaces", "tab-newline"])
def test_blank_report_name_is_rejected_with_the_user_message(raw: str) -> None:
    """비었거나 공백뿐인 이름은 사용자 문구로 거절한다."""
    # when·then: 빈 이름을 정규화하면 값 오류와 문구다
    with raises_with(InvalidValueError, "리포트 이름을 입력하세요."):
        normalize_report_name(raw)


def test_nul_in_report_name_is_rejected_even_when_surrounded_by_spaces() -> None:
    """공백으로 감싸도 이름의 NUL 문자는 거절한다."""
    # when·then: NUL이 든 이름을 정규화하면 NUL 문구의 값 오류다
    with raises_with(InvalidValueError, "리포트 이름에는 NUL 문자를 쓸 수 없습니다"):
        normalize_report_name(" a\x00b ")


def test_report_description_may_be_empty_and_is_trimmed() -> None:
    """설명은 빌 수 있고 앞뒤 공백을 지운다."""
    # when: 빈 설명·공백뿐인 설명·공백이 붙은 설명을 정규화한다
    empty = normalize_report_description("")
    blank = normalize_report_description("   ")
    padded = normalize_report_description("  설명  ")
    # then: 빈 설명·공백뿐인 설명은 빈 문자열, 앞뒤 공백은 지워진다
    assert empty == ""
    assert blank == ""
    assert padded == "설명"


def test_report_description_of_1000_characters_is_accepted() -> None:
    """1,000자 설명은 받는다."""
    # when: 1,000자 설명을 정규화한다
    description = normalize_report_description("a" * 1000)
    # then: 그대로 나온다
    assert description == "a" * 1000


def test_report_description_of_1001_characters_is_rejected_with_the_user_message() -> None:
    """1,001자 설명은 사용자 문구로 거절한다."""
    # when·then: 1,001자 설명을 정규화하면 값 오류와 문구다
    with raises_with(InvalidValueError, "설명은 1,000자 이내로 입력하세요."):
        normalize_report_description("a" * 1001)


def test_nul_in_report_description_is_rejected() -> None:
    """설명의 NUL 문자는 거절한다."""
    # when·then: NUL이 든 설명을 정규화하면 NUL 문구의 값 오류다
    with raises_with(InvalidValueError, "설명에는 NUL 문자를 쓸 수 없습니다"):
        normalize_report_description("a\x00b")


def test_visibility_parses_public_and_private() -> None:
    """공개 범위는 public과 private를 받는다."""
    # when: 두 값을 해석한다
    public = ReportVisibility.parse("public")
    private = ReportVisibility.parse("private")
    # then: 각각의 멤버로 해석되고 값 문자열이 같다
    assert public is ReportVisibility.PUBLIC
    assert private is ReportVisibility.PRIVATE
    assert ReportVisibility.PUBLIC.value == "public"
    assert ReportVisibility.PRIVATE.value == "private"


@pytest.mark.parametrize("raw", ["PUBLIC", "shared", "", " public", 1, None, True])
def test_visibility_rejects_anything_else_with_the_user_message(raw: object) -> None:
    """그 밖의 값(대소문자·공백·숫자·None)은 사용자 문구로 거절한다."""
    # when·then: 해석하면 값 오류와 문구다
    with raises_with(InvalidValueError, "공개 범위는 public 또는 private입니다."):
        ReportVisibility.parse(raw)
