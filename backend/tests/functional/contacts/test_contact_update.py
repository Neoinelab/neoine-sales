"""Feature: admin은 연락처의 값을 바꾸되 구분(kind)은 바꿀 수 없고, 다른 사람이 되려 하면 거절된다.

수정에도 등록과 같은 입력 규칙(공백 거절, 형식 검사)과 같은 사람 판정(자기 자신 제외)이 적용된다
(AC-19·20·21). 구 `/customers/{id}`·`/partners/{id}` 수정 시나리오를 옮겼다.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.contacts import (
    DUPLICATE_MESSAGE,
    EMAIL_MESSAGE,
    WHITESPACE_MESSAGE,
    given_contact,
    then_contact_has_the_documented_fields,
    then_contact_values_are,
    then_detail_is,
    update_payload,
    update_payload_with_extra,
    when_search_contacts,
    when_update_contact,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _listed(api: Api, contact_id: str) -> dict[str, object]:
    items = (await when_search_contacts(api, limit=200)).json()["items"]
    return next(item for item in items if item["id"] == contact_id)


async def test_admin_replaces_every_field_of_a_contact(api: Api) -> None:
    """Scenario: 수정하면 모든 값이 바뀌고 id·구분·등록 시각은 그대로이며 수정 시각이 갱신된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_contact(api, "partner")
    api.clock.advance(300)
    # When
    response = await when_update_contact(
        api,
        created["id"],
        update_payload(
            company="새회사",
            name="박영희",
            title="대표",
            email="NEW@Hanbit.Example",
            phone="031-777-4321",
        ),
    )
    # Then
    then_status_is(response, 200)
    then_contact_has_the_documented_fields(response)
    then_contact_values_are(
        response,
        id=created["id"],
        kind="partner",
        company="새회사",
        name="박영희",
        title="대표",
        email="new@hanbit.example",
        phone="031-777-4321",
        created_at=created["created_at"],
    )
    assert datetime.fromisoformat(response.json()["updated_at"]) > datetime.fromisoformat(
        created["created_at"]
    )
    assert await _listed(api, created["id"]) | {"deal_count": 0} == response.json() | {
        "deal_count": 0
    }


async def test_update_can_clear_the_optional_fields(api: Api) -> None:
    """Scenario: 직급·이메일·전화를 null로 보내면 지워진다."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_contact(api)
    # When
    response = await when_update_contact(
        api, created["id"], update_payload(title=None, email=None, phone=None)
    )
    # Then
    then_status_is(response, 200)
    then_contact_values_are(response, title=None, email=None, phone=None)


async def test_update_with_kind_in_the_body_is_rejected_and_the_kind_stays(api: Api) -> None:
    """Scenario: 수정 본문에 kind가 있으면 422(request-validation)이고 구분은 바뀌지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_contact(api, "customer")
    # When
    response = await when_update_contact(
        api, created["id"], update_payload_with_extra("kind", "partner")
    )
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    assert (await _listed(api, created["id"]))["kind"] == "customer"


@pytest.mark.parametrize("field", ["company_name", "employee_count", "notes", "x"])
async def test_update_rejects_unknown_and_retired_fields(api: Api, field: str) -> None:
    """Scenario: 모르는 필드와 구 고객 API의 필드가 있으면 422이고 값은 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_contact(api)
    # When
    response = await when_update_contact(api, created["id"], update_payload_with_extra(field))
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    assert (await _listed(api, created["id"]))["company"] == created["company"]


@pytest.mark.parametrize(
    ("overrides", "detail"),
    [
        ({"company": "네오 인"}, WHITESPACE_MESSAGE),
        ({"name": " 김철수"}, WHITESPACE_MESSAGE),
        ({"email": "kim @neoine.example"}, WHITESPACE_MESSAGE),
        ({"phone": "010 1234 5678"}, WHITESPACE_MESSAGE),
        ({"email": "not-an-email"}, EMAIL_MESSAGE),
    ],
)
async def test_update_with_invalid_values_is_422_and_changes_nothing(
    api: Api, overrides: dict[str, str], detail: str
) -> None:
    """Scenario: 공백·형식이 틀린 값으로 수정하면 422이고 기존 값이 그대로 남는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_contact(api)
    # When
    response = await when_update_contact(api, created["id"], update_payload(**overrides))
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, detail)
    listed = await _listed(api, created["id"])
    assert (listed["company"], listed["name"], listed["email"]) == (
        created["company"],
        created["name"],
        created["email"],
    )


async def test_update_of_an_unknown_contact_is_404(api: Api) -> None:
    """Scenario: 없는 연락처를 수정하면 404 '연락처를 찾을 수 없습니다.'이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_contact(api, str(uuid4()), update_payload())
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    then_detail_is(response, "연락처를 찾을 수 없습니다.")


async def test_update_with_a_malformed_id_is_a_request_validation_error(api: Api) -> None:
    """Scenario: id가 UUID 형식이 아니면 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_contact(api, "not-a-uuid", update_payload())
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_update_into_another_existing_person_conflicts_and_changes_nothing(
    api: Api,
) -> None:
    """Scenario: 이미 있는 다른 사람과 같은 회사명·담당자명으로 바꾸면 409이고 그대로 남는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, name="김철수", email=None)
    other = await given_contact(api, name="박영희", email=None)
    # When
    response = await when_update_contact(
        api, other["id"], update_payload(name="김철수", email=None)
    )
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    then_detail_is(response, DUPLICATE_MESSAGE)
    assert (await _listed(api, other["id"]))["name"] == "박영희"


async def test_update_keeping_its_own_person_is_not_a_conflict(api: Api) -> None:
    """Scenario: 자기 자신과 같은 회사명·담당자명으로 다른 값만 바꾸는 수정은 충돌이 아니다."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_contact(api, email=None)
    # When
    response = await when_update_contact(
        api, created["id"], update_payload(email=None, title="이사")
    )
    # Then
    then_status_is(response, 200)
    then_contact_values_are(response, title="이사")


async def test_update_changing_only_the_case_of_the_company_is_not_a_conflict(api: Api) -> None:
    """Scenario: 자기 회사명의 대소문자만 바꾸는 수정은 충돌이 아니다."""
    # Given
    await given_logged_in_as(api, role="admin")
    created = await given_contact(api, company="Acme", email=None)
    # When
    response = await when_update_contact(
        api, created["id"], update_payload(company="ACME", email=None)
    )
    # Then
    then_status_is(response, 200)
    then_contact_values_are(response, company="ACME")


async def test_update_into_a_namesake_with_another_email_is_allowed(api: Api) -> None:
    """Scenario: 둘 다 이메일이 있고 서로 다르면 같은 이름이어도 동명이인이라 수정된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, name="김철수", email="kim1@neoine.example")
    other = await given_contact(api, name="박영희", email="park@neoine.example")
    # When
    response = await when_update_contact(
        api, other["id"], update_payload(name="김철수", email="kim2@neoine.example")
    )
    # Then
    then_status_is(response, 200)
