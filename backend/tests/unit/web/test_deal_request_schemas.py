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
        "vendor_id": 7,
        "solution": "ITDR",
        "users": 10,
        "status_key": "prospecting",
        "forecast_key": "pipeline",
        "revenue_amount": 150_000_000,
        "revenue_date": "2026-06-30",
        "customer": CUSTOMER,
    }
    return {**values, **overrides}


def test_a_minimal_create_body_gets_the_documented_defaults() -> None:
    """필수 키만 있는 등록 본문은 문서화된 기본값을 갖는다."""
    # when: 필수 키만으로 DealCreateRequest를 만든다.
    request = DealCreateRequest(**_create())

    # then: vendor_id 7, procurement '', partner None, 고객 contact_id None이다.
    assert (request.vendor_id, request.solution, request.procurement) == (7, "ITDR", "")
    assert request.users == 10
    assert request.partner is None
    assert request.customer.contact_id is None


def test_create_request_without_users_is_a_validation_error() -> None:
    """users 키가 없는 등록 본문은 형식 오류다.

    테스트 코드: DE-010
    """
    # when: users 키를 뺀 본문으로 만든다.
    body = _create()
    del body["users"]

    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**body)

    # then: users의 missing 오류 하나다.
    assert [(e["type"], e["loc"]) for e in caught.value.errors()] == [("missing", ("users",))]


def test_create_request_with_null_users_is_a_validation_error() -> None:
    """users가 null인 등록 본문은 형식 오류다.

    테스트 코드: DE-010
    """
    # when: users를 null로 만든다.
    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**_create(users=None))

    # then: users 위치의 오류다.
    assert [e["loc"] for e in caught.value.errors()] == [("users",)]


@pytest.mark.parametrize("users", ["10", 1.5, True])
def test_create_request_with_a_non_integer_users_is_a_validation_error(users: object) -> None:
    """users가 문자열·실수·불리언이면 형식 오류다.

    테스트 코드: DE-010
    """
    # when·then: users에 '10'·1.5·True를 넣어 만든다 → ValidationError다.
    with pytest.raises(ValidationError):
        DealCreateRequest(**_create(users=users))


def test_the_create_body_maps_to_the_use_case_input() -> None:
    """등록 본문은 유스케이스 입력으로 그대로 옮겨진다."""
    # when: 모든 선택 필드가 든 본문을 to_input으로 바꾼다.
    partner_id, vendor_id, budget_id = new_id(), new_id(), new_id()
    request = DealCreateRequest(
        **_create(
            vendor_id=vendor_id,
            solution="ITDR",
            users=250,
            partner={"contact_id": partner_id, "company": "코어테크", "name": "민지훈"},
            quote={"submitted": "YES", "submitted_date": "2026-10-01"},
            poc={"state": "ING", "completed_date": "2026-11-01"},
            procurement="조달청",
            bant={"budget": {"id": budget_id}, "need": None, "timeline": {"name": "분기 내"}},
        )
    )

    data = request.to_input()

    # then: 각 필드와 BANT 선택 객체가 입력에 담긴다.
    assert (data.name, data.owner_user_id, data.vendor_id, data.solution) == (
        "ERP 구축",
        OWNER_ID,
        vendor_id,
        "ITDR",
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
    """범위·길이 규칙은 스키마가 아니라 도메인 문구로 나가도록 스키마는 통과시킨다.

    테스트 코드: DE-008
    """
    # when·then: 금액 0·음수, users 0·음수, 빈 이름, null 날짜, 긴 구매절차로 만든다
    # → 스키마 오류가 없다.
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
        {"solution_id": 1},  # 구 필드(id)는 모르는 필드다
        {"vendor": "SAP"},  # 구 필드(문자열)는 모르는 필드다
        {"solution": 1},  # 문자열이 아닌 값은 거절한다
        {"solution": ["ITDR"]},
        {"solution": {"name": "ITDR"}},
    ],
)
def test_wrong_types_unknown_values_and_unknown_fields_are_rejected(
    overrides: dict[str, object],
) -> None:
    """형식이 틀린 값과 모르는 필드(예전 필드 포함)는 거절한다.

    테스트 코드: DE-010
    """
    # when: 금액 '많이', 날짜 '30/06/2026', 모르는 키, 예전 vendor·solution_id, 구 BANT 형식
    #   등으로 만든다.
    # then: ValidationError다.
    with pytest.raises(ValidationError):
        DealCreateRequest(**_create(**overrides))


@pytest.mark.parametrize(
    "missing", ["name", "owner_user_id", "status_key", "forecast_key", "customer"]
)
def test_required_fields_cannot_be_omitted(missing: str) -> None:
    """필수 키를 빼면 형식 오류다.

    테스트 코드: DE-010
    """
    # when: name·owner_user_id·status_key·forecast_key·customer를 하나씩 뺀다.
    body = _create()
    del body[missing]

    # then: ValidationError다.
    with pytest.raises(ValidationError):
        DealCreateRequest(**body)


def test_a_contact_draft_requires_company_and_name_keys_but_not_their_content() -> None:
    """연락처 입력은 company·name 키가 필수지만 내용이 비어도 스키마는 통과시킨다.

    테스트 코드: DE-010
    """
    ContactDraftRequest(company="", name="")  # 빈 값 문구는 유스케이스가 낸다
    # when·then: 빈 문자열 값, 그리고 name 키 없이 만든다
    # → 빈 값은 통과하고 키 누락만 ValidationError다.
    with pytest.raises(ValidationError):
        ContactDraftRequest(company="네오인")  # type: ignore[call-arg]


def test_bant_accepts_choice_objects_and_null() -> None:
    """BANT는 선택 객체와 null을 받고 빠진 구분은 선택 안 함이다."""
    # when: {id}·{name}·null을 섞어 변환한다.
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

    # then: 입력 BANT에 선택 객체가 담기고 빠진 구분은 None이다.
    assert bant[BantCategory.BUDGET] == CatalogChoice(id=label_id)
    assert bant[BantCategory.AUTHORITY] == CatalogChoice(name="CEO 보고 완료")
    assert bant.get(BantCategory.NEED) is None
    assert bant.get(BantCategory.TIMELINE) is None


def test_bant_plain_id_without_a_choice_object_is_rejected() -> None:
    """객체가 아닌 Label id 값은 형식 오류다.

    테스트 코드: DE-010
    """
    # when·then: bant.budget에 정수를 넣어 만든다 → ValidationError다.
    with pytest.raises(ValidationError):
        DealCreateRequest(**_create(bant={"budget": MISSING_ID}))


def test_bant_category_with_both_id_and_name_is_rejected() -> None:
    """id와 name을 함께 보낸 BANT 구분은 형식 오류다.

    테스트 코드: DE-010
    """
    # when·then: bant.need에 id와 name을 같이 넣어 만든다 → ValidationError다.
    with pytest.raises(ValidationError):
        DealCreateRequest(**_create(bant={"need": {"id": MISSING_ID, "name": "x"}}))


BAD_JSON_IDS = ["5", True, 5.0, 0, -3, 2**53]  # 문자열·불리언·실수·0·음수·2^53-1 초과


@pytest.mark.parametrize("bad", BAD_JSON_IDS)
@pytest.mark.parametrize("field", ["owner_user_id", "vendor_id"])
def test_reference_ids_must_be_json_integers(field: str, bad: object) -> None:
    """Owner·Vendor id는 1~2^53-1의 JSON 정수여야 한다.

    테스트 코드: DE-010
    """
    # when: 문자열·불리언·실수·0·음수·상한 초과 값을 넣어 만든다.
    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**_create(**{field: bad}))

    # then: 해당 필드 위치의 오류다.
    assert [e["loc"] for e in caught.value.errors()] == [(field,)]


@pytest.mark.parametrize("bad", BAD_JSON_IDS)
@pytest.mark.parametrize("where", ["customer", "partner"])
def test_contact_ids_must_be_json_integers(where: str, bad: object) -> None:
    """연락처 입력의 contact_id는 JSON 정수여야 한다.

    테스트 코드: DE-010
    """
    # when: 고객·파트너 contact_id에 잘못된 값을 넣어 만든다.
    draft = {"company": "네오인", "name": "김철수", "contact_id": bad}

    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**_create(**{where: draft}))

    # then: contact_id 위치의 오류다.
    assert [e["loc"] for e in caught.value.errors()] == [(where, "contact_id")]


@pytest.mark.parametrize("bad", BAD_JSON_IDS)
def test_patch_reference_ids_must_be_json_integers(bad: object) -> None:
    """수정 본문의 Vendor·Owner id도 JSON 정수여야 한다.

    테스트 코드: DE-072
    """
    with pytest.raises(ValidationError):
        DealPatchRequest(vendor_id=bad)
    # when·then: 잘못된 id로 DealPatchRequest를 만든다 → ValidationError다.
    with pytest.raises(ValidationError):
        DealPatchRequest(owner_user_id=bad)


def test_the_largest_allowed_reference_id_is_accepted() -> None:
    """허용되는 가장 큰 id(2^53-1)는 받는다."""
    # when: vendor_id 2^53-1로 만든다.
    top = 2**53 - 1

    data = DealCreateRequest(**_create(vendor_id=top)).to_input()

    # then: 입력에 그 값이 담긴다.
    assert data.vendor_id == top


def test_create_request_without_vendor_id_is_a_validation_error() -> None:
    """vendor_id 키가 없는 등록 본문은 형식 오류다.

    테스트 코드: DE-010
    """
    # when: vendor_id 키를 뺀다.
    body = _create()
    del body["vendor_id"]

    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**body)

    # then: vendor_id의 missing 오류 하나다.
    assert [(e["type"], e["loc"]) for e in caught.value.errors()] == [("missing", ("vendor_id",))]


def test_create_request_with_null_vendor_id_is_a_validation_error() -> None:
    """vendor_id가 null인 등록 본문은 형식 오류다(Vendor는 필수).

    테스트 코드: DE-010
    """
    # when: vendor_id를 null로 만든다.
    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**_create(vendor_id=None))

    # then: vendor_id 위치의 오류다.
    assert [e["loc"] for e in caught.value.errors()] == [("vendor_id",)]


def test_create_request_keeps_the_vendor_id_in_the_input() -> None:
    """고른 Vendor id는 등록 입력에 그대로 담긴다.

    테스트 코드: DE-014
    """
    # when: vendor_id 7과 Solution 'ITDR'로 변환한다.
    data = DealCreateRequest(**_create()).to_input()

    # then: 입력에 vendor_id 7과 Solution이 담긴다.
    assert (data.vendor_id, data.solution) == (7, "ITDR")


def test_create_request_accepts_solution_text() -> None:
    """Solution 텍스트를 받는다."""
    # when: solution 'ITDR'로 변환한다.
    data = DealCreateRequest(**_create(solution="ITDR")).to_input()

    # then: 입력 solution이 'ITDR'이다.
    assert data.solution == "ITDR"


def test_create_request_without_solution_gets_an_empty_solution() -> None:
    """solution 키가 없으면 오류 없이 빈 Solution 입력이 된다.

    테스트 코드: DE-115
    """
    # when: solution 키를 빼고 변환한다.
    body = _create()
    del body["solution"]
    data = DealCreateRequest(**body).to_input()

    # then: 입력 solution이 ''다.
    assert data.solution == ""


def test_create_request_with_null_solution_gets_an_empty_solution() -> None:
    """solution이 null이면 오류 없이 빈 Solution 입력이 된다.

    테스트 코드: DE-115
    """
    # when: solution을 null로 만들어 변환한다.
    data = DealCreateRequest(**_create(solution=None)).to_input()

    # then: 입력 solution이 ''다.
    assert data.solution == ""


def test_create_request_keeps_a_blank_solution_for_the_domain_to_judge() -> None:
    """공백뿐인 Solution은 스키마가 바꾸지 않고 도메인이 빈 값으로 정리한다.

    테스트 코드: DE-115
    """
    # when: solution '   '로 변환한다
    solution = DealCreateRequest(**_create(solution="   ")).to_input().solution
    # then: 입력에 '   '가 그대로 담긴다.
    assert solution == "   "


def test_create_request_keeps_a_long_solution_for_the_domain_to_judge() -> None:
    """201자 Solution은 스키마가 자르지 않고 도메인 문구로 판정한다.

    테스트 코드: DE-017
    """
    # when: 201자 Solution으로 변환한다.
    data = DealCreateRequest(**_create(solution="a" * 201)).to_input()

    # then: 입력에 201자가 그대로 담긴다.
    assert data.solution == "a" * 201


def test_create_request_rejects_solution_id_field() -> None:
    """예전 solution_id 필드는 모르는 필드로 거절한다.

    테스트 코드: DE-010
    """
    # when·then: solution_id를 넣어 만든다 → ValidationError다.
    with pytest.raises(ValidationError):
        DealCreateRequest(**_create(solution_id=1))


@pytest.mark.parametrize("bad", [1, 1.5, True, ["a"], {"a": 1}])
def test_create_request_rejects_non_string_solution(bad: object) -> None:
    """문자열이 아닌 Solution은 형식 오류다.

    테스트 코드: DE-010
    """
    # when: 숫자·실수·불리언·목록·객체 Solution으로 만든다.
    with pytest.raises(ValidationError) as caught:
        DealCreateRequest(**_create(solution=bad))

    # then: solution 위치의 오류다.
    assert [e["loc"] for e in caught.value.errors()] == [("solution",)]


class TestPatchRequest:
    def test_patch_null_solution_is_provided(self) -> None:
        """수정에서 solution null은 보낸 필드다.

        테스트 코드: DE-017
        """
        # when: solution=None으로 변환한다.
        data = DealPatchRequest(solution=None).to_input()

        # then: provided에 solution이 있고 값은 None이다.
        assert data.provided == frozenset({"solution"})
        assert data.solution is None

    def test_patch_solution_text_is_provided(self) -> None:
        """수정에서 solution 텍스트는 보낸 필드다."""
        # when: solution='ITDR'로 변환한다.
        data = DealPatchRequest(solution="ITDR").to_input()

        # then: provided가 {solution}이다.
        assert data.provided == frozenset({"solution"})
        assert data.solution == "ITDR"

    def test_patch_vendor_only_does_not_provide_solution(self) -> None:
        """Vendor만 보내면 solution은 보낸 필드가 아니다.

        테스트 코드: DE-049
        """
        # when: vendor_id만 넣어 변환한다.
        vendor_id = new_id()

        data = DealPatchRequest(vendor_id=vendor_id).to_input()

        # then: provided가 {vendor_id}뿐이다.
        assert data.provided == frozenset({"vendor_id"})

    def test_patch_null_vendor_is_provided_and_left_for_the_domain_to_judge(self) -> None:
        """수정에서 vendor_id null은 보낸 필드다(거절은 유스케이스가 "Vendor를 선택하세요."로 한다).

        테스트 코드: DE-116
        """
        # when: vendor_id=None으로 변환한다.
        data = DealPatchRequest(vendor_id=None).to_input()

        # then: provided에 vendor_id가 있고 값은 None이다.
        assert data.provided == frozenset({"vendor_id"})
        assert data.vendor_id is None

    def test_patch_without_vendor_or_solution_does_not_provide_them(self) -> None:
        """이름만 보내면 vendor_id·solution은 보낸 필드가 아니다.

        테스트 코드: DE-053
        """
        # when: name만 넣어 변환한다.
        data = DealPatchRequest(name="B").to_input()

        # then: provided에 vendor_id·solution이 없다.
        assert not {"vendor_id", "solution"} & data.provided

    def test_patch_rejects_the_old_fields(self) -> None:
        """수정 본문의 예전 필드(vendor, solution_id)는 거절한다.

        테스트 코드: DE-072
        """
        with pytest.raises(ValidationError):
            DealPatchRequest(vendor="SAP")  # type: ignore[call-arg]
        # when·then: vendor·solution_id를 넣어 만든다 → ValidationError다.
        with pytest.raises(ValidationError):
            DealPatchRequest(solution_id=1)  # type: ignore[call-arg]

    @pytest.mark.parametrize("bad", [1, 1.5, True, ["a"]])
    def test_patch_rejects_a_non_string_solution(self, bad: object) -> None:
        """수정 본문의 문자열이 아닌 Solution은 형식 오류다.

        테스트 코드: DE-072
        """
        # when·then: 숫자·불리언·목록 solution으로 만든다 → ValidationError다.
        with pytest.raises(ValidationError):
            DealPatchRequest(solution=bad)

    def test_patch_rejects_a_non_integer_vendor_id(self) -> None:
        """수정 본문의 문자열 vendor_id는 형식 오류다.

        테스트 코드: DE-072
        """
        # when·then: vendor_id 'SAP'로 만든다 → ValidationError다.
        with pytest.raises(ValidationError):
            DealPatchRequest(vendor_id="SAP")

    def test_patch_bant_choices_are_provided_as_a_whole(self) -> None:
        """수정에서 bant를 보내면 네 구분 전체를 보낸 것으로 본다.

        테스트 코드: DE-056
        """
        # when: budget·need만 든 bant로 변환한다.
        label_id = new_id()

        data = DealPatchRequest(
            bant={"budget": {"id": label_id}, "need": {"name": "신규"}}
        ).to_input()

        # then: bant가 provided에 있고 빠진 구분은 None이다.
        assert "bant" in data.provided
        assert data.bant is not None
        assert data.bant[BantCategory.BUDGET] == CatalogChoice(id=label_id)
        assert data.bant[BantCategory.NEED] == CatalogChoice(name="신규")
        assert data.bant.get(BantCategory.AUTHORITY) is None

    def test_patch_rejects_the_old_bare_bant_id(self) -> None:
        """수정 본문의 객체가 아닌 Label id는 거절한다.

        테스트 코드: DE-072
        """
        # when·then: bant.budget에 정수를 넣어 만든다 → ValidationError다.
        with pytest.raises(ValidationError):
            DealPatchRequest(bant={"budget": MISSING_ID})

    def test_only_the_sent_fields_are_provided(self) -> None:
        """본문에 키가 있는 필드만 보낸 필드다(null 포함).

        테스트 코드: DE-017
        """
        # when: name='B', users=None으로 변환한다.
        request = DealPatchRequest(name="B", users=None)

        data = request.to_input()

        # then: provided가 {name, users}이고 users는 None이다.
        assert data.provided == frozenset({"name", "users"})
        assert data.name == "B"
        assert data.users is None

    def test_an_empty_body_provides_nothing(self) -> None:
        """빈 본문은 아무것도 보내지 않은 것이다.

        테스트 코드: DE-017
        """
        # when: 빈 DealPatchRequest를 변환한다
        provided = DealPatchRequest().to_input().provided
        # then: provided가 비어 있다.
        assert provided == frozenset()

    def test_partner_null_is_provided_and_a_missing_partner_is_not(self) -> None:
        """partner null은 보낸 필드이고 생략은 보낸 필드가 아니다.

        테스트 코드: DE-064, DE-065
        """
        # when: partner=None과 name만 든 본문을 각각 변환한다.
        sent_null = DealPatchRequest(partner=None).to_input()
        omitted = DealPatchRequest(name="B").to_input()

        # then: 앞의 것만 provided에 partner가 있다.
        assert "partner" in sent_null.provided
        assert sent_null.partner is None
        assert "partner" not in omitted.provided

    def test_a_partner_draft_is_converted(self) -> None:
        """파트너 입력은 연락처 입력으로 변환된다."""
        # when: 회사·이름이 든 partner로 변환한다.
        data = DealPatchRequest(partner={"company": "코어테크", "name": "민지훈"}).to_input()

        # then: 입력 partner의 회사명이 같다.
        assert data.partner is not None
        assert data.partner.company == "코어테크"

    def test_unknown_fields_are_rejected(self) -> None:
        """수정 본문의 모르는 필드(code 등)는 거절한다.

        테스트 코드: DE-072
        """
        with pytest.raises(ValidationError):
            DealPatchRequest(code="20261016-A001")  # type: ignore[call-arg]
        # when·then: code·registered_by를 넣어 만든다 → ValidationError다.
        with pytest.raises(ValidationError):
            DealPatchRequest(registered_by="x")  # type: ignore[call-arg]

    def test_wrong_types_are_rejected(self) -> None:
        """수정 본문의 형식이 틀린 값은 거절한다.

        테스트 코드: DE-072
        """
        # when·then: revenue_amount '많이'로 만든다 → ValidationError다.
        with pytest.raises(ValidationError):
            DealPatchRequest(revenue_amount="많이")


def test_create_schema_documents_vendor_as_required_and_solution_as_optional() -> None:
    """등록 요청 OpenAPI 스키마는 vendor_id를 필수·null 불가로, solution을 선택으로 문서화한다.

    테스트 코드: DE-010
    """
    # when: 등록 요청의 JSON 스키마를 만든다.
    schema = DealCreateRequest.model_json_schema()

    # then: vendor_id는 필수이고 null이 허용되지 않으며 solution은 필수가 아니다.
    assert "vendor_id" in schema["required"]
    assert "solution" not in schema["required"]
    vendor = schema["properties"]["vendor_id"]
    assert "null" not in str(vendor.get("anyOf", vendor.get("type")))
