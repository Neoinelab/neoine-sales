import pytest

from app.domain.common.contact import Email
from app.domain.common.errors import InvalidValueError
from tests.factories import make_customer_details, make_partner_details


class TestCustomerDetails:
    def test_keeps_all_given_values(self) -> None:
        details = make_customer_details()

        assert details.company_name == "네오인"
        assert details.contact_name == "김철수"
        assert details.contact_title == "팀장"
        assert details.email == Email("kim@neoine.example")
        assert details.employee_count == 120
        assert details.notes == "초기 미팅 완료"

    def test_only_company_and_contact_names_are_required(self) -> None:
        details = make_customer_details(
            contact_title=None, email=None, phone=None, employee_count=None, notes=""
        )

        assert details.contact_title is None
        assert details.email is None
        assert details.phone is None
        assert details.employee_count is None
        assert details.notes == ""

    @pytest.mark.parametrize("field", ["company_name", "contact_name"])
    @pytest.mark.parametrize("value", ["", "   "])
    def test_rejects_blank_required_fields(self, field: str, value: str) -> None:
        with pytest.raises(InvalidValueError):
            make_customer_details(**{field: value})

    def test_strips_text_and_turns_blank_optional_text_into_none(self) -> None:
        details = make_customer_details(
            company_name="  네오인 ", contact_title="   ", notes="  메모  "
        )

        assert details.company_name == "네오인"
        assert details.contact_title is None
        assert details.notes == "메모"

    def test_rejects_negative_employee_count_but_accepts_zero(self) -> None:
        assert make_customer_details(employee_count=0).employee_count == 0
        with pytest.raises(InvalidValueError):
            make_customer_details(employee_count=-1)

    @pytest.mark.parametrize(
        ("field", "max_length"),
        [
            ("company_name", 200),
            ("contact_name", 100),
            ("contact_title", 100),
            ("notes", 2000),
        ],
    )
    def test_enforces_maximum_text_lengths(self, field: str, max_length: int) -> None:
        make_customer_details(**{field: "a" * max_length})
        with pytest.raises(InvalidValueError):
            make_customer_details(**{field: "a" * (max_length + 1)})


class TestPartnerDetails:
    def test_keeps_all_given_values(self) -> None:
        details = make_partner_details()

        assert details.company_name == "한빛파트너스"
        assert details.contact_name == "이영희"
        assert details.contact_title == "이사"
        assert details.email == Email("lee@hanbit.example")

    def test_only_company_and_contact_names_are_required(self) -> None:
        details = make_partner_details(contact_title=None, email=None, phone=None)

        assert details.contact_title is None
        assert details.email is None
        assert details.phone is None

    @pytest.mark.parametrize("field", ["company_name", "contact_name"])
    def test_rejects_blank_required_fields(self, field: str) -> None:
        with pytest.raises(InvalidValueError):
            make_partner_details(**{field: "  "})

    @pytest.mark.parametrize(
        ("field", "max_length"),
        [("company_name", 200), ("contact_name", 100), ("contact_title", 100)],
    )
    def test_enforces_maximum_text_lengths(self, field: str, max_length: int) -> None:
        make_partner_details(**{field: "a" * max_length})
        with pytest.raises(InvalidValueError):
            make_partner_details(**{field: "a" * (max_length + 1)})
