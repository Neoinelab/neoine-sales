"""계약 요청 스키마와 Deal 요청의 Won 이탈 선택 필드(AC7·AC11·D12)."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.application.deal.inputs import DealChangeInput, DealPatchInput
from app.application.deal_action.inputs import DealActionInput
from app.domain.license_contract.values import (
    ContractFields,
    InspectionCycle,
    LicenseTerm,
    TermUnit,
)
from app.web.schemas.deal import DealPatchRequest
from app.web.schemas.deal_action import DealActionCreateRequest
from app.web.schemas.deal_change import DealChangeRequest
from app.web.schemas.license_contract import LicenseContractFieldsRequest, LicenseIssueRequest

ACTION = {"action_type": {"name": "미팅"}, "action": "킥오프", "next_action": "", "memo": ""}


def test_fields_request_defaults_are_empty_text_and_no_inspection() -> None:
    request = LicenseContractFieldsRequest()

    assert (request.tech_owner, request.inspection_cycle, request.note) == ("", "none", "")


def test_fields_request_maps_to_the_domain_fields() -> None:
    request = LicenseContractFieldsRequest(
        tech_owner=" 이기술 ", inspection_cycle="yearly", note="메모"
    )

    assert request.to_fields() == ContractFields(
        tech_owner="이기술", inspection=InspectionCycle.YEARLY, note="메모"
    )


@pytest.mark.parametrize("field", ["customer", "vendor", "product", "partner", "sales_owner"])
def test_fields_request_rejects_the_deal_owned_columns(field: str) -> None:
    with pytest.raises(ValidationError):
        LicenseContractFieldsRequest(**{field: "x"})


def test_fields_request_rejects_a_tech_owner_over_100_chars() -> None:
    with pytest.raises(ValidationError):
        LicenseContractFieldsRequest(tech_owner="가" * 101)


def test_fields_request_accepts_a_tech_owner_of_100_chars() -> None:
    assert len(LicenseContractFieldsRequest(tech_owner="가" * 100).tech_owner) == 100


def test_issue_request_maps_to_the_use_case_input() -> None:
    request = LicenseIssueRequest(
        start_date="2026-01-31", term_amount=1, term_unit="month", tech_owner="이기술"
    )

    data = request.to_input()

    assert data.start == date(2026, 1, 31)
    assert data.term == LicenseTerm(amount=1, unit=TermUnit.MONTH)
    assert data.fields.tech_owner == "이기술"
    assert data.fields.inspection is InspectionCycle.NONE


@pytest.mark.parametrize("amount", [0, 100, -1])
def test_issue_request_rejects_a_term_amount_outside_one_to_ninety_nine(amount: int) -> None:
    with pytest.raises(ValidationError):
        LicenseIssueRequest(start_date="2026-01-01", term_amount=amount, term_unit="year")


@pytest.mark.parametrize("amount", [1, 99])
def test_issue_request_accepts_the_boundary_amounts(amount: int) -> None:
    request = LicenseIssueRequest(start_date="2026-01-01", term_amount=amount, term_unit="year")

    assert request.term_amount == amount


@pytest.mark.parametrize("missing", ["start_date", "term_amount", "term_unit"])
def test_issue_request_requires_the_period(missing: str) -> None:
    body = {"start_date": "2026-01-01", "term_amount": 1, "term_unit": "year"}
    body.pop(missing)

    with pytest.raises(ValidationError):
        LicenseIssueRequest(**body)


def test_issue_request_rejects_a_fractional_or_string_amount() -> None:
    with pytest.raises(ValidationError):
        LicenseIssueRequest(start_date="2026-01-01", term_amount=1.5, term_unit="year")
    with pytest.raises(ValidationError):
        LicenseIssueRequest(start_date="2026-01-01", term_amount="1", term_unit="year")


def test_issue_request_rejects_an_end_date_field() -> None:
    body: dict[str, object] = {
        "start_date": "2026-01-01",
        "term_amount": 1,
        "term_unit": "year",
        "end_date": "2026-12-31",
    }

    with pytest.raises(ValidationError):
        LicenseIssueRequest(**body)


def test_deal_patch_request_accepts_the_delete_flag_and_it_is_not_a_form_field() -> None:
    request = DealPatchRequest(status_key="poc_completed", delete_license_contracts=True)

    data = request.to_input()

    assert isinstance(data, DealPatchInput)
    assert data.delete_license_contracts is True
    assert data.provided == frozenset({"status_key"})  # 폼 필드가 아니므로 provided에 없다


def test_deal_patch_request_delete_flag_defaults_to_false() -> None:
    data = DealPatchRequest(name="이름").to_input()

    assert data.delete_license_contracts is False


def test_deal_change_request_accepts_the_delete_flag() -> None:
    request = DealChangeRequest(
        change={"field": "forecast_key", "value": "commit"}, delete_license_contracts=True
    )

    data = request.to_input()

    assert isinstance(data, DealChangeInput)
    assert data.delete_license_contracts is True


def test_deal_change_request_delete_flag_defaults_to_false() -> None:
    data = DealChangeRequest(change={"field": "forecast_key", "value": "commit"}).to_input()

    assert data.delete_license_contracts is False


def test_deal_action_request_accepts_the_delete_flag() -> None:
    request = DealActionCreateRequest(**ACTION, delete_license_contracts=True)

    data = request.to_input()

    assert isinstance(data, DealActionInput)
    assert data.delete_license_contracts is True


def test_deal_action_request_delete_flag_defaults_to_false() -> None:
    assert DealActionCreateRequest(**ACTION).to_input().delete_license_contracts is False


@pytest.mark.parametrize("value", ["true", 1, "yes", None])
def test_the_delete_flag_must_be_a_real_boolean(value: object) -> None:
    with pytest.raises(ValidationError):
        DealChangeRequest(
            change={"field": "forecast_key", "value": "commit"}, delete_license_contracts=value
        )
