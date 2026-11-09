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
    """계약 칸 요청의 생략값은 빈 기술담당·점검 없음·빈 Note다.

    테스트 코드: LC-032
    """
    # when: 아무 값도 주지 않고 요청 모델을 만든다
    request = LicenseContractFieldsRequest()

    # then: 기술담당 '', 점검주기 none, Note ''
    assert (request.tech_owner, request.inspection_cycle, request.note) == ("", "none", "")


def test_fields_request_maps_to_the_domain_fields() -> None:
    """계약 칸 요청은 앞뒤 공백을 지운 도메인 값으로 바뀐다.

    테스트 코드: LC-031
    """
    # when: 공백이 붙은 값으로 도메인 값으로 변환한다
    request = LicenseContractFieldsRequest(
        tech_owner=" 이기술 ", inspection_cycle="yearly", note="메모"
    )

    # then: 공백이 지워진 ContractFields다
    assert request.to_fields() == ContractFields(
        tech_owner="이기술", inspection=InspectionCycle.YEARLY, note="메모"
    )


@pytest.mark.parametrize("field", ["customer", "vendor", "product", "partner", "sales_owner"])
def test_fields_request_rejects_the_deal_owned_columns(field: str) -> None:
    """Deal 값 칸은 요청 모델이 거절한다.

    테스트 코드: LC-033
    """
    # when: customer·vendor·product·partner·sales_owner를 넣어 만든다
    with pytest.raises(ValidationError):
        LicenseContractFieldsRequest(**{field: "x"})
    # then: ValidationError


def test_fields_request_rejects_a_tech_owner_over_100_chars() -> None:
    """기술담당 101자는 요청 모델이 거절한다.

    테스트 코드: LC-034
    """
    # when: 101자로 만든다
    with pytest.raises(ValidationError):
        LicenseContractFieldsRequest(tech_owner="가" * 101)
    # then: ValidationError


def test_fields_request_accepts_a_tech_owner_of_100_chars() -> None:
    """기술담당 100자는 허용된다.

    테스트 코드: LC-034
    """
    # when: 100자로 만든다
    # then: 길이 100이 그대로다
    assert len(LicenseContractFieldsRequest(tech_owner="가" * 100).tech_owner) == 100


def test_issue_request_maps_to_the_use_case_input() -> None:
    """발급 요청은 유스케이스 입력(시작일·기간·칸)으로 바뀐다."""
    request = LicenseIssueRequest(
        start_date="2026-01-31", term_amount=1, term_unit="month", tech_owner="이기술"
    )

    # when: 요청 모델을 입력으로 변환한다
    data = request.to_input()

    # then: 시작일, 기간, 기술담당, 점검주기 기본값이 담긴다
    assert data.start == date(2026, 1, 31)
    assert data.term == LicenseTerm(amount=1, unit=TermUnit.MONTH)
    assert data.fields.tech_owner == "이기술"
    assert data.fields.inspection is InspectionCycle.NONE


@pytest.mark.parametrize("amount", [0, 100, -1])
def test_issue_request_rejects_a_term_amount_outside_one_to_ninety_nine(amount: int) -> None:
    """기간 수량이 1~99 밖이면 거절된다.

    테스트 코드: LC-044
    """
    # when: 0·100·-1로 만든다
    with pytest.raises(ValidationError):
        LicenseIssueRequest(start_date="2026-01-01", term_amount=amount, term_unit="year")
    # then: ValidationError


@pytest.mark.parametrize("amount", [1, 99])
def test_issue_request_accepts_the_boundary_amounts(amount: int) -> None:
    """기간 수량 1과 99는 허용된다.

    테스트 코드: LC-044
    """
    # when: 경계 수량으로 만든다
    request = LicenseIssueRequest(start_date="2026-01-01", term_amount=amount, term_unit="year")

    # then: 수량이 그대로다
    assert request.term_amount == amount


@pytest.mark.parametrize("missing", ["start_date", "term_amount", "term_unit"])
def test_issue_request_requires_the_period(missing: str) -> None:
    """시작일·수량·단위는 필수다.

    테스트 코드: LC-044
    """
    # given: 필드 하나를 뺀 본문
    body = {"start_date": "2026-01-01", "term_amount": 1, "term_unit": "year"}
    body.pop(missing)

    # when: 요청 모델을 만든다
    with pytest.raises(ValidationError):
        LicenseIssueRequest(**body)
    # then: ValidationError


def test_issue_request_rejects_a_fractional_or_string_amount() -> None:
    """수량이 소수나 문자열이면 거절된다.

    테스트 코드: LC-044
    """
    # when: 1.5와 "1"로 만든다
    with pytest.raises(ValidationError):
        LicenseIssueRequest(start_date="2026-01-01", term_amount=1.5, term_unit="year")
    with pytest.raises(ValidationError):
        LicenseIssueRequest(start_date="2026-01-01", term_amount="1", term_unit="year")
    # then: 둘 다 ValidationError


def test_issue_request_rejects_an_end_date_field() -> None:
    """종료일 필드는 받지 않는다.

    테스트 코드: LC-044
    """
    # given: end_date가 든 본문
    body: dict[str, object] = {
        "start_date": "2026-01-01",
        "term_amount": 1,
        "term_unit": "year",
        "end_date": "2026-12-31",
    }

    # when: 요청 모델을 만든다
    with pytest.raises(ValidationError):
        LicenseIssueRequest(**body)
    # then: ValidationError


def test_deal_patch_request_accepts_the_delete_flag_and_it_is_not_a_form_field() -> None:
    """Deal 폼 수정 요청은 삭제 값을 받고 폼 필드로 세지 않는다."""
    request = DealPatchRequest(status_key="poc_completed", delete_license_contracts=True)

    # when: delete_license_contracts=true로 입력으로 변환한다
    data = request.to_input()

    # then: 플래그가 true이고 provided에는 폼 필드만 있다
    assert isinstance(data, DealPatchInput)
    assert data.delete_license_contracts is True
    assert data.provided == frozenset({"status_key"})  # 폼 필드가 아니므로 provided에 없다


def test_deal_patch_request_delete_flag_defaults_to_false() -> None:
    """삭제 값을 생략한 폼 수정은 false다.

    테스트 코드: LC-007
    """
    # when: 삭제 값 없이 변환한다
    data = DealPatchRequest(name="이름").to_input()

    # then: false다
    assert data.delete_license_contracts is False


def test_deal_change_request_accepts_the_delete_flag() -> None:
    """인라인 변경 요청은 삭제 값을 받는다."""
    request = DealChangeRequest(
        change={"field": "forecast_key", "value": "commit"}, delete_license_contracts=True
    )

    # when: delete_license_contracts=true로 변환한다
    data = request.to_input()

    # then: 플래그가 true다
    assert isinstance(data, DealChangeInput)
    assert data.delete_license_contracts is True


def test_deal_change_request_delete_flag_defaults_to_false() -> None:
    """삭제 값을 생략한 인라인 변경은 false다.

    테스트 코드: LC-007
    """
    # when: 삭제 값 없이 변환한다
    data = DealChangeRequest(change={"field": "forecast_key", "value": "commit"}).to_input()

    # then: false다
    assert data.delete_license_contracts is False


def test_deal_action_request_accepts_the_delete_flag() -> None:
    """Action 등록 요청은 삭제 값을 받는다."""
    request = DealActionCreateRequest(**ACTION, delete_license_contracts=True)

    # when: delete_license_contracts=true로 변환한다
    data = request.to_input()

    # then: 플래그가 true다
    assert isinstance(data, DealActionInput)
    assert data.delete_license_contracts is True


def test_deal_action_request_delete_flag_defaults_to_false() -> None:
    """삭제 값을 생략한 Action 등록은 false다.

    테스트 코드: LC-007
    """
    # when: 삭제 값 없이 변환한다
    # then: false다
    assert DealActionCreateRequest(**ACTION).to_input().delete_license_contracts is False


@pytest.mark.parametrize("value", ["true", 1, "yes", None])
def test_the_delete_flag_must_be_a_real_boolean(value: object) -> None:
    """삭제 값은 진짜 불리언이어야 한다."""
    # when: "true"·1·"yes"·null로 만든다
    with pytest.raises(ValidationError):
        DealChangeRequest(
            change={"field": "forecast_key", "value": "commit"}, delete_license_contracts=value
        )
    # then: ValidationError
