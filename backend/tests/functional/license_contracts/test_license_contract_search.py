"""Feature: 계약관리 목록은 Deal 값 기준으로 검색·정렬되고 서버가 전체 건수를 알려 준다.

고객사명·제품명(Solution)·Vendor·담당영업(Owner)은 계약이 아니라 Deal 값이다. 모든 로그인 역할이
읽을 수 있다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_user_registered
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import customer_draft
from tests.functional.steps.license_contracts import (
    contracts_of,
    given_contract_of,
    given_issued_contract,
    given_won_deal,
    then_contract_has_the_documented_keys,
    when_end,
    when_list_contracts,
)
from tests.functional.steps.users import given_signed_in_session
from tests.functional.steps.vendors import given_vendor

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _three_contracts(api: Api) -> dict[str, dict[str, Any]]:
    """알파(SAP, kim, 발급 1년), 베타(Oracle, park, 발급 6개월), 감마(미발급)."""
    await given_logged_in_as(api)
    sap = await given_vendor(api, "SAP")
    oracle = await given_vendor(api, "Oracle")
    kim = await given_user_registered(api, login_id="kim", role="sales")
    park = await given_user_registered(api, login_id="park", role="sales")
    alpha = await given_won_deal(
        api,
        owner_user_id=kim,
        vendor_id=sap.id,
        solution="S/4HANA",
        customer=customer_draft(company="알파상사", name="알파", email="a@alpha.example"),
    )
    beta = await given_won_deal(
        api,
        owner_user_id=park,
        vendor_id=oracle.id,
        solution="Oracle EBS",
        customer=customer_draft(company="베타물산", name="베타", email="b@beta.example"),
    )
    gamma = await given_won_deal(
        api,
        owner_user_id=kim,
        solution="ERP Cloud",
        customer=customer_draft(company="감마전자", name="감마", email="g@gamma.example"),
    )
    await given_issued_contract(api, alpha, start="2026-01-01", amount=1, unit="year")
    await given_issued_contract(api, beta, start="2026-07-01", amount=6, unit="month")
    return {
        "alpha": {"code": alpha, "vendor": sap.id, "owner": kim},
        "beta": {"code": beta, "vendor": oracle.id, "owner": park},
        "gamma": {"code": gamma, "vendor": None, "owner": kim},
    }


def _customers(response_json: dict[str, Any]) -> list[str]:
    return [str(item["customer"]) for item in response_json["items"]]


async def test_listing_returns_the_page_total_and_the_documented_keys(api: Api) -> None:
    """Scenario: 목록 응답은 items·total·offset·limit이고 각 항목은 계약 응답 모양이다."""
    # Given
    await _three_contracts(api)
    # When
    response = await when_list_contracts(api)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert set(body) == {"items", "total", "offset", "limit"}
    assert (body["total"], body["offset"], body["limit"]) == (3, 0, 50)
    for item in body["items"]:
        then_contract_has_the_documented_keys(item)
    first = body["items"][0]
    assert first["deal_name"] == "ERP 구축"
    assert first["sales_owner"]["role"] == "sales"


async def test_the_customer_filter_is_a_case_insensitive_partial_match_on_the_deal(
    api: Api,
) -> None:
    """Scenario: 고객사명 조건은 Deal 고객 회사명의 부분 일치다."""
    # Given
    await _three_contracts(api)
    # When
    response = await when_list_contracts(api, customer="물산")
    # Then
    then_status_is(response, 200)
    assert _customers(response.json()) == ["베타물산"]
    assert response.json()["total"] == 1


async def test_the_product_filter_matches_the_deal_solution_ignoring_case(api: Api) -> None:
    """Scenario: 제품명 조건은 Deal Solution의 부분 일치(대소문자 무시)다."""
    # Given
    await _three_contracts(api)
    # When
    response = await when_list_contracts(api, product="ebs")
    # Then
    assert _customers(response.json()) == ["베타물산"]


async def test_the_vendor_filter_matches_the_deal_vendor_id(api: Api) -> None:
    """Scenario: Vendor 조건은 Deal의 vendor_id 일치다."""
    # Given
    data = await _three_contracts(api)
    # When
    response = await when_list_contracts(api, vendor_id=int(data["alpha"]["vendor"]))
    # Then
    assert _customers(response.json()) == ["알파상사"]


async def test_the_sales_owner_filter_matches_the_deal_owner(api: Api) -> None:
    """Scenario: 담당영업 조건은 Deal Owner의 user id 일치다."""
    # Given
    data = await _three_contracts(api)
    # When
    response = await when_list_contracts(api, owner_user_id=int(data["beta"]["owner"]))
    # Then
    assert _customers(response.json()) == ["베타물산"]
    both = await when_list_contracts(api, owner_user_id=int(data["alpha"]["owner"]))
    assert sorted(_customers(both.json())) == ["감마전자", "알파상사"]


@pytest.mark.parametrize(
    ("status", "expected"),
    [("not_issued", ["감마전자"]), ("issued_new", ["베타물산", "알파상사"]), ("ended", [])],
)
async def test_the_status_filter(api: Api, status: str, expected: list[str]) -> None:
    """Scenario: 상태 조건은 계약 상태 일치다."""
    # Given
    await _three_contracts(api)
    # When
    response = await when_list_contracts(api, status=status)
    # Then
    assert sorted(_customers(response.json())) == sorted(expected)
    assert response.json()["total"] == len(expected)


async def test_date_ranges_are_inclusive_and_exclude_contracts_without_dates(api: Api) -> None:
    """Scenario: 시작일·종료일 범위는 양끝 포함이고 날짜가 없는 계약은 제외된다."""
    # Given
    await _three_contracts(api)
    # When
    by_start = await when_list_contracts(api, start_from="2026-01-01", start_to="2026-07-01")
    only_after = await when_list_contracts(api, start_from="2026-07-01")
    by_end = await when_list_contracts(api, end_to="2026-12-31")
    until = await when_list_contracts(api, end_from="2027-01-01")
    # Then
    assert sorted(_customers(by_start.json())) == ["베타물산", "알파상사"]
    assert _customers(only_after.json()) == ["베타물산"]
    assert sorted(_customers(by_end.json())) == ["베타물산", "알파상사"]
    assert _customers(until.json()) == []


async def test_a_reversed_date_range_is_422(api: Api) -> None:
    """Scenario: 범위의 시작이 끝보다 늦으면 422(invalid-value)다."""
    # Given
    await given_logged_in_as(api)
    # When
    start = await when_list_contracts(api, start_from="2026-02-01", start_to="2026-01-01")
    end = await when_list_contracts(api, end_from="2026-02-01", end_to="2026-01-01")
    # Then
    then_problem_is(start, status=422, type_suffix="invalid-value")
    then_problem_is(end, status=422, type_suffix="invalid-value")


async def test_the_default_order_is_the_end_date_ascending_with_empty_dates_last(api: Api) -> None:
    """Scenario: 기본 정렬은 종료일 오름차순이고 날짜 없는 계약은 맨 뒤다."""
    # Given
    await _three_contracts(api)
    # When
    response = await when_list_contracts(api)
    # Then
    # 알파와 베타의 종료일이 같아(2026-12-31) 동률은 id 오름차순이다
    assert _customers(response.json()) == ["알파상사", "베타물산", "감마전자"]


@pytest.mark.parametrize(
    ("sort", "order", "expected"),
    [
        ("customer", "asc", ["감마전자", "베타물산", "알파상사"]),
        ("customer", "desc", ["알파상사", "베타물산", "감마전자"]),
        ("vendor", "asc", ["베타물산", "알파상사", "감마전자"]),
        ("vendor", "desc", ["알파상사", "베타물산", "감마전자"]),
        ("status", "asc", ["감마전자", "알파상사", "베타물산"]),
        ("status", "desc", ["알파상사", "베타물산", "감마전자"]),
        ("license_start", "asc", ["알파상사", "베타물산", "감마전자"]),
        ("license_start", "desc", ["베타물산", "알파상사", "감마전자"]),
    ],
)
async def test_sorting_follows_the_deal_values_and_keeps_empty_values_last(
    api: Api, sort: str, order: str, expected: list[str]
) -> None:
    """Scenario: 열 정렬은 Deal 값 기준이고 값 없는 칸은 방향과 무관하게 맨 뒤다."""
    # Given
    await _three_contracts(api)
    # When
    response = await when_list_contracts(api, sort=sort, order=order)
    # Then
    then_status_is(response, 200)
    assert _customers(response.json()) == expected


async def test_paging_returns_consecutive_slices_and_a_stable_total(api: Api) -> None:
    """Scenario: offset·limit으로 나눠 읽어도 순서가 이어지고 total은 전체 건수다."""
    # Given
    await _three_contracts(api)
    # When
    first = await when_list_contracts(api, sort="customer", limit=2)
    second = await when_list_contracts(api, sort="customer", limit=2, offset=2)
    # Then
    assert _customers(first.json()) == ["감마전자", "베타물산"]
    assert _customers(second.json()) == ["알파상사"]
    assert first.json()["total"] == second.json()["total"] == 3


async def test_a_wildcard_character_in_the_filter_is_literal(api: Api) -> None:
    """Scenario: 조건의 %와 _는 와일드카드가 아니라 글자 그대로다."""
    # Given
    await _three_contracts(api)
    # When
    percent = await when_list_contracts(api, customer="%")
    underscore = await when_list_contracts(api, customer="_")
    # Then
    assert _customers(percent.json()) == []
    assert _customers(underscore.json()) == []


async def test_ended_contracts_are_listed_with_the_ended_status(api: Api) -> None:
    """Scenario: 종료된 계약도 목록에 남고 종료 상태로 보인다."""
    # Given
    data = await _three_contracts(api)
    contract = await given_contract_of(api, str(data["gamma"]["code"]))
    then_status_is(await when_end(api, contract["id"]), 200)
    # When
    response = await when_list_contracts(api, status="ended")
    # Then
    assert _customers(response.json()) == ["감마전자"]
    assert len(await contracts_of(api, str(data["gamma"]["code"]))) == 1


@pytest.mark.parametrize("role", ["sales", "user"])
async def test_every_role_can_read_the_list(api: Api, role: str) -> None:
    """Scenario: sales·user도 목록을 읽을 수 있다."""
    # Given
    await _three_contracts(api)
    session = await given_signed_in_session(api, login_id=f"{role}-reader", role=role)  # type: ignore[arg-type]
    # When
    response = await when_list_contracts(api, session=session)
    # Then
    then_status_is(response, 200)
    assert response.json()["total"] == 3
