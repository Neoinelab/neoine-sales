"""Feature: 코드·BANT Label 입력에 NUL 문자가 오면 500이 아니라 422로 거절된다.

PostgreSQL은 문자열의 NUL(\\x00)을 저장하지 못한다. 서버가 DB 오류(500)를 내지 않고 기존 입력
규약처럼 422 invalid-value로 답해야 하며, 거절된 요청은 아무것도 바꾸지 않는다.
확률 힌트는 앞뒤 공백을 제거하고 빈 값이면 비운다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.fakes.catalog_seed import DEFAULT_LABELS
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import (
    given_code_id,
    then_code_count_is,
    then_code_name_is,
    when_create_code,
    when_rename_code,
)
from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is
from tests.functional.steps.labels import (
    given_label_id,
    then_label_count_is,
    then_label_names_are,
    when_create_label,
    when_rename_label,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

NUL_TEXTS = ["a\x00b", "\x00", "name\x00"]
NUL_IDS = ["inside", "only", "trailing"]
FIRST_BUDGET_LABEL = DEFAULT_LABELS["budget"][0]


@pytest.mark.parametrize("name", NUL_TEXTS, ids=NUL_IDS)
async def test_creating_a_status_code_with_a_nul_in_the_name_is_422(api: Api, name: str) -> None:
    """Scenario: 이름에 NUL이 든 Status 코드 추가는 422이고 코드는 늘지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="status", name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_code_count_is(api, kind="status", count=7)


@pytest.mark.parametrize(
    "hint", ["1\x002", "\x00", "10-20\x00"], ids=["inside", "only", "trailing"]
)
async def test_creating_a_forecast_code_with_a_nul_in_the_hint_is_422(api: Api, hint: str) -> None:
    """Scenario: 확률 힌트에 NUL이 든 Forecast 코드 추가는 422이고 코드는 늘지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="forecast", name="Upside", probability_hint=hint)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_code_count_is(api, kind="forecast", count=6)


@pytest.mark.parametrize("name", NUL_TEXTS, ids=NUL_IDS)
async def test_renaming_a_code_with_a_nul_in_the_name_is_422_and_keeps_the_name(
    api: Api, name: str
) -> None:
    """Scenario: 이름에 NUL을 넣어 코드 이름을 바꾸면 422이고 이름은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="introduction")
    # When
    response = await when_rename_code(api, code_id=code_id, name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_code_name_is(api, kind="status", key="introduction", name="제품소개")


@pytest.mark.parametrize("name", NUL_TEXTS, ids=NUL_IDS)
async def test_creating_a_label_with_a_nul_in_the_name_is_422(api: Api, name: str) -> None:
    """Scenario: 이름에 NUL이 든 BANT Label 추가는 422이고 Label은 늘지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_label(api, category="need", name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_label_count_is(api, count=23)


@pytest.mark.parametrize("name", NUL_TEXTS, ids=NUL_IDS)
async def test_renaming_a_label_with_a_nul_in_the_name_is_422_and_keeps_the_name(
    api: Api, name: str
) -> None:
    """Scenario: 이름에 NUL을 넣어 Label 이름을 바꾸면 422이고 이름은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    label_id = await given_label_id(api, category="budget", name=FIRST_BUDGET_LABEL)
    # When
    response = await when_rename_label(api, label_id=label_id, name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_label_names_are(api, category="budget", names=list(DEFAULT_LABELS["budget"]))


@pytest.mark.parametrize(
    ("sent", "stored"),
    [("  10-20  ", "10-20"), ("", None), ("   ", None)],
    ids=["trimmed", "empty", "blank"],
)
async def test_a_forecast_hint_is_trimmed_and_a_blank_hint_is_stored_as_null(
    api: Api, sent: str, stored: str | None
) -> None:
    """Scenario: 확률 힌트는 앞뒤 공백이 제거되고 빈 값이면 null로 저장된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(api, kind="forecast", name="Upside", probability_hint=sent)
    # Then
    then_status_is(response, 201)
    then_body_includes(response, probability_hint=stored)
    await then_code_count_is(api, kind="forecast", count=7)


@pytest.mark.parametrize("sent", ["", "   "], ids=["empty", "blank"])
async def test_a_status_code_with_a_blank_hint_is_created_without_a_hint(
    api: Api, sent: str
) -> None:
    """Scenario: 프런트가 빈 입력을 ""로 보내도 Status 코드는 힌트 없이 만들어진다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_create_code(
        api, kind="status", name="Final Review", probability_hint=sent
    )
    # Then
    then_status_is(response, 201)
    then_body_includes(response, probability_hint=None)
    await then_code_count_is(api, kind="status", count=8)
