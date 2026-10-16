"""Feature: admin은 고객·파트너 연락처를 등록하고, 잘못된 입력은 저장되지 않는다.

회사명·담당자명·이메일·전화에 공백 문자가 하나라도 있으면 strip하지 않고 422(공백은 입력할 수
없습니다.)이다. 직급은 앞뒤 공백만 제거하고 빈 값은 null이다. 이메일 빈 문자열("")은 null로 본다
(AC-19). 구 `/customers`·`/partners` 등록 시나리오(test_customers_api, test_partners_api,
test_nul_input_api)를 옮겼다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.contacts import (
    COMPANY_REQUIRED_MESSAGE,
    EMAIL_MESSAGE,
    NAME_REQUIRED_MESSAGE,
    PHONE_MESSAGE,
    WHITESPACE_MESSAGE,
    contact_payload,
    payload_with_extra,
    payload_with_kind,
    payload_without,
    then_contact_has_the_documented_fields,
    then_contact_is_listed,
    then_contact_values_are,
    then_detail_is,
    then_location_points_to_the_created,
    then_total_contacts_are,
    when_create_contact,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

DB_ERROR_TOKENS = ("asyncpg", "dbapierror", "sqlalchemy", "postgres", "0x00")
WHITESPACE_VALUES = ["x y", " x", "x ", "x\ty", "x\ny", "x　y", "　x"]


@pytest.mark.parametrize("kind", ["customer", "partner"])
async def test_admin_registers_a_contact_of_each_kind(api: Api, kind: str) -> None:
    """Scenario: admin이 연락처를 등록하면 201과 Location이 오고 목록에 나타난다."""
    # Given
    await given_logged_in_as(api, role="admin")
    payload = contact_payload(kind)
    # When
    response = await when_create_contact(api, payload)
    # Then
    then_status_is(response, 201)
    then_contact_has_the_documented_fields(response)
    then_location_points_to_the_created(response)
    then_contact_values_are(response, kind=kind, title=payload["title"], phone=payload["phone"])
    assert response.json()["updated_at"] == response.json()["created_at"]
    await then_contact_is_listed(api, response.json()["id"], company=payload["company"])


async def test_registration_with_only_required_fields_leaves_optional_ones_empty(api: Api) -> None:
    """Scenario: kind·회사명·담당자명만 보내면 직급·이메일·전화는 null로 저장된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(
        api, {"kind": "customer", "company": "회사", "name": "담당"}
    )
    # Then
    then_status_is(response, 201)
    then_contact_values_are(response, title=None, email=None, phone=None)


async def test_registration_lowercases_the_email(api: Api) -> None:
    """Scenario: 이메일은 소문자로 정규화되어 저장된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, contact_payload(email="Kim@Neoine.Example"))
    # Then
    then_status_is(response, 201)
    then_contact_values_are(response, email="kim@neoine.example")


@pytest.mark.parametrize(
    ("raw", "stored"),
    [("  팀장  ", "팀장"), ("수석 과장", "수석 과장"), ("   ", None), ("", None), (None, None)],
)
async def test_registration_trims_the_title_and_turns_a_blank_title_into_null(
    api: Api, raw: str | None, stored: str | None
) -> None:
    """Scenario: 직급은 앞뒤 공백만 제거하고 내부 공백은 그대로 두며 빈 값은 null이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, contact_payload(title=raw))
    # Then
    then_status_is(response, 201)
    then_contact_values_are(response, title=stored)


async def test_registration_treats_an_empty_email_and_phone_as_missing(api: Api) -> None:
    """Scenario: 이메일·전화가 빈 문자열이면 null로 저장되고 오류가 아니다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, contact_payload(email="", phone=""))
    # Then
    then_status_is(response, 201)
    then_contact_values_are(response, email=None, phone=None)


@pytest.mark.parametrize("field", ["company", "name", "email", "phone"])
@pytest.mark.parametrize("value", WHITESPACE_VALUES)
async def test_registration_rejects_any_whitespace_instead_of_stripping_it(
    api: Api, field: str, value: str
) -> None:
    """Scenario: 회사명·담당자명·이메일·전화에 공백 문자가 있으면 422이고 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, contact_payload(**{field: value}))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, WHITESPACE_MESSAGE)
    await then_total_contacts_are(api, 0)


@pytest.mark.parametrize(
    ("field", "message"),
    [("company", COMPANY_REQUIRED_MESSAGE), ("name", NAME_REQUIRED_MESSAGE)],
)
async def test_registration_requires_company_and_name(api: Api, field: str, message: str) -> None:
    """Scenario: 회사명·담당자명이 비어 있으면 422와 각각의 안내 문구이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, contact_payload(**{field: ""}))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, message)
    await then_total_contacts_are(api, 0)


@pytest.mark.parametrize(
    "email", ["not-an-email", "a@b", "@neoine.example", "kim@", "kim@@neoine.example"]
)
async def test_registration_rejects_a_malformed_email(api: Api, email: str) -> None:
    """Scenario: 이메일 형식이 틀리면 422 '이메일 형식이 올바르지 않습니다.'이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, contact_payload(email=email))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, EMAIL_MESSAGE)
    await then_total_contacts_are(api, 0)


@pytest.mark.parametrize("phone", ["abc", "12-34", "1234567890123456", "010-1234-567x"])
async def test_registration_rejects_a_malformed_phone(api: Api, phone: str) -> None:
    """Scenario: 전화 형식이 틀리면(문자 포함, 7~15자리 밖) 422이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, contact_payload(phone=phone))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert PHONE_MESSAGE in response.json()["detail"]
    await then_total_contacts_are(api, 0)


@pytest.mark.parametrize("field", ["company", "name", "title", "email", "phone"])
async def test_registration_with_a_nul_character_is_422_not_a_server_error(
    api: Api, field: str
) -> None:
    """Scenario: NUL 문자가 든 입력은 500이 아니라 422 invalid-value이고 DB 오류를 숨긴다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, contact_payload(**{field: "a\x00b"}))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    detail = str(response.json().get("detail", "")).lower()
    assert not any(token in detail for token in DB_ERROR_TOKENS), detail
    await then_total_contacts_are(api, 0)


async def test_registration_accepts_values_at_the_length_limits(api: Api) -> None:
    """Scenario: 회사명 200자·담당자명 100자·직급 100자는 등록된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(
        api, contact_payload(company="a" * 200, name="b" * 100, title="c" * 100)
    )
    # Then
    then_status_is(response, 201)


@pytest.mark.parametrize(("field", "length"), [("company", 201), ("name", 101), ("title", 101)])
async def test_registration_rejects_values_over_the_length_limits(
    api: Api, field: str, length: int
) -> None:
    """Scenario: 회사명 201자·담당자명 101자·직급 101자는 422이고 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, contact_payload(**{field: "a" * length}))
    # Then
    then_status_is(response, 422)
    await then_total_contacts_are(api, 0)


@pytest.mark.parametrize("missing", ["kind", "company", "name"])
async def test_registration_without_a_required_field_is_a_request_validation_error(
    api: Api, missing: str
) -> None:
    """Scenario: kind·회사명·담당자명 중 하나가 빠지면 422 request-validation이고 위치가 담긴다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, payload_without(missing))
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    assert any(error["loc"][-1] == missing for error in response.json()["errors"])


async def test_registration_with_an_unknown_kind_is_a_request_validation_error(api: Api) -> None:
    """Scenario: kind가 customer·partner가 아니면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, payload_with_kind("supplier"))
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize("field", ["company_name", "contact_name", "employee_count", "notes", "x"])
async def test_registration_rejects_unknown_and_retired_fields(api: Api, field: str) -> None:
    """Scenario: 모르는 필드와 구 고객 API의 필드(company_name, employee_count 등)는 422이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_contact(api, payload_with_extra(field))
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_total_contacts_are(api, 0)
