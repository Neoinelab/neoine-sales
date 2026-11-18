"""Deal CSV 내보내기 규칙: 상한 판정·파일 이름·수식 방지·머리글 (DL-R34~R36)."""

from datetime import date

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal.export import (
    EXPORT_HEADER,
    EXPORT_MAX_ROWS,
    check_export_size,
    export_file_name,
    neutralize_formula,
)
from tests.support.expect import raises_with


def test_header_has_fourteen_columns_with_product_after_vendor() -> None:
    """머리글은 14열이고 Product가 Vendor 바로 뒤에 있다."""
    # when: 머리글 상수를 읽는다
    # then: DL-R35의 순서와 같다
    assert EXPORT_HEADER == (
        "Deal", "담당자", "고객사", "파트너사", "Vendor", "Product", "Status", "Forecast",
        "금액(단위:원)", "Expected Close", "최종 업데이트", "Next Action", "Due",
        "Next Action 상태",
    )  # fmt: skip


@pytest.mark.parametrize("total", [0, 1, 9_999, 10_000])
def test_size_up_to_the_limit_is_allowed(total: int) -> None:
    """10,000건까지는 내려받을 수 있다."""
    # when: 상한 이하 건수를 판정한다
    # then: 예외가 없다
    assert EXPORT_MAX_ROWS == 10_000
    check_export_size(total)


@pytest.mark.parametrize(("total", "text"), [(10_001, "10,001"), (1_234_567, "1,234,567")])
def test_size_over_the_limit_is_invalid_value_with_a_comma_separated_count(
    total: int, text: str
) -> None:
    """상한을 넘으면 천 단위 콤마가 든 건수와 함께 InvalidValueError다."""
    # when: 상한을 넘은 건수를 판정한다
    # then: 고정 문구에 건수가 들어간다
    with raises_with(
        InvalidValueError,
        f"내려받을 Deal이 10,000건을 넘습니다({text}건). 조건을 좁혀 다시 시도하세요.",
    ):
        check_export_size(total)


@pytest.mark.parametrize(
    ("day", "name"),
    [(date(2026, 10, 15), "Deals_20261015.csv"), (date(2026, 1, 2), "Deals_20260102.csv")],
)
def test_file_name_is_deals_plus_zero_padded_business_date(day: date, name: str) -> None:
    """파일 이름은 대문자 D의 Deals_ + 0을 채운 YYYYMMDD.csv다."""
    # when: 업무 날짜로 파일 이름을 만든다
    # then: 형식 그대로다
    assert export_file_name(day) == name


@pytest.mark.parametrize("first", ["=", "+", "-", "@", "\t", "\r"])
def test_text_starting_with_a_formula_symbol_gets_a_leading_quote(first: str) -> None:
    """수식 기호(= + - @ 탭 CR)로 시작하면 앞에 작은따옴표가 붙는다."""
    # when: 그 기호로 시작하는 텍스트를 처리한다
    # then: 원문 앞에 '가 붙는다
    assert neutralize_formula(f"{first}SUM(A1)") == f"'{first}SUM(A1)"


@pytest.mark.parametrize("text", ["", "정상", " =SUM(A1)", "a=b", "'=x", "#hash", "\n=x"])
def test_other_text_is_left_unchanged(text: str) -> None:
    """빈 값·일반 글자·공백/줄바꿈으로 시작하는 값·기호가 가운데 있는 값은 그대로다."""
    # when: 위험하지 않은 텍스트를 처리한다
    # then: 같은 값이다
    assert neutralize_formula(text) == text
