"""Feature: 연도 선택지의 기준인 "가장 이른 Expected Close 연도"를 모든 로그인 역할이 읽는다.

`GET /api/v1/deals/years`는 `{"earliest_year": <연도 | null>}`만 돌려준다(선택지 규칙은 화면 몫).
Deal이 하나도 없으면 null이다. 삭제·수정을 바로 반영한다. 경로는 Deal code로 해석되지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_years import (
    given_deals_closing_on,
    then_earliest_year_is,
    when_get_years,
    when_get_years_as,
)
from tests.functional.steps.deals import given_deal_deleted, when_update_deal
from tests.functional.steps.users import given_signed_in_session

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_years_is_null_without_deals(api: Api) -> None:
    """Scenario: Deal이 하나도 없으면 earliest_year는 null이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_get_years(api)
    # Then
    then_earliest_year_is(response, None)


async def test_years_returns_earliest_expected_close_year(api: Api) -> None:
    """Scenario: Deal의 Expected Close 중 가장 이른 날짜의 연도를 돌려준다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_deals_closing_on(api, "2024-05-01", "2019-12-31", "2027-01-01")
    # When
    response = await when_get_years(api)
    # Then
    then_earliest_year_is(response, 2019)


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_role_can_read_years(api: Api, role: str) -> None:
    """Scenario: admin·sales·user 모두 같은 값을 읽는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_deals_closing_on(api, "2023-03-01", "2026-06-30")
    reader = await given_signed_in_session(api, login_id=f"{role}-reader", role=role)  # type: ignore[arg-type]
    # When
    response = await when_get_years_as(api, reader)
    # Then
    then_earliest_year_is(response, 2023)


async def test_years_path_is_not_taken_as_a_deal_code(api: Api) -> None:
    """Scenario: /deals/years는 Deal 조회(404 Deal을 찾을 수 없음)가 아니라 연도 응답이다."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_get_years(api)
    # Then
    then_status_is(response, 200)
    assert set(response.json()) == {"earliest_year"}


async def test_years_requires_login(api: Api) -> None:
    """Scenario: 로그인하지 않으면 401이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_get_years(api)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_years_moves_after_the_oldest_deal_is_deleted(api: Api) -> None:
    """Scenario: 가장 이른 Deal을 삭제하면 그다음으로 이른 연도가 된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    oldest, _ = await given_deals_closing_on(api, "2019-05-01", "2024-05-01")
    assert (await when_get_years(api)).json() == {"earliest_year": 2019}
    await given_deal_deleted(api, oldest["code"])
    # When
    response = await when_get_years(api)
    # Then
    then_earliest_year_is(response, 2024)


async def test_years_is_null_after_the_last_deal_is_deleted(api: Api) -> None:
    """Scenario: 마지막 Deal을 삭제하면 다시 null이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    (only,) = await given_deals_closing_on(api, "2025-05-01")
    await given_deal_deleted(api, only["code"])
    # When
    response = await when_get_years(api)
    # Then
    then_earliest_year_is(response, None)


async def test_years_follows_an_expected_close_update(api: Api) -> None:
    """Scenario: Expected Close를 더 이른 해로 고치면 그 연도가 된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    (deal,) = await given_deals_closing_on(api, "2026-06-30")
    assert (await when_get_years(api)).json() == {"earliest_year": 2026}
    updated = await when_update_deal(api, deal["code"], revenue_date="2021-02-03")
    then_status_is(updated, 200)
    # When
    response = await when_get_years(api)
    # Then
    then_earliest_year_is(response, 2021)
