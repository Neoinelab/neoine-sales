from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.errors import DomainError, InvalidValueError
from app.domain.common.money import Money
from app.domain.common.validation import optional_text, require_aware, required_text


class TestRequiredText:
    def test_strips_surrounding_whitespace(self) -> None:
        assert required_text("  네오인  ", "회사명", max_length=10) == "네오인"

    @pytest.mark.parametrize("value", ["", "   ", "\t\n"])
    def test_rejects_blank_text(self, value: str) -> None:
        with pytest.raises(InvalidValueError, match="회사명"):
            required_text(value, "회사명", max_length=10)

    def test_rejects_text_longer_than_max_length(self) -> None:
        with pytest.raises(InvalidValueError, match="회사명"):
            required_text("a" * 11, "회사명", max_length=10)

    def test_accepts_text_exactly_at_max_length(self) -> None:
        assert required_text("a" * 10, "회사명", max_length=10) == "a" * 10


class TestOptionalText:
    def test_returns_none_for_none_and_blank(self) -> None:
        assert optional_text(None, "직함", max_length=5) is None
        assert optional_text("   ", "직함", max_length=5) is None

    def test_strips_and_validates_length(self) -> None:
        assert optional_text(" 팀장 ", "직함", max_length=5) == "팀장"
        with pytest.raises(InvalidValueError, match="직함"):
            optional_text("a" * 6, "직함", max_length=5)


class TestRequireAware:
    def test_accepts_timezone_aware_datetime(self) -> None:
        value = datetime(2026, 1, 1, tzinfo=UTC)

        assert require_aware(value, "시각") == value

    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(InvalidValueError, match="시각"):
            require_aware(datetime(2026, 1, 1), "시각")


class TestEmail:
    def test_normalizes_to_lowercase_and_strips(self) -> None:
        assert Email("  Kim@Neoine.Example ").value == "kim@neoine.example"

    @pytest.mark.parametrize(
        "value",
        ["", "no-at-sign", "a@b", "a b@c.com", "@c.com", "a@.com", "a@@c.com"],
    )
    def test_rejects_invalid_format(self, value: str) -> None:
        with pytest.raises(InvalidValueError):
            Email(value)

    def test_rejects_address_longer_than_254_chars(self) -> None:
        with pytest.raises(InvalidValueError):
            Email("a" * 250 + "@x.com")

    def test_equal_when_normalized_values_match(self) -> None:
        assert Email("A@x.com") == Email("a@x.com")


class TestPhoneNumber:
    @pytest.mark.parametrize(
        "value",
        ["010-1234-5678", "+82 10 1234 5678", "(02) 123-4567", "0212345678"],
    )
    def test_accepts_common_formats(self, value: str) -> None:
        assert PhoneNumber(value).value == value

    def test_strips_surrounding_whitespace(self) -> None:
        assert PhoneNumber("  010-1234-5678 ").value == "010-1234-5678"

    @pytest.mark.parametrize("value", ["", "abc", "010-1234-567a", "123456", "1" * 16])
    def test_rejects_invalid_numbers(self, value: str) -> None:
        with pytest.raises(InvalidValueError):
            PhoneNumber(value)


class TestMoney:
    def test_defaults_to_krw(self) -> None:
        money = Money(Decimal("1000"))

        assert money.currency == "KRW"
        assert money.amount == Decimal("1000")

    def test_accepts_zero(self) -> None:
        assert Money(Decimal(0)).amount == Decimal(0)

    def test_rejects_negative_amount(self) -> None:
        with pytest.raises(InvalidValueError):
            Money(Decimal("-1"))

    @pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity")])
    def test_rejects_non_finite_amount(self, amount: Decimal) -> None:
        with pytest.raises(InvalidValueError):
            Money(amount)

    @pytest.mark.parametrize("currency", ["", "kr", "krw", "KRWW", "K1W"])
    def test_rejects_invalid_currency_code(self, currency: str) -> None:
        with pytest.raises(InvalidValueError):
            Money(Decimal(1), currency)

    def test_accepts_up_to_four_decimal_places(self) -> None:
        assert Money(Decimal("1234.5678")).amount == Decimal("1234.5678")

    def test_rejects_more_than_four_decimal_places(self) -> None:
        with pytest.raises(InvalidValueError, match="소수"):
            Money(Decimal("1.23456"))

    def test_accepts_the_largest_storable_amount(self) -> None:
        assert Money(Decimal("9999999999999999.9999")).amount == Decimal("9999999999999999.9999")

    def test_rejects_amount_beyond_sixteen_integer_digits(self) -> None:
        with pytest.raises(InvalidValueError, match="큰"):
            Money(Decimal("10000000000000000"))


def test_invalid_value_error_is_a_domain_error_and_value_error() -> None:
    error = InvalidValueError("x")

    assert isinstance(error, DomainError)
    assert isinstance(error, ValueError)
