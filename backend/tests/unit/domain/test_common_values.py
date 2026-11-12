from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.errors import DomainError, InvalidValueError
from app.domain.common.money import Money
from app.domain.common.validation import optional_text, require_aware, required_text


class TestRequiredText:
    def test_strips_surrounding_whitespace(self) -> None:
        """앞뒤 공백이 제거된 필수 텍스트를 돌려주는지 확인한다."""
        # when: 공백이 붙은 텍스트를 검증한다
        result = required_text("  네오인  ", "회사명", max_length=10)
        # then: 공백이 제거된다
        assert result == "네오인"

    @pytest.mark.parametrize("value", ["", "   ", "\t\n"])
    def test_rejects_blank_text(self, value: str) -> None:
        """빈 문자열과 공백뿐인 텍스트는 거절하는지 확인한다."""
        # when·then: 빈 텍스트를 검증하면 필드 이름이 든 오류가 난다
        with pytest.raises(InvalidValueError, match="회사명"):
            required_text(value, "회사명", max_length=10)

    def test_rejects_text_longer_than_max_length(self) -> None:
        """최대 길이를 넘는 텍스트는 거절하는지 확인한다."""
        # when·then: 최대 길이보다 1자 긴 텍스트를 검증하면 오류가 난다
        with pytest.raises(InvalidValueError, match="회사명"):
            required_text("a" * 11, "회사명", max_length=10)

    def test_accepts_text_exactly_at_max_length(self) -> None:
        """최대 길이와 같은 텍스트는 허용하는지 확인한다."""
        # when: 최대 길이 텍스트를 검증한다
        result = required_text("a" * 10, "회사명", max_length=10)
        # then: 그대로 돌려준다
        assert result == "a" * 10


class TestOptionalText:
    def test_returns_none_for_none_and_blank(self) -> None:
        """None과 공백뿐인 텍스트는 None으로 돌려주는지 확인한다."""
        # when: None과 공백 텍스트를 검증한다
        result = optional_text(None, "직함", max_length=5)
        # then: 모두 None이다
        assert result is None
        assert optional_text("   ", "직함", max_length=5) is None

    def test_strips_and_validates_length(self) -> None:
        """공백을 제거하고 길이를 검증하는지 확인한다."""
        # when: 공백이 붙은 텍스트를 검증한다
        result = optional_text(" 팀장 ", "직함", max_length=5)
        # then: 공백이 제거된 값을 돌려준다
        assert result == "팀장"
        # when·then: 최대 길이를 넘는 텍스트는 오류가 난다
        with pytest.raises(InvalidValueError, match="직함"):
            optional_text("a" * 6, "직함", max_length=5)


class TestRequireAware:
    def test_accepts_timezone_aware_datetime(self) -> None:
        """시간대가 있는 시각은 그대로 돌려주는지 확인한다."""
        # given: 시간대가 있는 시각이 있다
        value = datetime(2026, 1, 1, tzinfo=UTC)

        # when: 검증한다
        result = require_aware(value, "시각")
        # then: 같은 값을 돌려준다
        assert result == value

    def test_rejects_naive_datetime(self) -> None:
        """시간대 없는 시각은 거절하는지 확인한다."""
        # when·then: 시간대 없는 시각을 검증하면 오류가 난다
        with pytest.raises(InvalidValueError, match="시각"):
            require_aware(datetime(2026, 1, 1), "시각")


class TestEmail:
    def test_normalizes_to_lowercase_and_strips(self) -> None:
        """이메일을 소문자로 바꾸고 공백을 제거하는지 확인한다."""
        # when: 대소문자와 공백이 섞인 주소를 만든다
        result = Email("  Kim@Neoine.Example ").value
        # then: 정규화된 값이 된다
        assert result == "kim@neoine.example"

    @pytest.mark.parametrize(
        "value",
        ["", "no-at-sign", "a@b", "a b@c.com", "@c.com", "a@.com", "a@@c.com"],
    )
    def test_rejects_invalid_format(self, value: str) -> None:
        """형식이 잘못된 이메일을 거절하는지 확인한다."""
        # when·then: 잘못된 주소로 만들면 오류가 난다
        with pytest.raises(InvalidValueError):
            Email(value)

    def test_rejects_address_longer_than_254_chars(self) -> None:
        """254자를 넘는 이메일을 거절하는지 확인한다."""
        # when·then: 254자를 넘는 주소로 만들면 오류가 난다
        with pytest.raises(InvalidValueError):
            Email("a" * 250 + "@x.com")

    def test_equal_when_normalized_values_match(self) -> None:
        """정규화한 값이 같으면 같은 이메일로 보는지 확인한다."""
        # when: 대소문자만 다른 두 주소를 비교한다
        result = Email("A@x.com")
        # then: 같다
        assert result == Email("a@x.com")


class TestPhoneNumber:
    @pytest.mark.parametrize(
        "value",
        ["010-1234-5678", "+82 10 1234 5678", "(02) 123-4567", "0212345678"],
    )
    def test_accepts_common_formats(self, value: str) -> None:
        """흔한 전화번호 형식을 허용하는지 확인한다."""
        # when: 일반적인 형식으로 만든다
        result = PhoneNumber(value).value
        # then: 값이 그대로 유지된다
        assert result == value

    def test_strips_surrounding_whitespace(self) -> None:
        """전화번호 앞뒤 공백을 제거하는지 확인한다."""
        # when: 공백이 붙은 번호로 만든다
        result = PhoneNumber("  010-1234-5678 ").value
        # then: 공백이 제거된다
        assert result == "010-1234-5678"

    @pytest.mark.parametrize("value", ["", "abc", "010-1234-567a", "123456", "1" * 16])
    def test_rejects_invalid_numbers(self, value: str) -> None:
        """잘못된 전화번호를 거절하는지 확인한다."""
        # when·then: 잘못된 번호로 만들면 오류가 난다
        with pytest.raises(InvalidValueError):
            PhoneNumber(value)


class TestMoney:
    def test_defaults_to_krw(self) -> None:
        """통화를 생략하면 KRW인지 확인한다."""
        # when: 통화 없이 금액을 만든다
        money = Money(Decimal("1000"))

        # then: 통화는 KRW이고 금액은 그대로다
        assert money.currency == "KRW"
        assert money.amount == Decimal("1000")

    def test_accepts_zero(self) -> None:
        """0원을 허용하는지 확인한다."""
        # when: 0으로 만든다
        result = Money(Decimal(0)).amount
        # then: 금액이 0이다
        assert result == Decimal(0)

    def test_rejects_negative_amount(self) -> None:
        """음수 금액을 거절하는지 확인한다."""
        # when·then: 음수로 만들면 오류가 난다
        with pytest.raises(InvalidValueError):
            Money(Decimal("-1"))

    @pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity")])
    def test_rejects_non_finite_amount(self, amount: Decimal) -> None:
        """NaN과 무한대 금액을 거절하는지 확인한다."""
        # when·then: 유한하지 않은 값으로 만들면 오류가 난다
        with pytest.raises(InvalidValueError):
            Money(amount)

    @pytest.mark.parametrize("currency", ["", "kr", "krw", "KRWW", "K1W"])
    def test_rejects_invalid_currency_code(self, currency: str) -> None:
        """대문자 3자가 아닌 통화 코드를 거절하는지 확인한다."""
        # when·then: 잘못된 통화 코드로 만들면 오류가 난다
        with pytest.raises(InvalidValueError):
            Money(Decimal(1), currency)

    def test_accepts_up_to_four_decimal_places(self) -> None:
        """소수 4자리까지는 허용하는지 확인한다."""
        # when: 소수 4자리 금액으로 만든다
        result = Money(Decimal("1234.5678")).amount
        # then: 값이 유지된다
        assert result == Decimal("1234.5678")

    def test_rejects_more_than_four_decimal_places(self) -> None:
        """소수 5자리 이상은 거절하는지 확인한다."""
        # when·then: 소수 5자리 금액으로 만들면 소수 오류가 난다
        with pytest.raises(InvalidValueError, match="소수"):
            Money(Decimal("1.23456"))

    def test_accepts_the_largest_storable_amount(self) -> None:
        """저장 가능한 최대 금액을 허용하는지 확인한다."""
        # when: 정수 16자리와 소수 4자리 금액으로 만든다
        result = Money(Decimal("9999999999999999.9999")).amount
        # then: 값이 유지된다
        assert result == Decimal("9999999999999999.9999")

    def test_rejects_amount_beyond_sixteen_integer_digits(self) -> None:
        """정수 16자리를 넘는 금액을 거절하는지 확인한다."""
        # when·then: 정수 17자리 금액으로 만들면 큰 값 오류가 난다
        with pytest.raises(InvalidValueError, match="큰"):
            Money(Decimal("10000000000000000"))


def test_invalid_value_error_is_a_domain_error_and_value_error() -> None:
    """InvalidValueError가 DomainError이자 ValueError인지 확인한다."""
    # when: InvalidValueError를 만든다
    error = InvalidValueError("x")

    # then: DomainError이고 ValueError이기도 하다
    assert isinstance(error, DomainError)
    assert isinstance(error, ValueError)
