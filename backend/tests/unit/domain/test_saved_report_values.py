"""저장 리포트 값 규칙(AC2): 이름 1~100자, 설명 0~1,000자, 공개 범위 두 값, NUL 거절."""

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
    assert REPORT_NAME_MAX == 100
    assert REPORT_DESCRIPTION_MAX == 1000


def test_report_name_is_trimmed() -> None:
    assert normalize_report_name("  a  ") == "a"


def test_report_name_of_100_characters_is_accepted() -> None:
    assert normalize_report_name("가" * 100) == "가" * 100


def test_report_name_length_is_counted_after_trimming() -> None:
    assert normalize_report_name(" " + "가" * 100 + " ") == "가" * 100


def test_report_name_of_101_characters_is_rejected_with_the_user_message() -> None:
    with raises_with(InvalidValueError, "리포트 이름은 100자 이내로 입력하세요."):
        normalize_report_name("가" * 101)


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"], ids=["empty", "spaces", "tab-newline"])
def test_blank_report_name_is_rejected_with_the_user_message(raw: str) -> None:
    with raises_with(InvalidValueError, "리포트 이름을 입력하세요."):
        normalize_report_name(raw)


def test_nul_in_report_name_is_rejected_even_when_surrounded_by_spaces() -> None:
    with pytest.raises(InvalidValueError):
        normalize_report_name(" a\x00b ")


def test_report_description_may_be_empty_and_is_trimmed() -> None:
    assert normalize_report_description("") == ""
    assert normalize_report_description("   ") == ""
    assert normalize_report_description("  설명  ") == "설명"


def test_report_description_of_1000_characters_is_accepted() -> None:
    assert normalize_report_description("a" * 1000) == "a" * 1000


def test_report_description_of_1001_characters_is_rejected_with_the_user_message() -> None:
    with raises_with(InvalidValueError, "설명은 1,000자 이내로 입력하세요."):
        normalize_report_description("a" * 1001)


def test_nul_in_report_description_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        normalize_report_description("a\x00b")


def test_visibility_parses_public_and_private() -> None:
    assert ReportVisibility.parse("public") is ReportVisibility.PUBLIC
    assert ReportVisibility.parse("private") is ReportVisibility.PRIVATE
    assert ReportVisibility.PUBLIC.value == "public"
    assert ReportVisibility.PRIVATE.value == "private"


@pytest.mark.parametrize("raw", ["PUBLIC", "shared", "", " public", 1, None, True])
def test_visibility_rejects_anything_else_with_the_user_message(raw: object) -> None:
    with raises_with(InvalidValueError, "공개 범위는 public 또는 private입니다."):
        ReportVisibility.parse(raw)
