"""Feature: 영업은 Deals 목록을 Next Action 상태로 거른다.

기준은 Next Action이 있는 가장 최근 Action의 상태다(그 뒤에 진행사항만 있는 Action이 있어도 같다).
선택지는 open / done / not_done / closed(= done 또는 not_done)이고, 상태 필터가 있으면 Next Action이
한 번도 없는 Deal은 제외된다. total은 같은 조건으로 센다. 허용하지 않는 값은 422다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import given_action
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.deal_lists import then_codes_are_exactly, then_total_is
from tests.functional.steps.deals import given_deal, when_list_deals
from tests.functional.steps.next_action_status import (
    given_progress_only_action,
    given_status_changed,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _three_deals(api: Api) -> tuple[str, str, str]:
    """A: 기준 행 done 뒤에 진행사항만, B: 기준 행 open, C: 진행사항만. 그리고 Action 없는 D."""
    await given_logged_in_as(api, role="sales")
    deal_a = str((await given_deal(api, name="A"))["code"])
    deal_b = str((await given_deal(api, name="B"))["code"])
    deal_c = str((await given_deal(api, name="C"))["code"])
    await given_deal(api, name="D")
    basis = await given_action(api, deal_a, action="A 기준")
    await given_status_changed(api, basis["id"], "done")
    await given_progress_only_action(api, deal_a, action="A 이후 진행")
    await given_action(api, deal_b, action="B 기준")
    await given_progress_only_action(api, deal_c, action="C 진행")
    return deal_a, deal_b, deal_c


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param("open", ["B"], id="open"),
        pytest.param("done", ["A"], id="done"),
        pytest.param("not_done", [], id="not-done"),
        pytest.param("closed", ["A"], id="closed"),
    ],
)
async def test_status_filter_uses_the_status_of_the_basis_row(
    api: Api, status: str, expected: list[str]
) -> None:
    """Scenario: 기준 행의 상태로 거르고, total도 같은 조건으로 센다."""
    # Given
    codes = dict(zip("ABC", await _three_deals(api), strict=True))
    # When
    response = await when_list_deals(api, next_action_status=status)
    # Then
    then_codes_are_exactly(response, [codes[name] for name in expected])
    then_total_is(response, len(expected))


async def test_without_a_status_filter_every_deal_is_listed(api: Api) -> None:
    """Scenario: 상태 조건이 없으면 Next Action이 없는 Deal까지 모두 나온다."""
    # Given
    await _three_deals(api)
    # When
    response = await when_list_deals(api)
    # Then
    then_total_is(response, 4)


async def test_closed_filter_includes_not_done_basis_rows(api: Api) -> None:
    """Scenario: closed는 종료(미수행) 기준 행도 포함한다."""
    # Given
    deal_a, deal_b, _ = await _three_deals(api)
    other = await given_action(api, deal_b, action="B 새 기준")
    await given_status_changed(api, other["id"], "not_done")
    # When
    response = await when_list_deals(api, next_action_status="closed")
    # Then
    then_codes_are_exactly(response, sorted([deal_a, deal_b]))
    then_total_is(response, 2)


async def test_status_filter_combines_with_other_conditions(api: Api) -> None:
    """Scenario: 상태 조건은 검색어와 AND로 결합된다."""
    # Given
    deal_a, _, _ = await _three_deals(api)
    # When
    hit = await when_list_deals(api, next_action_status="closed", keyword=deal_a)
    miss = await when_list_deals(api, next_action_status="open", keyword=deal_a)
    # Then
    then_codes_are_exactly(hit, [deal_a])
    then_codes_are_exactly(miss, [])


@pytest.mark.parametrize("value", ["notDone", "DONE", "all", "", "close"])
async def test_a_status_outside_the_allowed_values_is_rejected(api: Api, value: str) -> None:
    """Scenario: 허용하지 않는 상태 값은 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_list_deals(api, next_action_status=value)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
