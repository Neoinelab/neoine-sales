"""Deal code 값 객체(R-6): `YYYYMMDD-XXXX`(날짜 8자리 - 영문 대문자·숫자 4자리)."""

import dataclasses
import string
from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.code import DEAL_CODE_ALPHABET, SUFFIX_LENGTH, DealCode


def test_alphabet_is_uppercase_letters_and_digits_and_suffix_is_four_chars() -> None:
    """suffix 문자 집합은 대문자·숫자이고 길이는 4자다."""
    # when: 상수를 읽는다
    actual = string.ascii_uppercase + string.digits
    # then: 문자 집합은 대문자+숫자이고 길이는 4다
    assert actual == DEAL_CODE_ALPHABET
    assert SUFFIX_LENGTH == 4


def test_issue_joins_the_date_and_the_suffix() -> None:
    """발급은 날짜와 suffix를 이어 붙인다."""
    # when: 2026-10-16과 A7K2로 발급한다
    value = DealCode.issue(date(2026, 10, 16), "A7K2").value
    # then: 20261016-A7K2다
    assert value == "20261016-A7K2"


def test_issue_zero_pads_month_and_day() -> None:
    """월·일이 한 자리면 0을 채운다."""
    # when: 2026-01-05와 0009로 발급한다
    value = DealCode.issue(date(2026, 1, 5), "0009").value
    # then: 20260105-0009다
    assert value == "20260105-0009"


@pytest.mark.parametrize("suffix", ["a7k2", "A7K", "A7K22", "", "A7-2", "A 72", "한글12", "A7K\n"])
def test_issue_rejects_a_suffix_that_is_not_four_uppercase_alphanumerics(suffix: str) -> None:
    """suffix가 대문자·숫자 4자가 아니면 발급을 거절한다.

    테스트 코드: DD-006
    """
    # when·then: 형식이 틀린 suffix로 발급한다 → 입력값 오류다
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
    """8자리 날짜-대문자·숫자 4자리 형식은 그대로 Deal code가 된다.

    테스트 코드: DD-006
    """
    # when: 형식에 맞는 값으로 Deal code를 만든다
    actual = DealCode(value).value
    # then: 값이 그대로다
    assert actual == value


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
    """소문자·자릿수 오류·구분자 없음·끝 줄바꿈 등 형식이 틀린 값은 Deal code가 될 수 없다.

    테스트 코드: DD-006
    """
    # when·then: 형식이 틀린 값으로 Deal code를 만든다 → 값 오류가 난다
    with pytest.raises(InvalidValueError):
        DealCode(value)


def test_codes_with_the_same_value_are_equal_and_hashable() -> None:
    """같은 값의 Deal code는 서로 같고 해시할 수 있다."""
    # given: 같은 값으로 만든 code 둘
    first = DealCode("20261016-A7K2")
    second = DealCode.issue(date(2026, 10, 16), "A7K2")

    # when·then: code들을 비교한다 → 같은 값은 같고 해시가 하나로 모이며 다른 값은 다르다
    assert first == second
    assert len({first, second}) == 1
    assert first != DealCode("20261016-A7K3")


def test_the_code_is_immutable() -> None:
    """Deal code는 만든 뒤 바꿀 수 없다."""
    # given: Deal code 하나
    code = DealCode("20261016-A7K2")

    # when·then: 값을 바꾸려 한다 → FrozenInstanceError다
    with pytest.raises(dataclasses.FrozenInstanceError):
        code.value = "20261016-ZZZZ"  # type: ignore[misc]


def test_parse_or_none_returns_the_code_for_a_valid_path_value() -> None:
    """경로 값이 형식에 맞으면 해석한 Deal code를 돌려준다.

    테스트 코드: DD-006
    """
    # when: 형식에 맞는 경로 값을 해석한다
    actual = DealCode.parse_or_none("20261016-A7K2")
    # then: 같은 값의 Deal code다
    assert actual == DealCode("20261016-A7K2")


@pytest.mark.parametrize(
    "raw", ["", "bad", "20261016-a7k2", "20261016-A7K2/", "facets", "20261016-A7K2\n"]
)
def test_parse_or_none_returns_none_for_a_malformed_value(raw: str) -> None:
    """경로 값이 형식에 맞지 않으면(끝 줄바꿈·UUID 형태 포함) 없음으로 해석한다.

    테스트 코드: DD-006
    """
    # when: 형식이 틀린 경로 값을 해석한다
    actual = DealCode.parse_or_none(raw)
    # then: None이다
    assert actual is None
