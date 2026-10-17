"""Feature: 영업은 Deal을 등록한다.

sales·admin이 새 고객·파트너 입력과 함께 Deal을 등록하면 code가 발급되고(날짜는 서버 로컬 시간대),
등록 이력이 남는다. 입력 검증과 권한은 test_deal_registration_validation.py다.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_user_registered
from tests.functional.steps.common import then_body_includes, then_status_is
from tests.functional.steps.deals import (
    CREATED_ENTRY,
    given_clock_at,
    given_deal,
    given_label_id,
    partner_draft,
    then_code_date_is_local_today,
    then_history_is,
    when_list_history,
    when_register_deal,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

DETAIL_KEYS = {
    "code",
    "name",
    "owner_user_id",
    "owner",
    "vendor",
    "solution",
    "users",
    "status_key",
    "forecast_key",
    "revenue_amount",
    "revenue_date",
    "customer",
    "active_partner",
    "partner_links",
    "quote",
    "poc",
    "procurement",
    "bant",
    "next_action",
    "last_updated_at",
    "status_changed_at",
    "status_days",
    "risk",
    "created_at",
    "updated_at",
    "partner_history",
}


async def test_sales_registers_a_deal_with_a_new_customer_and_partner(api: Api) -> None:
    """Scenario: 새 고객·파트너 입력으로 등록하면 201, Location, 발급된 code, 연락처가 생긴다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(
        api,
        partner=partner_draft(),
        users=250,
        quote={"submitted": "YES", "submitted_date": "2026-10-01"},
        poc={"state": "ING", "completed_date": None},
        procurement="조달청 입찰",
    )
    # Then
    then_status_is(response, 201)
    then_code_date_is_local_today(response, api)
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert (body["name"], body["vendor"], body["users"]) == ("ERP 구축", "SAP", 250)
    assert body["revenue_amount"] == 150_000_000
    assert isinstance(body["revenue_amount"], int)
    assert (body["status_key"], body["forecast_key"]) == ("prospecting", "pipeline")
    assert body["owner"]["role"] == "sales"
    assert body["customer"]["company"] == "네오인"
    assert body["active_partner"]["company"] == "한빛파트너스"
    assert [link["active"] for link in body["partner_links"]] == [True]
    assert [h["active"] for h in body["partner_history"]] == [True]
    assert body["quote"] == {"submitted": "YES", "submitted_date": "2026-10-01"}
    assert body["procurement"] == "조달청 입찰"
    assert (body["next_action"], body["risk"]) == (None, None)
    assert body["last_updated_at"] == body["updated_at"]


@pytest.mark.parametrize(
    ("zone", "registered_at", "expected_day"),
    [
        ("Asia/Seoul", datetime(2026, 10, 15, 15, 30, tzinfo=UTC), "20261016"),
        ("Asia/Seoul", datetime(2026, 10, 15, 14, 59, tzinfo=UTC), "20261015"),
        ("UTC", datetime(2026, 10, 15, 15, 30, tzinfo=UTC), "20261015"),
        ("UTC", datetime(2026, 10, 16, 0, 0, tzinfo=UTC), "20261016"),
    ],
)
async def test_the_code_date_is_the_server_local_calendar_day(
    api: Api,
    local_tz: Callable[[str], None],
    zone: str,
    registered_at: datetime,
    expected_day: str,
) -> None:
    """Scenario: code 날짜는 서버 프로세스 로컬 시간대의 달력 날짜다(UTC와 다를 수 있다)."""
    # Given
    local_tz(zone)
    await given_logged_in_as(api, role="sales")
    await given_clock_at(api, registered_at)
    # When
    response = await when_register_deal(api)
    # Then
    then_status_is(response, 201)
    assert str(response.json()["code"]).startswith(f"{expected_day}-")


async def test_registration_is_recorded_in_history_by_the_requester(api: Api) -> None:
    """Scenario: 등록하면 이력 한 건(등록)이 남고 변경자는 요청자다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_list_history(api, deal["code"])
    # Then
    then_status_is(response, 200)
    (entry,) = response.json()
    assert (entry["category"], entry["target"], entry["before"], entry["after"]) == CREATED_ENTRY
    assert entry["by"]["id"] == deal["owner_user_id"]
    assert entry["deal_code"] == deal["code"]
    assert datetime.fromisoformat(entry["at"]) == api.clock.now()


async def test_a_deal_has_only_the_registration_entry_right_after_registering(api: Api) -> None:
    """Scenario: 등록 직후 이력은 등록 한 건뿐이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    deal = await given_deal(api, name="새 딜")
    # Then
    await then_history_is(api, deal["code"], [])


async def test_an_admin_registers_a_deal_for_a_sales_owner(api: Api) -> None:
    """Scenario: admin이 등록하면 Owner는 지정한 영업 담당자이고 이력의 변경자는 admin이다."""
    # Given
    sales_id = await given_user_registered(api, login_id="park", role="sales")
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_deal(api, owner_user_id=sales_id)
    # Then
    then_status_is(response, 201)
    body = response.json()
    assert (body["owner"]["id"], body["owner"]["role"]) == (sales_id, "sales")
    history = await when_list_history(api, body["code"])
    assert history.json()[0]["by"]["role"] == "admin"


async def test_the_same_customer_person_is_reused_across_deals(api: Api) -> None:
    """Scenario: 같은 고객 입력으로 두 번 등록하면 연락처가 하나로 재사용된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    first = await given_deal(api)
    # When
    second = await given_deal(api)
    # Then
    assert second["customer"]["id"] == first["customer"]["id"]
    assert first["code"] != second["code"]


async def test_bant_labels_are_saved_one_per_category(api: Api) -> None:
    """Scenario: 구분별 Label id를 보내면 저장되고 응답 bant에 그대로 나온다."""
    # Given
    await given_logged_in_as(api, role="sales")
    budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    timeline = await given_label_id(api, category="timeline", name="금년 구매")
    chosen = {"budget": budget, "authority": None, "need": None, "timeline": timeline}
    # When
    response = await when_register_deal(api, bant=chosen)
    # Then
    then_status_is(response, 201)
    then_body_includes(response, bant=chosen)
