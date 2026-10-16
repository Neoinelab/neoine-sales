"""Feature: 로그인한 모든 역할은 회사 목록과 회사별 담당자 목록을 조회한다.

`GET /contacts/companies?kind=`는 대소문자만 다른 표기를 먼저 등록된 하나로 묶은 회사명 목록,
`GET /contacts/by-company?kind=&company=`는 그 회사(대소문자 무시)의 담당자 목록(이름순, deal_count
포함)이다(AC-18). Deal 화면의 연락처 선택이 쓰는 조회다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.contacts import (
    contact_payload,
    given_contact,
    given_contacts,
    then_companies_are,
    then_contact_names_are,
    then_every_row_has_the_documented_fields,
    then_row_deal_counts_are,
    when_list_companies,
    when_list_contacts_of_company,
)
from tests.functional.steps.deals import given_deal_of_contacts

if TYPE_CHECKING:
    from tests.functional.conftest import Api
    from tests.functional.steps.auth import RoleName

pytestmark = pytest.mark.integration
ROLES = ["admin", "sales", "user"]


@pytest.mark.parametrize("role", ROLES)
async def test_every_role_lists_the_companies_of_a_kind(api: Api, role: RoleName) -> None:
    """Scenario: admin·sales·user 누구나 구분별 회사 목록을 받는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contacts(
        api,
        contact_payload("customer", company="Beta", name="일", email=None),
        contact_payload("customer", company="alpha", name="이", email=None),
        contact_payload("partner", company="partner-co", name="삼", email=None),
    )
    await given_logged_in_as(api, role=role)
    # When
    response = await when_list_companies(api, kind="customer")
    # Then
    then_status_is(response, 200)
    then_companies_are(response, ["alpha", "Beta"])


async def test_companies_differing_only_in_case_collapse_to_the_first_registered_spelling(
    api: Api,
) -> None:
    """Scenario: 대소문자만 다른 회사명은 하나로 보고 먼저 등록된 표기를 쓴다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contacts(
        api,
        contact_payload(company="Acme", name="김철수", email=None),
        contact_payload(company="ACME", name="박영희", email=None),
        contact_payload(company="acme", name="최민수", email=None),
    )
    # When
    response = await when_list_companies(api, kind="customer")
    # Then
    then_companies_are(response, ["Acme"])


async def test_companies_of_the_other_kind_are_listed_separately(api: Api) -> None:
    """Scenario: kind=partner면 파트너 회사만 나온다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, "customer", company="customer-co")
    await given_contact(api, "partner", company="partner-co")
    # When
    response = await when_list_companies(api, kind="partner")
    # Then
    then_companies_are(response, ["partner-co"])


async def test_companies_of_an_empty_system_is_an_empty_list(api: Api) -> None:
    """Scenario: 연락처가 없으면 빈 배열이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_companies(api, kind="customer")
    # Then
    then_companies_are(response, [])


@pytest.mark.parametrize("params", [{}, {"kind": "supplier"}], ids=["missing-kind", "unknown-kind"])
async def test_companies_require_a_valid_kind(api: Api, params: dict[str, str]) -> None:
    """Scenario: kind가 없거나 모르는 값이면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_companies(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize("role", ROLES)
async def test_every_role_lists_the_people_of_a_company_sorted_by_name(
    api: Api, role: RoleName
) -> None:
    """Scenario: 회사(대소문자 무시)의 담당자 목록은 이름순이고 항목에 deal_count가 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contacts(
        api,
        contact_payload(company="Acme", name="park", email=None),
        contact_payload(company="ACME", name="kim", email=None),
        contact_payload(company="Other", name="aaa", email=None),
    )
    await given_logged_in_as(api, role=role)
    # When
    response = await when_list_contacts_of_company(api, kind="customer", company="aCmE")
    # Then
    then_status_is(response, 200)
    then_contact_names_are(response, ["kim", "park"])
    then_every_row_has_the_documented_fields(response)


async def test_people_of_a_company_carry_their_deal_counts(api: Api) -> None:
    """Scenario: 담당자별 deal_count는 그 사람을 참조하는 Deal 수이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    busy = await given_contact(api, company="Acme", name="busy", email=None)
    idle = await given_contact(api, company="Acme", name="idle", email=None)
    await given_deal_of_contacts(api, customer_id=busy["id"])
    await given_deal_of_contacts(api, customer_id=busy["id"])
    # When
    response = await when_list_contacts_of_company(api, kind="customer", company="Acme")
    # Then
    then_row_deal_counts_are(response, {busy["id"]: 2, idle["id"]: 0})


async def test_the_people_of_a_company_are_scoped_to_the_kind(api: Api) -> None:
    """Scenario: 같은 회사명이라도 요청한 구분의 담당자만 나온다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, "customer", company="Acme", name="고객담당", email=None)
    await given_contact(api, "partner", company="Acme", name="파트너담당", email=None)
    # When
    response = await when_list_contacts_of_company(api, kind="partner", company="Acme")
    # Then
    then_contact_names_are(response, ["파트너담당"])


async def test_an_unknown_company_has_no_people(api: Api) -> None:
    """Scenario: 없는 회사는 빈 배열이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_contacts_of_company(api, kind="customer", company="없는회사")
    # Then
    then_status_is(response, 200)
    assert response.json() == []


@pytest.mark.parametrize(
    "params",
    [{"kind": "customer"}, {"company": "Acme"}, {"kind": "customer", "company": "a" * 201}],
    ids=["missing-company", "missing-kind", "company-too-long"],
)
async def test_people_of_a_company_require_valid_parameters(
    api: Api, params: dict[str, str]
) -> None:
    """Scenario: kind·company가 빠지거나 회사명이 200자를 넘으면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_contacts_of_company(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_the_lookup_item_shape_matches_the_admin_list_item(api: Api) -> None:
    """Scenario: 회사별 담당자 항목은 admin 목록 항목과 같은 필드를 가진다."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_contact(api)
    # When
    response = await when_list_contacts_of_company(api, kind="customer", company=created["company"])
    # Then
    then_row_deal_counts_are(response, {created["id"]: 0})
    then_every_row_has_the_documented_fields(response)
