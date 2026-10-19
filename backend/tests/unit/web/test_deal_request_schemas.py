"""Deal 등록·수정 요청 스키마(계획 7장): 보낸 필드 판단, 범위 검증은 도메인 몫, 모르는 필드 거부."""

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.bant.values import BantCategory
from app.domain.deal.values import PocState, QuoteSubmitted
from app.web.schemas.deal import ContactDraftRequest, DealCreateRequest, DealPatchRequest
from tests.support.user_ids import OWNER_ID

CUSTOMER = {"company": "네오인", "name": "김철수"}


def _create(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "name": "ERP 구축",
        "owner_user_id": str(OWNER_ID),
        "status_key": "prospecting",
        "forecast_key": "pipeline",
        "revenue_amount": 150_000_000,
        "revenue_date": "2026-06-30",
        "customer": CUSTOMER,
    }
    return {**values, **overrides}


def test_a_minimal_create_body_gets_the_documented_defaults() -> None:
    request = DealCreateRequest(**_create())

    assert (request.vendor_id, request.solution_id, request.procurement) == (None, None, "")
    assert request.users is None
    assert request.partner is None
    assert request.customer.contact_id is None


def test_the_create_body_maps_to_the_use_case_input() -> None:
    partner_id, vendor_id, solution_id = uuid4(), uuid4(), uuid4()
    request = DealCreateRequest(
        **_create(
            vendor_id=str(vendor_id),
            solution_id=str(solution_id),
            users=250,
            partner={"contact_id": str(partner_id), "company": "코어테크", "name": "민지훈"},
            quote={"submitted": "YES", "submitted_date": "2026-10-01"},
            poc={"state": "ING", "completed_date": "2026-11-01"},
            procurement="조달청",
            bant={"budget": str(uuid4()), "need": None},
        )
    )

    data = request.to_input()

    assert (data.name, data.owner_user_id, data.vendor_id, data.solution_id) == (
        "ERP 구축",
        OWNER_ID,
        vendor_id,
        solution_id,
    )
    assert (data.users, data.revenue_amount, data.revenue_date) == (
        250,
        150_000_000,
        date(2026, 6, 30),
    )
    assert (data.status_key, data.forecast_key) == ("prospecting", "pipeline")
    assert data.customer.company == "네오인"
    assert data.partner is not None
    assert data.partner.contact_id == partner_id
    assert (data.quote_submitted, data.quote_submitted_date) == (
        QuoteSubmitted.YES,
        date(2026, 10, 1),
    )
    assert (data.poc_state, data.poc_completed_date) == (PocState.ING, date(2026, 11, 1))
    assert data.procurement == "조달청"
    assert data.bant[BantCategory.BUDGET] is not None
    assert data.bant.get(BantCategory.NEED) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"revenue_amount": 0},  # 범위는 도메인 문구가 나가도록 스키마에 두지 않는다
        {"revenue_amount": -5},
        {"users": 0},
        {"name": ""},
        {"revenue_date": None},
        {"procurement": "가" * 5000},
    ],
)
def test_range_and_length_rules_are_left_to_the_domain(overrides: dict[str, object]) -> None:
    DealCreateRequest(**_create(**overrides))  # 스키마는 형식만 본다


@pytest.mark.parametrize(
    "overrides",
    [
        {"revenue_amount": "많이"},
        {"revenue_amount": 1.5},
        {"revenue_date": "30/06/2026"},
        {"owner_user_id": "not-a-uuid"},
        {"quote": {"submitted": "MAYBE"}},
        {"poc": {"state": "DONE"}},
        {"unexpected": 1},
        {"registered_by": str(OWNER_ID)},
        {"vendor_id": "SAP"},  # 이름이 아니라 UUID여야 한다
        {"solution_id": "not-a-uuid"},
        {"vendor": "SAP"},  # 구 필드(문자열)는 모르는 필드다
        {"solution": "S/4HANA"},
    ],
)
def test_wrong_types_unknown_values_and_unknown_fields_are_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        DealCreateRequest(**_create(**overrides))


@pytest.mark.parametrize(
    "missing", ["name", "owner_user_id", "status_key", "forecast_key", "customer"]
)
def test_required_fields_cannot_be_omitted(missing: str) -> None:
    body = _create()
    del body[missing]

    with pytest.raises(ValidationError):
        DealCreateRequest(**body)


def test_a_contact_draft_requires_company_and_name_keys_but_not_their_content() -> None:
    ContactDraftRequest(company="", name="")  # 빈 값 문구는 유스케이스가 낸다
    with pytest.raises(ValidationError):
        ContactDraftRequest(company="네오인")  # type: ignore[call-arg]


def test_create_accepts_vendor_id_and_solution_id_as_null() -> None:
    request = DealCreateRequest(**_create(vendor_id=None, solution_id=None))

    data = request.to_input()

    assert (data.vendor_id, data.solution_id) == (None, None)


class TestPatchRequest:
    def test_patch_null_solution_id_is_sent(self) -> None:
        vendor_id = uuid4()

        data = DealPatchRequest(vendor_id=vendor_id, solution_id=None).to_input()

        assert data.provided == frozenset({"vendor_id", "solution_id"})
        assert (data.vendor_id, data.solution_id) == (vendor_id, None)

    def test_patch_without_vendor_fields_does_not_provide_them(self) -> None:
        data = DealPatchRequest(name="B").to_input()

        assert not {"vendor_id", "solution_id"} & data.provided

    def test_patch_rejects_the_old_text_fields(self) -> None:
        with pytest.raises(ValidationError):
            DealPatchRequest(vendor="SAP")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            DealPatchRequest(solution="S/4HANA")  # type: ignore[call-arg]

    def test_patch_rejects_a_non_uuid_vendor_id(self) -> None:
        with pytest.raises(ValidationError):
            DealPatchRequest(vendor_id="SAP")

    def test_only_the_sent_fields_are_provided(self) -> None:
        request = DealPatchRequest(name="B", users=None)

        data = request.to_input()

        assert data.provided == frozenset({"name", "users"})
        assert data.name == "B"
        assert data.users is None

    def test_an_empty_body_provides_nothing(self) -> None:
        assert DealPatchRequest().to_input().provided == frozenset()

    def test_partner_null_is_provided_and_a_missing_partner_is_not(self) -> None:
        sent_null = DealPatchRequest(partner=None).to_input()
        omitted = DealPatchRequest(name="B").to_input()

        assert "partner" in sent_null.provided
        assert sent_null.partner is None
        assert "partner" not in omitted.provided

    def test_a_partner_draft_is_converted(self) -> None:
        data = DealPatchRequest(partner={"company": "코어테크", "name": "민지훈"}).to_input()

        assert data.partner is not None
        assert data.partner.company == "코어테크"

    def test_unknown_fields_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DealPatchRequest(code="20261016-A001")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            DealPatchRequest(registered_by="x")  # type: ignore[call-arg]

    def test_wrong_types_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DealPatchRequest(revenue_amount="많이")
