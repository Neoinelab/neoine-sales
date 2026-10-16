"""Deal code 값 객체(R-6, AC-03): `YYYYMMDD-XXXX`(날짜 8자리 - 영문 대문자·숫자 4자리)."""

import dataclasses
import string
from datetime import date

import pytest
from app.domain.deal.code import DEAL_CODE_ALPHABET, SUFFIX_LENGTH, DealCode

from app.domain.common.errors import InvalidValueError


def test_alphabet_is_uppercase_letters_and_digits_and_suffix_is_four_chars() -> None:
    assert string.ascii_uppercase + string.digits == DEAL_CODE_ALPHABET
    assert SUFFIX_LENGTH == 4


def test_issue_joins_the_date_and_the_suffix() -> None:
    assert DealCode.issue(date(2026, 10, 16), "A7K2").value == "20261016-A7K2"


def test_issue_zero_pads_month_and_day() -> None:
    assert DealCode.issue(date(2026, 1, 5), "0009").value == "20260105-0009"


@pytest.mark.parametrize("suffix", ["a7k2", "A7K", "A7K22", "", "A7-2", "A 72", "한글12", "A7K\n"])
def test_issue_rejects_a_suffix_that_is_not_four_uppercase_alphanumerics(suffix: str) -> None:
    with pytest.raises(InvalidValueError):
        DealCode.issue(date(2026, 10, 16), suffix)


@pytest.mark.parametrize(
    "value",
    [
        "20261016-A7K2",
        "20260101-0000",
        "20261231-ZZZZ",
    ],
)
def test_a_well_formed_code_is_accepted_as_is(value: str) -> None:
    assert DealCode(value).value == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "20261016-a7k2",  # 소문자
        "2026101-A7K2",  # 날짜 7자리
        "202610160-A7K2",  # 날짜 9자리
        "20261016-A7K",  # suffix 3자리
        "20261016-A7K22",  # suffix 5자리
        "20261016A7K2",  # 구분자 없음
        "20261016_A7K2",
        "2026101a-A7K2",  # 날짜에 영문
        "20261016-A7K2\n",  # 끝 줄바꿈(정규식 $가 통과시키기 쉬운 값)
        " 20261016-A7K2",
        "DEAL-001",  # 구 형식
    ],
)
def test_a_malformed_code_is_rejected(value: str) -> None:
    with pytest.raises(InvalidValueError):
        DealCode(value)


def test_codes_with_the_same_value_are_equal_and_hashable() -> None:
    first = DealCode("20261016-A7K2")
    second = DealCode.issue(date(2026, 10, 16), "A7K2")

    assert first == second
    assert len({first, second}) == 1
    assert first != DealCode("20261016-A7K3")


def test_the_code_is_immutable() -> None:
    code = DealCode("20261016-A7K2")

    with pytest.raises(dataclasses.FrozenInstanceError):
        code.value = "20261016-ZZZZ"  # type: ignore[misc]


def test_parse_or_none_returns_the_code_for_a_valid_path_value() -> None:
    assert DealCode.parse_or_none("20261016-A7K2") == DealCode("20261016-A7K2")


@pytest.mark.parametrize(
    "raw", ["", "bad", "20261016-a7k2", "20261016-A7K2/", "facets", "20261016-A7K2\n"]
)
def test_parse_or_none_returns_none_for_a_malformed_value(raw: str) -> None:
    assert DealCode.parse_or_none(raw) is None
