"""Feature: admin은 코드와 BANT Label의 실제 사용 수를 보고, 사용 중인 항목은 지울 수 없다.

사용 수는 Deal의 status_key·forecast_key·BANT 선택 기준이다. 사용 중인 코드·Label의 삭제는 409이고
메시지에 실제 Deal 수가 들어간다. 쓰던 Deal이 모두 사라지면 다시 지울 수 있다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import (
    given_code_id,
    in_use_message,
    then_code_exists,
    then_code_is_gone,
    then_detail_is,
    then_usage_counts_are,
    when_delete_code,
    when_list_code_usage,
)
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    given_deal,
    given_deal_deleted,
    given_label_id,
    given_sales_owner,
)
from tests.functional.steps.labels import (
    given_label_list,
    then_label_exists,
    then_label_is_gone,
    when_delete_label,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _label_usage(api: Api, label_id: str) -> int:
    (found,) = [x for x in await given_label_list(api) if x["id"] == label_id]
    usage = found["usage_count"]
    assert isinstance(usage, int)
    return usage


async def test_forecast_usage_counts_the_deals_using_each_forecast(api: Api) -> None:
    """Scenario: Forecast 사용 수는 Deal의 forecast_key 기준이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    owner = await given_sales_owner(api)
    await given_deal(api, owner_user_id=owner, forecast_key="best")
    await given_deal(api, owner_user_id=owner, forecast_key="best")
    await given_deal(api, owner_user_id=owner, forecast_key="commit")
    # When
    response = await when_list_code_usage(api, kind="forecast")
    # Then
    then_status_is(response, 200)
    then_usage_counts_are(response, {"best": 2, "commit": 1})


async def test_a_forecast_in_use_cannot_be_deleted_until_its_deals_are_gone(api: Api) -> None:
    """Scenario: 사용 중인 Forecast는 409(실제 Deal 수)이고 Deal이 사라지면 지울 수 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    owner = await given_sales_owner(api)
    deal = await given_deal(api, owner_user_id=owner, forecast_key="best")
    best_id = await given_code_id(api, kind="forecast", key="best")
    # When
    refused = await when_delete_code(api, code_id=best_id)
    # Then
    then_problem_is(refused, status=409, type_suffix="invalid-state")
    then_detail_is(refused, in_use_message(1))
    await then_code_exists(api, kind="forecast", key="best")
    await given_deal_deleted(api, deal["code"])
    removed = await when_delete_code(api, code_id=best_id)
    then_status_is(removed, 204)
    await then_code_is_gone(api, kind="forecast", key="best")


async def test_a_status_in_use_cannot_be_deleted(api: Api) -> None:
    """Scenario: 사용 중인 Status 코드의 삭제는 409이고 메시지에 Deal 수가 들어간다."""
    # Given
    await given_logged_in_as(api, role="admin")
    owner = await given_sales_owner(api)
    await given_deal(api, owner_user_id=owner, status_key="introduction")
    await given_deal(api, owner_user_id=owner, status_key="introduction")
    introduction_id = await given_code_id(api, kind="status", key="introduction")
    # When
    response = await when_delete_code(api, code_id=introduction_id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, in_use_message(2))
    await then_code_exists(api, kind="status", key="introduction")


async def test_label_usage_counts_the_deals_that_selected_it(api: Api) -> None:
    """Scenario: Label 목록의 usage_count는 그 Label을 선택한 Deal 수다."""
    # Given
    await given_logged_in_as(api, role="admin")
    owner = await given_sales_owner(api)
    budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    need = await given_label_id(api, category="need", name="CISO 지시")
    await given_deal(api, owner_user_id=owner, bant={"budget": budget, "need": need})
    await given_deal(api, owner_user_id=owner, bant={"budget": budget})
    await given_deal(api, owner_user_id=owner)
    # When
    labels = await given_label_list(api)
    # Then
    counts = {x["id"]: x["usage_count"] for x in labels if x["usage_count"]}
    assert counts == {budget: 2, need: 1}


async def test_a_label_in_use_cannot_be_deleted_by_admin(api: Api) -> None:
    """Scenario: 사용 중인 Label은 409(실제 Deal 수)이고 Label과 Deal의 선택은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    owner = await given_sales_owner(api)
    budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    deal = await given_deal(api, owner_user_id=owner, bant={"budget": budget})
    await given_deal(api, owner_user_id=owner, bant={"budget": budget})
    # When
    response = await when_delete_label(api, label_id=budget)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == "사용 중인 Label은 삭제할 수 없습니다. (Deal 2건)"
    await then_label_exists(api, category="budget", name="풀 예산 확보")
    assert await _label_usage(api, budget) == 2
    assert deal["bant"]["budget"] == budget


async def test_a_label_becomes_deletable_once_no_deal_selects_it(api: Api) -> None:
    """Scenario: 선택한 Deal이 모두 사라지면 Label을 지울 수 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    owner = await given_sales_owner(api)
    budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    deal = await given_deal(api, owner_user_id=owner, bant={"budget": budget})
    await given_deal_deleted(api, deal["code"])
    # When
    response = await when_delete_label(api, label_id=budget)
    # Then
    then_status_is(response, 204)
    await then_label_is_gone(api, category="budget", name="풀 예산 확보")
