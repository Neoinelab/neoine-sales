"""Feature: 목록에서 Deal을 찾고 상세를 본다.

기본 정렬은 최근 갱신 순(동률은 code 오름차순), total은 필터 적용 후 전체 건수다.
keyword·owner·vendor_id·status·기간·내 딜 필터는 모두 AND로 결합한다. 확장 필터(연/분기·BANT·
solution_id·forecast)와 정렬 선택은 다음 라운드(R3)에서 같은 feature에 시나리오가 늘어난다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_user_registered
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    NOT_FOUND,
    customer_draft,
    given_deal,
    list_codes,
    partner_draft,
    when_get_deal,
    when_list_deals,
    when_update_deal,
)
from tests.functional.steps.users import log_in
from tests.functional.steps.vendors import given_vendor

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_the_list_has_rows_total_offset_and_limit_newest_first(api: Api) -> None:
    """Scenario: 목록은 {items, total, offset, limit}이고 가장 최근에 갱신된 Deal이 먼저다."""
    # Given
    await given_logged_in_as(api, role="sales")
    first = await given_deal(api, name="첫째")
    second = await given_deal(api, name="둘째")
    third = await given_deal(api, name="셋째")
    # When
    response = await when_list_deals(api)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert (body["total"], body["offset"], body["limit"]) == (3, 0, 20)
    assert list_codes(response) == [third["code"], second["code"], first["code"]]
    row = body["items"][0]
    assert row["owner"]["role"] == "sales"
    assert row["customer"]["company"] == "네오인"
    assert (row["next_action"], row["risk"]) == (None, None)
    assert row["last_updated_at"] == row["updated_at"]


async def test_editing_a_deal_moves_it_to_the_top(api: Api) -> None:
    """Scenario: Deal을 수정하면 그 Deal이 목록 맨 위로 온다."""
    # Given
    await given_logged_in_as(api, role="sales")
    old = await given_deal(api, name="오래된 딜")
    newer = await given_deal(api, name="새 딜")
    api.clock.advance(60)
    await when_update_deal(api, old["code"], name="수정된 딜")
    # When
    response = await when_list_deals(api)
    # Then
    assert list_codes(response) == [old["code"], newer["code"]]


async def test_total_ignores_the_page_and_limit_is_bounded(api: Api) -> None:
    """Scenario: 페이지를 잘라도 total은 필터 후 전체 건수이고 limit은 1~200이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    for number in range(5):
        await given_deal(api, name=f"딜{number}")
    # When
    page = await when_list_deals(api, offset=3, limit=1)
    too_many = await when_list_deals(api, limit=201)
    # Then
    assert (page.json()["total"], len(page.json()["items"])) == (5, 1)
    then_problem_is(too_many, status=422, type_suffix="request-validation")


async def test_keyword_matches_name_customer_active_partner_and_code(api: Api) -> None:
    """Scenario: keyword는 Deal Name·고객 회사·활성 파트너 회사·code를 대소문자 무시로 찾는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    by_name = await given_deal(api, name="ErP 구축")
    by_customer = await given_deal(
        api, name="도입 과제 A", customer=customer_draft(company="한빛은행", name="정민수")
    )
    by_partner = await given_deal(
        api, name="도입 과제 B", partner=partner_draft(company="코어테크", name="민지훈")
    )
    replaced = await given_deal(
        api, name="도입 과제 C", partner=partner_draft(company="에이원", name="표성호")
    )
    await when_update_deal(
        api, replaced["code"], partner=partner_draft(company="대한", name="최민수")
    )
    # When
    name = await when_list_deals(api, keyword="erp")
    customer = await when_list_deals(api, keyword="한빛")
    partner = await when_list_deals(api, keyword="코어테크")
    inactive = await when_list_deals(api, keyword="에이원")
    code = await when_list_deals(api, keyword=by_name["code"].lower())
    # Then
    assert list_codes(name) == [by_name["code"]]
    assert list_codes(customer) == [by_customer["code"]]
    assert list_codes(partner) == [by_partner["code"]]
    assert list_codes(inactive) == []  # 비활성 파트너는 검색 대상이 아니다
    assert list_codes(code) == [by_name["code"]]


async def test_filters_combine_with_and(api: Api) -> None:
    """Scenario: owner·vendor_id·status·기간·keyword는 모두 AND로 결합한다."""
    # Given
    sap = await given_vendor(api, "SAP")
    oracle = await given_vendor(api, "Oracle")
    await given_logged_in_as(api, role="sales")
    hit = await given_deal(
        api, name="ERP", vendor_id=sap.id, status_key="introduction", revenue_date="2026-06-15"
    )
    await given_deal(
        api, name="ERP", vendor_id=oracle.id, status_key="introduction", revenue_date="2026-06-15"
    )
    await given_deal(
        api, name="ERP", vendor_id=sap.id, status_key="prospecting", revenue_date="2026-06-15"
    )
    await given_deal(
        api, name="ERP", vendor_id=sap.id, status_key="introduction", revenue_date="2026-08-01"
    )
    await given_deal(
        api, name="CRM", vendor_id=sap.id, status_key="introduction", revenue_date="2026-06-15"
    )
    # When
    response = await when_list_deals(
        api,
        keyword="erp",
        owner_user_id=hit["owner_user_id"],
        vendor_id=sap.id,
        status_key="introduction",
        revenue_from="2026-06-01",
        revenue_to="2026-06-30",
    )
    # Then
    assert list_codes(response) == [hit["code"]]
    assert response.json()["total"] == 1


async def test_the_revenue_period_includes_both_ends(api: Api) -> None:
    """Scenario: revenue_from/to는 양끝을 포함한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    for day in ("2026-05-31", "2026-06-01", "2026-06-30", "2026-07-01"):
        await given_deal(api, name=day, revenue_date=day)
    # When
    response = await when_list_deals(api, revenue_from="2026-06-01", revenue_to="2026-06-30")
    # Then
    names = sorted(item["name"] for item in response.json()["items"])
    assert names == ["2026-06-01", "2026-06-30"]


async def test_an_unknown_status_key_gives_zero_results_not_an_error(api: Api) -> None:
    """Scenario: 존재하지 않는 status_key는 오류 없이 0건이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_deal(api)
    # When
    response = await when_list_deals(api, status_key="no_such_status")
    # Then
    then_status_is(response, 200)
    assert (response.json()["items"], response.json()["total"]) == ([], 0)


async def test_mine_lists_only_the_deals_the_viewer_owns(api: Api) -> None:
    """Scenario: mine=true는 요청자가 Owner인 Deal만이고 owner_user_id보다 우선한다."""
    # Given
    alice = await given_logged_in_as(api, role="sales", login_id="alice")
    mine = await given_deal(api, name="앨리스 딜")
    await given_user_registered(api, login_id="bob", role="sales")
    await log_in(api, "bob")
    theirs = await given_deal(api, name="밥 딜")
    # When
    bob_mine = await when_list_deals(api, mine="true")
    bob_ignores_owner = await when_list_deals(api, mine="true", owner_user_id=mine["owner_user_id"])
    everyone = await when_list_deals(api)
    # Then
    assert alice == "alice"
    assert list_codes(bob_mine) == [theirs["code"]]
    assert list_codes(bob_ignores_owner) == [theirs["code"]]
    assert set(list_codes(everyone)) == {mine["code"], theirs["code"]}


@pytest.mark.parametrize(
    "params",
    [
        {"stage": "lost"},
        {"customer_id": "x"},
        {"owner": "박영업"},
        {"mine": "maybe"},
        {"offset": -1},
    ],
)
async def test_retired_or_malformed_parameters_are_request_validation_errors(
    api: Api, params: dict[str, str | int]
) -> None:
    """Scenario: 폐지된 조건과 잘못된 값은 422(request-validation)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_a_nul_character_in_the_keyword_is_a_422_not_a_server_error(api: Api) -> None:
    """Scenario: keyword에 NUL 문자가 있으면 500이 아니라 422(invalid-value)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, keyword="a\x00b")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


async def test_everyone_logged_in_can_read_but_anonymous_cannot(api: Api) -> None:
    """Scenario: 조회 전용(user)도 목록·상세를 보고, 비로그인은 401이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_logged_in_as(api, role="user")
    # When
    listing = await when_list_deals(api)
    detail = await when_get_deal(api, deal["code"])
    await api.post("/api/v1/auth/logout")
    api.forget_session()
    anonymous = await when_list_deals(api)
    # Then
    then_status_is(listing, 200)
    then_status_is(detail, 200)
    then_problem_is(anonymous, status=401, type_suffix="unauthenticated")


async def test_the_detail_is_the_row_plus_the_partner_history(api: Api) -> None:
    """Scenario: 상세는 목록 행 + partner_history이고 형식이 틀린 code와 없는 code는 같은 404다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, partner=partner_draft())
    # When
    detail = await when_get_deal(api, deal["code"])
    unknown = await when_get_deal(api, "20260101-ZZZZ")
    malformed = await when_get_deal(api, "bad-code")
    # Then
    then_status_is(detail, 200)
    assert detail.json() == deal
    assert [h["active"] for h in detail.json()["partner_history"]] == [True]
    for missing in (unknown, malformed):
        then_problem_is(missing, status=404, type_suffix="not-found")
        assert missing.json()["detail"] == NOT_FOUND
