"""Feature: Deal을 수정하면 바뀐 필드마다 이력이 남는다.

PATCH는 보낸 필드만 바꾼다. 바뀐 필드마다 화면과 같은 target·before·after 이력이 남고(최신순 조회),
바뀐 것이 없으면 이력도 updated_at도 그대로다. 파트너는 교체해도 이전 링크가 남는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    NOT_FOUND,
    customer_draft,
    given_deal,
    given_label_id,
    partner_draft,
    then_deal_keeps,
    then_history_is,
    when_get_deal,
    when_list_history,
    when_update_deal,
)
from tests.functional.steps.session import when_log_out
from tests.functional.steps.vendors import given_vendor

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_only_the_sent_fields_change_and_each_is_logged(api: Api) -> None:
    """Scenario: 보낸 필드만 바뀌고 바뀐 필드마다 이력(화면과 같은 표기)이 남는다."""
    # Given
    oracle = await given_vendor(api, "Oracle")
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    api.clock.advance(3600)
    # When
    response = await when_update_deal(
        api,
        deal["code"],
        name="확장 프로젝트",
        revenue_amount=1_870_000_000,
        revenue_date="2026-12-31",
        vendor_id=oracle.id,
        users=10,
        status_key="price_negotiation",
    )
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert body["name"] == "확장 프로젝트"
    assert body["vendor"] == {"id": oracle.id, "name": "Oracle"}
    assert body["solution"] is None
    assert body["revenue_amount"] == 1_870_000_000
    await then_history_is(
        api,
        deal["code"],
        [
            ("status", "Status", "기회발굴", "가격협상"),
            ("amount", "금액(단위:천원)", "150,000", "1,870,000"),
            ("expectedClose", "Expected Close", "2026-06-30", "2026-12-31"),
            ("other", "Deal Name", "ERP 구축", "확장 프로젝트"),
            ("other", "Vendor", "선택 안 함", "Oracle"),
            ("other", "Users", "-", "10"),
        ],
    )
    assert body["updated_at"] > deal["updated_at"]


async def test_an_unchanged_patch_leaves_no_history_and_keeps_updated_at(api: Api) -> None:
    """Scenario: 같은 값을 보내면 이력 0건이고 updated_at도 그대로다."""
    # Given
    sap = await given_vendor(api, "SAP")
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, vendor_id=sap.id)
    api.clock.advance(3600)
    # When
    response = await when_update_deal(
        api, deal["code"], name="ERP 구축", revenue_amount=150_000_000, vendor_id=sap.id
    )
    # Then
    then_status_is(response, 200)
    assert response.json()["updated_at"] == deal["updated_at"]
    await then_history_is(api, deal["code"], [])


async def test_quote_poc_and_procurement_are_logged_with_their_formats(api: Api) -> None:
    """Scenario: 견적·POC·구매절차 변경은 other 구분의 이력으로 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    await when_update_deal(
        api,
        deal["code"],
        quote={"submitted": "YES", "submitted_date": "2026-10-01"},
        poc={"state": "ING", "completed_date": None},
        procurement="조달청 입찰",
    )
    # Then
    await then_history_is(
        api,
        deal["code"],
        [
            ("other", "견적", "-", "YES (2026-10-01)"),
            ("other", "POC", "-", "ING"),
            ("other", "구매절차", "-", "조달청 입찰"),
        ],
    )


async def test_bant_labels_can_be_changed_and_cleared(api: Api) -> None:
    """Scenario: BANT Label을 바꾸면 구분별 이력이 남고 비우면 '선택 안 함'이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    none = {"budget": None, "authority": None, "need": None, "timeline": None}
    # When
    await when_update_deal(api, deal["code"], bant={**none, "budget": budget})
    await when_update_deal(api, deal["code"], bant=none)
    # Then
    await then_history_is(
        api,
        deal["code"],
        [
            ("bant", "BANT Label: Budget", "선택 안 함", "풀 예산 확보"),
            ("bant", "BANT Label: Budget", "풀 예산 확보", "선택 안 함"),
        ],
    )


async def test_replacing_the_partner_keeps_the_previous_link_in_the_detail(api: Api) -> None:
    """Scenario: 파트너를 교체하면 이전 링크는 비활성으로 남아 partner_history에 나온다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, partner=partner_draft(company="코어테크", name="민지훈"))
    api.clock.advance(60)
    # When
    response = await when_update_deal(
        api, deal["code"], partner=partner_draft(company="에이원", name="표성호")
    )
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert body["active_partner"]["company"] == "에이원"
    assert [(h["contact"]["company"], h["active"]) for h in body["partner_history"]] == [
        ("에이원", True),
        ("코어테크", False),
    ]
    assert [link["active"] for link in body["partner_links"]].count(True) == 1
    inactive = next(h for h in body["partner_history"] if not h["active"])
    assert inactive["unlinked_at"] is not None
    await then_history_is(
        api, deal["code"], [("partner", "파트너", "코어테크 민지훈", "에이원 표성호")]
    )


async def test_partner_null_removes_only_the_active_link(api: Api) -> None:
    """Scenario: partner를 null로 보내면 활성 링크만 비활성이 되고 이력에 '없음'이 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, partner=partner_draft())
    # When
    response = await when_update_deal(api, deal["code"], partner=None)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert body["active_partner"] is None
    assert [h["active"] for h in body["partner_history"]] == [False]
    await then_history_is(api, deal["code"], [("partner", "파트너", "한빛파트너스 이영희", "없음")])


async def test_the_same_partner_or_an_omitted_partner_changes_nothing(api: Api) -> None:
    """Scenario: 같은 파트너를 다시 보내거나 partner를 보내지 않으면 변화가 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api, partner=partner_draft())
    same = {"contact_id": deal["active_partner"]["id"], **partner_draft()}
    # When
    await when_update_deal(api, deal["code"], partner=same)
    await when_update_deal(api, deal["code"], name="ERP 구축")
    # Then
    await then_history_is(api, deal["code"], [])
    body = (await when_get_deal(api, deal["code"])).json()
    assert len(body["partner_history"]) == 1


async def test_changing_the_customer_is_logged_as_a_contact_change(api: Api) -> None:
    """Scenario: 고객을 다른 사람으로 바꾸면 contact 구분 이력이 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    await when_update_deal(
        api, deal["code"], customer=customer_draft(company="대한상사", name="오세훈")
    )
    # Then
    await then_history_is(
        api, deal["code"], [("contact", "고객 연락처", "네오인 김철수", "대한상사 오세훈")]
    )


async def test_history_is_listed_newest_first_and_can_be_filtered_by_category(api: Api) -> None:
    """Scenario: 이력은 최신순이고 category로 거를 수 있다. 모르는 category는 422다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    for name in ("B", "C"):
        api.clock.advance(60)
        await when_update_deal(api, deal["code"], name=name)
    api.clock.advance(60)
    await when_update_deal(api, deal["code"], status_key="introduction")
    # When
    everything = await when_list_history(api, deal["code"])
    others = await when_list_history(api, deal["code"], category="other")
    unknown = await when_list_history(api, deal["code"], category="nonsense")
    # Then
    assert [e["after"] for e in everything.json()] == ["제품소개", "C", "B", "Deal 등록"]
    assert [e["after"] for e in others.json()] == ["C", "B"]
    assert all(
        {"id", "deal_code", "at", "by", "category", "target", "before", "after"} == set(e)
        for e in everything.json()
    )
    assert isinstance(everything.json()[0]["id"], str)
    then_problem_is(unknown, status=422, type_suffix="request-validation")


async def test_history_of_an_unknown_deal_is_not_found(api: Api) -> None:
    """Scenario: 없는 Deal의 이력 조회는 404이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_history(api, "20260101-ZZZZ")
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    assert response.json()["detail"] == NOT_FOUND


async def test_updating_an_unknown_or_malformed_code_is_not_found(api: Api) -> None:
    """Scenario: 없는 code와 형식이 틀린 code는 모두 같은 404 문구다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    unknown = await when_update_deal(api, "20260101-ZZZZ", name="B")
    malformed = await when_update_deal(api, "not-a-code", name="B")
    # Then
    for response in (unknown, malformed):
        then_problem_is(response, status=404, type_suffix="not-found")
        assert response.json()["detail"] == NOT_FOUND


async def test_an_invalid_patch_is_a_422_and_changes_nothing(api: Api) -> None:
    """Scenario: 보낸 필드가 잘못되면 422이고 Deal도 이력도 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_update_deal(api, deal["code"], name="", revenue_amount=0)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == "Deal Name을 입력하세요."
    await then_deal_keeps(api, deal["code"], name="ERP 구축")
    await then_history_is(api, deal["code"], [])


async def test_a_read_only_user_cannot_update(api: Api) -> None:
    """Scenario: 조회 전용(user)은 수정할 수 없다(403). 비로그인은 401이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_logged_in_as(api, role="user", login_id="viewer")
    # When
    forbidden = await when_update_deal(api, deal["code"], name="B")
    await when_log_out(api)
    anonymous = await when_update_deal(api, deal["code"], name="B")
    # Then
    then_problem_is(forbidden, status=403, type_suffix="forbidden")
    then_problem_is(anonymous, status=401, type_suffix="unauthenticated")
