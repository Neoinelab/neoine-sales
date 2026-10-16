"""Feature: admin은 연락처 목록을 구분·키워드로 거르고 페이지로 넘기며 Deal 연결 수를 본다.

응답은 `{items(deal_count 포함), total, offset, limit}`이다. 정렬은 고객 먼저 → 회사명 → 담당자명 →
id이고 키워드는 회사명·담당자명·이메일의 대소문자 무시 부분 일치다(AC-17). 구 고객·파트너 검색
시나리오(test_customer_search_api, test_partner_search_api)를 옮겼다. 직급·전화 검색은 AC-17의
검색 대상이 아니라 옮기지 않았다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.contacts import (
    contact_payload,
    given_contact,
    given_contacts,
    given_people,
    then_deal_counts_are,
    then_every_item_has_the_documented_fields,
    then_item_companies_are,
    then_item_names_are,
    then_page_is,
    when_search_contacts,
)
from tests.functional.steps.deals import given_deal_of_contacts

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_admin_gets_the_page_shape_with_documented_item_fields(api: Api) -> None:
    """Scenario: 목록 응답은 items·total·offset·limit이고 항목에 deal_count가 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api)
    # When
    response = await when_search_contacts(api, limit=10)
    # Then
    then_status_is(response, 200)
    then_page_is(response, total=1, offset=0, limit=10)
    then_every_item_has_the_documented_fields(response)


async def test_an_empty_system_lists_no_contacts(api: Api) -> None:
    """Scenario: 연락처가 없으면 items가 비고 total은 0이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_search_contacts(api)
    # Then
    then_page_is(response, total=0, offset=0, limit=50)
    assert response.json()["items"] == []


async def test_contacts_are_ordered_customers_first_then_company_name_and_id(api: Api) -> None:
    """Scenario: 정렬은 고객 먼저, 회사명(대소문자 무시), 담당자명, id 순이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contacts(
        api,
        contact_payload("partner", company="aaa-partner", name="이영희", email=None),
        contact_payload("customer", company="Beta", name="park", email=None),
        contact_payload("customer", company="alpha", name="zed", email=None),
        contact_payload("customer", company="alpha", name="Amy", email=None),
        contact_payload("partner", company="bbb-partner", name="이영희", email=None),
    )
    # When
    response = await when_search_contacts(api)
    # Then
    then_item_companies_are(response, ["alpha", "alpha", "Beta", "aaa-partner", "bbb-partner"])
    then_item_names_are(response, ["Amy", "zed", "park", "이영희", "이영희"])


async def test_kind_filter_lists_only_that_kind(api: Api) -> None:
    """Scenario: kind=partner면 파트너 연락처만, kind=customer면 고객만 나온다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, "customer", company="customer-co")
    await given_contact(api, "partner", company="partner-co")
    # When
    partners = await when_search_contacts(api, kind="partner")
    customers = await when_search_contacts(api, kind="customer")
    # Then
    then_item_companies_are(partners, ["partner-co"])
    then_item_companies_are(customers, ["customer-co"])
    then_page_is(partners, total=1, offset=0, limit=50)


@pytest.mark.parametrize(
    ("keyword", "expected"),
    [
        ("alpha", ["Alpha상사"]),  # 회사명(대소문자 무시)
        ("알파", ["무관회사"]),  # 담당자명
        ("SEARCH.ME@", ["메일회사"]),  # 이메일(대소문자 무시)
    ],
)
async def test_keyword_matches_company_name_and_email_ignoring_case(
    api: Api, keyword: str, expected: list[str]
) -> None:
    """Scenario: 키워드는 회사명·담당자명·이메일의 부분 일치다(대소문자 무시)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contacts(
        api,
        contact_payload(company="Alpha상사", name="가나다", email="a@x.example"),
        contact_payload(company="무관회사", name="알파담당", email="b@x.example"),
        contact_payload(company="메일회사", name="라마바", email="Search.Me@Sample.Example"),
        contact_payload(company="다른회사", name="사아자", email="c@x.example"),
    )
    # When
    response = await when_search_contacts(api, keyword=keyword)
    # Then
    then_item_companies_are(response, expected)


async def test_keyword_does_not_search_title_or_phone(api: Api) -> None:
    """Scenario: 직급과 전화는 검색 대상이 아니다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, company="직급회사", title="ZETA 팀장", phone="031-777-4321")
    # When
    by_title = await when_search_contacts(api, keyword="zeta")
    by_phone = await when_search_contacts(api, keyword="777-43")
    # Then
    then_page_is(by_title, total=0, offset=0, limit=50)
    then_page_is(by_phone, total=0, offset=0, limit=50)


async def test_a_blank_keyword_applies_no_condition(api: Api) -> None:
    """Scenario: 공백뿐인 키워드는 조건이 없는 것과 같다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contacts(
        api,
        contact_payload(company="가", name="일", email=None),
        contact_payload(company="나", name="이", email=None),
    )
    # When
    response = await when_search_contacts(api, keyword="   ")
    # Then
    then_item_companies_are(response, ["가", "나"])


async def test_percent_in_a_keyword_is_matched_literally(api: Api) -> None:
    """Scenario: 키워드의 %는 와일드카드가 아니라 글자 그대로 찾는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contacts(
        api,
        contact_payload(company="백%프로", name="일", email=None),
        contact_payload(company="백천프로", name="이", email=None),
    )
    # When
    response = await when_search_contacts(api, keyword="백%")
    # Then
    then_item_companies_are(response, ["백%프로"])


async def test_paging_is_applied_after_filtering_and_total_counts_every_match(api: Api) -> None:
    """Scenario: 필터 뒤에 offset·limit이 적용되고 total은 페이지와 무관한 전체 건수다."""
    # Given
    await given_logged_in_as(api, role="admin")
    for number in range(4):
        await given_contact(api, company=f"hit{number}", name="김철수", email=None)
        await given_contact(api, company=f"other{number}", name="김철수", email=None)
    # When
    response = await when_search_contacts(api, keyword="hit", offset=1, limit=2)
    # Then
    then_item_companies_are(response, ["hit1", "hit2"])
    then_page_is(response, total=4, offset=1, limit=2)


async def test_deal_count_counts_the_deals_referencing_each_contact(api: Api) -> None:
    """Scenario: deal_count는 고객 또는 파트너로 참조하는 Deal 수이고 없으면 0이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    customer = await given_contact(api, "customer", company="고객사")
    partner = await given_contact(api, "partner", company="파트너사")
    idle = await given_contact(api, "customer", company="한가한고객", name="박영희", email=None)
    await given_deal_of_contacts(api, customer_id=customer["id"], partner_id=partner["id"])
    await given_deal_of_contacts(api, customer_id=customer["id"])
    # When
    response = await when_search_contacts(api)
    # Then
    then_deal_counts_are(response, {customer["id"]: 2, partner["id"]: 1, idle["id"]: 0})


async def test_a_page_beyond_the_end_is_empty_but_keeps_the_total(api: Api) -> None:
    """Scenario: 끝을 넘어선 페이지는 items가 비지만 total은 전체 건수이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_people(api, 3)
    # When
    response = await when_search_contacts(api, offset=10, limit=5)
    # Then
    assert response.json()["items"] == []
    then_page_is(response, total=3, offset=10, limit=5)


async def test_a_keyword_of_100_characters_is_accepted(api: Api) -> None:
    """Scenario: 키워드 100자는 허용된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_search_contacts(api, keyword="k" * 100)
    # Then
    then_status_is(response, 200)


async def test_a_keyword_over_100_characters_is_a_request_validation_error(api: Api) -> None:
    """Scenario: 키워드 101자는 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_search_contacts(api, keyword="k" * 101)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_a_keyword_with_a_nul_character_is_422_invalid_value(api: Api) -> None:
    """Scenario: 키워드에 NUL 문자가 있으면 500이 아니라 422 invalid-value이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_search_contacts(api, keyword="a\x00b")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


@pytest.mark.parametrize(
    "params",
    [{"foo": "1"}, {"keyword": "a", "company_name": "a"}, {"kind": "supplier"}],
    ids=["unknown-parameter", "retired-parameter", "unknown-kind"],
)
async def test_unknown_parameters_and_kinds_are_request_validation_errors(
    api: Api, params: dict[str, str]
) -> None:
    """Scenario: 모르는 쿼리 파라미터나 모르는 kind는 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_search_contacts(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"limit": 201}])
async def test_invalid_paging_is_a_request_validation_error_even_with_a_keyword(
    api: Api, params: dict[str, int]
) -> None:
    """Scenario: offset < 0, limit 0 또는 201은 키워드가 있어도 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_search_contacts(api, keyword="a", **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
