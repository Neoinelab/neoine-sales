from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.common.money import Money
from app.domain.customer.value_objects import CustomerId
from app.domain.deal.value_objects import DealCode
from app.domain.partner.value_objects import PartnerId
from tests.factories import make_deal_details


class TestDealCode:
    def test_normalizes_to_uppercase_and_strips(self) -> None:
        assert DealCode("  deal-001 ").value == "DEAL-001"

    @pytest.mark.parametrize("value", ["A", "2026.Q1_A-1", "D" * 50])
    def test_accepts_letters_digits_and_separators(self, value: str) -> None:
        assert DealCode(value).value == value.upper()

    @pytest.mark.parametrize("value", ["", "  ", "-A", ".A", "A B", "A!", "한글", "D" * 51])
    def test_rejects_invalid_codes(self, value: str) -> None:
        with pytest.raises(InvalidValueError):
            DealCode(value)

    def test_codes_equal_regardless_of_case(self) -> None:
        assert DealCode("a-1") == DealCode("A-1")


class TestDealDetails:
    def test_keeps_all_seven_business_fields(self) -> None:
        details = make_deal_details()

        assert details.code == DealCode("DEAL-001")
        assert details.name == "ERP 구축"
        assert details.owner == "박영업"
        assert details.vendor == "SAP"
        assert details.solution == "S/4HANA"
        assert details.revenue == Money(Decimal("150000000"))
        assert details.revenue_date == date(2026, 6, 30)

    def test_partner_is_optional_and_customer_is_kept(self) -> None:
        customer_id = CustomerId(uuid4())
        partner_id = PartnerId(uuid4())

        without = make_deal_details(customer_id=customer_id)
        with_partner = make_deal_details(customer_id=customer_id, partner_id=partner_id)

        assert without.partner_id is None
        assert with_partner.partner_id == partner_id
        assert with_partner.customer_id == customer_id

    @pytest.mark.parametrize("field", ["name", "owner", "vendor", "solution"])
    @pytest.mark.parametrize("value", ["", "   "])
    def test_rejects_blank_required_text(self, field: str, value: str) -> None:
        with pytest.raises(InvalidValueError):
            make_deal_details(**{field: value})

    def test_strips_text_fields(self) -> None:
        details = make_deal_details(name="  ERP  ", owner=" 박영업 ")

        assert details.name == "ERP"
        assert details.owner == "박영업"

    @pytest.mark.parametrize(
        ("field", "max_length"),
        [("name", 200), ("owner", 100), ("vendor", 100), ("solution", 200)],
    )
    def test_enforces_maximum_text_lengths(self, field: str, max_length: int) -> None:
        make_deal_details(**{field: "a" * max_length})
        with pytest.raises(InvalidValueError):
            make_deal_details(**{field: "a" * (max_length + 1)})
