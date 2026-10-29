"""Feature: Solution 도입 전에 만들어진 Deal(Solution 빈 값)도 Solution과 무관한 변경은 그대로 된다.

빈 값 거절은 solution을 보낸 경우에만 한다(등록은 항상 필수, 수정은 보낸 때만).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_changes import when_change_deal
from tests.functional.steps.deals import then_deal_keeps, when_update_deal
from tests.functional.steps.legacy_solution import (
    SOLUTION_REQUIRED,
    given_legacy_deal_without_solution,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_partial_update_without_solution_succeeds_on_a_legacy_deal(api: Api) -> None:
    """Scenario: Solution이 빈 Deal의 Users count와 이름만 수정하면 성공하고

    Solution은 빈 채로 남는다.
    """
    # Given
    await given_logged_in_as(api, role="sales")
    code = await given_legacy_deal_without_solution(api)
    # When
    response = await when_update_deal(api, code, users=7, name="수정한 이름")
    # Then
    then_status_is(response, 200)
    await then_deal_keeps(api, code, users=7, name="수정한 이름", solution="")


async def test_blank_solution_in_update_is_rejected_on_a_legacy_deal(api: Api) -> None:
    """Scenario: Solution이 빈 Deal이라도 빈 solution을 보내면 422(invalid-value)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    code = await given_legacy_deal_without_solution(api)
    # When
    response = await when_update_deal(api, code, solution="  ")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == SOLUTION_REQUIRED
    await then_deal_keeps(api, code, solution="")


async def test_single_change_of_amount_succeeds_on_a_legacy_deal(api: Api) -> None:
    """Scenario: Solution이 빈 Deal의 매출금액을 단일 변경하면 성공한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    code = await given_legacy_deal_without_solution(api)
    # When
    response = await when_change_deal(api, code, "revenue_amount", 321_000_000)
    # Then
    then_status_is(response, 200)
    await then_deal_keeps(api, code, revenue_amount=321_000_000, solution="")
