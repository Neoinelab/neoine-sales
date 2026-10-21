"""Deal 등록·수정 요청 스키마(계획 7장): 보낸 필드 판단, 범위 검증은 도메인 몫, 모르는 필드 거부."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.application.choice import CatalogChoice
from app.domain.bant.values import BantCategory
from app.domain.deal.values import PocState, QuoteSubmitted
from app.web.schemas.deal import ContactDraftRequest, DealCreateRequest, DealPatchRequest
from tests.support.ids import MISSING_ID, new_id
from tests.support.user_ids import OWNER_ID

CUSTOMER = {"company": "네오인", "name": "김철수"}


def _create(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "name": "ERP 구축",
        "owner_user_id": OWNER_ID,
        "users": 10,
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
    assert request.users == 10
    assert request.partner is None
    assert request.customer.contact_id is None


def test_create_request_without_users_is_a_validation_error() -> None:
    body = _create()
    del body["users"]

    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**body)

    assert [(e["type"], e["loc"]) for e in caught.value.errors()] == [("missing", ("users",))]


def test_create_request_with_null_users_is_a_validation_error() -> None:
    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**_create(users=None))

    assert [e["loc"] for e in caught.value.errors()] == [("users",)]


@pytest.mark.parametrize("users", ["10", 1.5, True])
def test_create_request_with_a_non_integer_users_is_a_validation_error(users: object) -> None:
    with pytest.raises(ValidationError):
        DealCreateRequest(**_create(users=users))


def test_the_create_body_maps_to_the_use_case_input() -> None:
    partner_id, vendor_id, solution_id, budget_id = new_id(), new_id(), new_id(), new_id()
    request = DealCreateRequest(
        **_create(
            vendor_id=vendor_id,
            solution_id=solution_id,
            users=250,
            partner={"contact_id": partner_id, "company": "코어테크", "name": "민지훈"},
            quote={"submitted": "YES", "submitted_date": "2026-10-01"},
            poc={"state": "ING", "completed_date": "2026-11-01"},
            procurement="조달청",
            bant={"budget": {"id": budget_id}, "need": None, "timeline": {"name": "분기 내"}},
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
    assert data.bant[BantCategory.BUDGET] == CatalogChoice(id=budget_id)
    assert data.bant.get(BantCategory.NEED) is None
    assert data.bant[BantCategory.TIMELINE] == CatalogChoice(name="분기 내")
    assert data.bant.get(BantCategory.AUTHORITY) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"revenue_amount": 0},  # 범위는 도메인 문구가 나가도록 스키마에 두지 않는다
        {"revenue_amount": -5},
        {"users": 0},
        {"users": -1},  # 음수 범위도 도메인 문구가 나가게 스키마는 통과시킨다
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
        {"owner_user_id": "not-an-id"},
        {"quote": {"submitted": "MAYBE"}},
        {"poc": {"state": "DONE"}},
        {"unexpected": 1},
        {"registered_by": OWNER_ID},
        {"bant": {"budget": MISSING_ID}},  # 구 형식(id 값 그대로)은 선택 객체로 바꿔야 한다
        {"bant": {"budget": {"id": MISSING_ID, "name": "둘 다"}}},
        {"bant": {"budget": {}}},
        {"bant": {"budget": {"id": "not-an-id"}}},
        {"bant": {"budget": "풀 예산 확보"}},
        {"vendor_id": "SAP"},  # 이름이 아니라 정수 id여야 한다
        {"solution_id": "not-an-id"},
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


def test_bant_accepts_choice_objects_and_null() -> None:
    label_id = new_id()
    request = DealCreateRequest(
        **_create(
            bant={
                "budget": {"id": label_id},
                "authority": {"name": "CEO 보고 완료"},
                "need": None,
            }
        )
    )

    bant = request.to_input().bant

    assert bant[BantCategory.BUDGET] == CatalogChoice(id=label_id)
    assert bant[BantCategory.AUTHORITY] == CatalogChoice(name="CEO 보고 완료")
    assert bant.get(BantCategory.NEED) is None
    assert bant.get(BantCategory.TIMELINE) is None


def test_bant_plain_id_without_a_choice_object_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DealCreateRequest(**_create(bant={"budget": MISSING_ID}))


def test_bant_category_with_both_id_and_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DealCreateRequest(**_create(bant={"need": {"id": MISSING_ID, "name": "x"}}))


BAD_JSON_IDS = ["5", True, 5.0, 0, -3, 2**53]  # 문자열·불리언·실수·0·음수·2^53-1 초과


@pytest.mark.parametrize("bad", BAD_JSON_IDS)
@pytest.mark.parametrize("field", ["owner_user_id", "vendor_id", "solution_id"])
def test_reference_ids_must_be_json_integers(field: str, bad: object) -> None:
    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**_create(**{field: bad}))

    assert [e["loc"] for e in caught.value.errors()] == [(field,)]


@pytest.mark.parametrize("bad", BAD_JSON_IDS)
@pytest.mark.parametrize("where", ["customer", "partner"])
def test_contact_ids_must_be_json_integers(where: str, bad: object) -> None:
    draft = {"company": "네오인", "name": "김철수", "contact_id": bad}

    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**_create(**{where: draft}))

    assert [e["loc"] for e in caught.value.errors()] == [(where, "contact_id")]


@pytest.mark.parametrize("bad", BAD_JSON_IDS)
def test_patch_reference_ids_must_be_json_integers(bad: object) -> None:
    with pytest.raises(ValidationError):
        DealPatchRequest(vendor_id=bad)
    with pytest.raises(ValidationError):
        DealPatchRequest(solution_id=bad)
    with pytest.raises(ValidationError):
        DealPatchRequest(owner_user_id=bad)


def test_the_largest_allowed_reference_id_is_accepted() -> None:
    top = 2**53 - 1

    data = DealCreateRequest(**_create(vendor_id=top, solution_id=1)).to_input()

    assert (data.vendor_id, data.solution_id) == (top, 1)


def test_create_accepts_vendor_id_and_solution_id_as_null() -> None:
    request = DealCreateRequest(**_create(vendor_id=None, solution_id=None))

    data = request.to_input()

    assert (data.vendor_id, data.solution_id) == (None, None)


class TestPatchRequest:
    def test_patch_null_solution_id_is_sent(self) -> None:
        vendor_id = new_id()

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

    def test_patch_rejects_a_non_integer_vendor_id(self) -> None:
        with pytest.raises(ValidationError):
            DealPatchRequest(vendor_id="SAP")

    def test_patch_bant_choices_are_provided_as_a_whole(self) -> None:
        label_id = new_id()

        data = DealPatchRequest(
            bant={"budget": {"id": label_id}, "need": {"name": "신규"}}
        ).to_input()

        assert "bant" in data.provided
        assert data.bant is not None
        assert data.bant[BantCategory.BUDGET] == CatalogChoice(id=label_id)
        assert data.bant[BantCategory.NEED] == CatalogChoice(name="신규")
        assert data.bant.get(BantCategory.AUTHORITY) is None

    def test_patch_rejects_the_old_bare_bant_id(self) -> None:
        with pytest.raises(ValidationError):
            DealPatchRequest(bant={"budget": MISSING_ID})

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
