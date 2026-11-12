"""Vendor 이름 규칙: 앞뒤 공백 제거, 빈 값·길이·NUL 거부."""

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.vendor.values import (
    VENDOR_NAME_MAX,
    normalize_vendor_name,
)


def test_vendor_name_limit_is_100() -> None:
    """Vendor 이름 길이 상한은 100이다."""
    # when·then: 상수 값을 확인한다
    assert VENDOR_NAME_MAX == 100


def test_vendor_name_is_trimmed() -> None:
    """Vendor 이름은 앞뒤 공백을 제거한다."""
    # when: 앞뒤에 공백이 있는 이름을 정규화한다
    name = normalize_vendor_name("  SAP ")

    # then: 공백이 없어진다
    assert name == "SAP"


@pytest.mark.parametrize("raw", ["", "   ", "\t"])
def test_blank_vendor_name_is_rejected(raw: str) -> None:
    """비었거나 공백뿐인 Vendor 이름은 거부한다."""
    # when·then: 정규화하면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError) as raised:
        normalize_vendor_name(raw)

    # then: 안내 문구가 맞다
    assert str(raised.value) == "Vendor 이름을 입력하세요."


def test_vendor_name_allows_100_and_rejects_101() -> None:
    """Vendor 이름은 100자까지 허용하고 101자는 거부한다."""
    # when: 100자 이름을 정규화한다
    name = normalize_vendor_name("a" * 100)

    # then: 그대로 통과한다
    assert name == "a" * 100
    # when·then: 101자 이름은 거부한다
    with pytest.raises(InvalidValueError) as raised:
        normalize_vendor_name("a" * 101)

    # then: 안내 문구가 맞다
    assert str(raised.value) == "Vendor 이름은 100자 이내로 입력하세요."


def test_length_is_counted_after_trimming() -> None:
    """길이는 앞뒤 공백을 제거한 뒤에 센다."""
    # when: 공백을 포함하면 102자인 이름을 정규화한다
    name = normalize_vendor_name(" " + "a" * 100 + " ")

    # then: 공백 제거 후 100자라 통과한다
    assert name == "a" * 100


def test_length_counts_code_points() -> None:
    """길이는 코드 포인트 수로 센다."""
    # when: 이모지 100개를 정규화한다
    name = normalize_vendor_name("😀" * 100)

    # then: 통과한다
    assert name == "😀" * 100
    # when·then: 이모지 101개는 거부한다
    with pytest.raises(InvalidValueError):
        normalize_vendor_name("😀" * 101)


def test_nul_in_vendor_name_is_rejected() -> None:
    """Vendor 이름에 NUL 문자가 있으면 거부한다."""
    # when·then: NUL이 든 이름을 정규화하면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        normalize_vendor_name("a\x00b")
