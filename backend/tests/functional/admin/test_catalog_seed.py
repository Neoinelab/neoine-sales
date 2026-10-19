"""Feature: 새로 배포한 시스템에는 기본 코드·기본 BANT Label·기본 Action 유형이 이미 들어 있다.

`fresh_api`는 마이그레이션만 적용한 새 임시 DB 위의 앱이다. 다른 시나리오가 복원하는 기본값
(`tests/fakes/catalog_seed.py`)이 마이그레이션이 실제로 넣는 시드와 같은지 여기서 대조한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.fakes.catalog_seed import DEFAULT_FORECASTS, DEFAULT_LABELS, DEFAULT_STATUSES, LOCKED
from tests.functional.steps.action_types import (
    then_every_type_has_the_documented_fields,
    then_types_are_the_defaults,
    when_list_types,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import when_list_code_usage, when_list_codes
from tests.functional.steps.common import then_status_is
from tests.functional.steps.labels import then_labels_are_the_defaults, when_list_labels

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_new_system_has_the_default_status_codes(fresh_api: Api) -> None:
    """Scenario: 마이그레이션 직후 Status는 기회발굴…계약완료 7개이고 두 개가 잠겨 있다(AC-01)."""
    # Given
    await given_logged_in_as(fresh_api, role="admin")
    # When
    response = await when_list_codes(fresh_api)
    # Then
    then_status_is(response, 200)
    assert [
        (c["key"], c["name"], c["order"], c["locked"], c["outcome"], c["probability_hint"])
        for c in response.json()["statuses"]
    ] == [
        (key, name, order, ("status", key) in LOCKED, "open", None)
        for order, (key, name) in enumerate(DEFAULT_STATUSES, start=1)
    ]


async def test_new_system_has_the_default_forecast_codes(fresh_api: Api) -> None:
    """Scenario: 마이그레이션 직후 Forecast는 6개이고 확률 힌트·결과가 목업과 같다(AC-01)."""
    # Given
    await given_logged_in_as(fresh_api, role="admin")
    # When
    response = await when_list_codes(fresh_api)
    # Then
    then_status_is(response, 200)
    assert [
        (c["key"], c["name"], c["order"], c["locked"], c["outcome"], c["probability_hint"])
        for c in response.json()["forecasts"]
    ] == [
        (key, name, order, ("forecast", key) in LOCKED, outcome, hint)
        for order, (key, name, outcome, hint) in enumerate(DEFAULT_FORECASTS, start=1)
    ]


async def test_new_system_has_the_23_default_labels(fresh_api: Api) -> None:
    """Scenario: 마이그레이션 직후 기본 Label은 구분별 7·6·5·5개, 모두 만든 사람이 없다(AC-10)."""
    # Given
    await given_logged_in_as(fresh_api, role="admin")
    # When
    response = await when_list_labels(fresh_api)
    # Then
    then_status_is(response, 200)
    then_labels_are_the_defaults(response)
    counts = [sum(1 for x in response.json() if x["category"] == c) for c in DEFAULT_LABELS]
    assert counts == [7, 6, 5, 5]


async def test_new_system_has_the_8_default_action_types(fresh_api: Api) -> None:
    """Scenario: 마이그레이션 직후 기본 Action 유형은 Fake 시드와 같은 8개이고 만든 사람이 없다."""
    # Given
    await given_logged_in_as(fresh_api, role="admin")
    # When
    response = await when_list_types(fresh_api)
    # Then
    then_status_is(response, 200)
    then_types_are_the_defaults(response)
    then_every_type_has_the_documented_fields(response)
    assert len(response.json()) == 8


async def test_new_system_has_no_deal_using_any_code(fresh_api: Api) -> None:
    """Scenario: Deal이 없는 새 시스템에서 모든 코드의 사용 수는 0이다(AC-02)."""
    # Given
    await given_logged_in_as(fresh_api, role="admin")
    # When
    response = await when_list_code_usage(fresh_api, kind="status")
    # Then
    then_status_is(response, 200)
    assert [c["usage_count"] for c in response.json()] == [0] * 7
