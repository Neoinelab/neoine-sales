"""Feature: 같은 사람(3단계 규칙)은 연락처로 한 번만 등록되고 동시에 등록해도 한 건만 생긴다.

같은 구분 안에서 회사명·담당자명(대소문자 무시)이 같고 (1) 이메일까지 같거나 (2) 한쪽에 이메일이
없으면 같은 사람이다. 이메일이 서로 다르면 동명이인이다. 프런트 `findSamePerson`과 같은 규칙이며
409 '이미 등록된 연락처입니다.'(AC-20).
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.contacts import (
    DUPLICATE_MESSAGE,
    contact_payload,
    given_contact,
    then_detail_is,
    then_total_contacts_are,
    when_create_contact,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_the_same_company_and_name_without_email_conflicts(api: Api) -> None:
    """Scenario: 이메일 없이 같은 회사명·담당자명을 다시 등록하면 409이고 한 건만 남는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, email=None)
    # When
    response = await when_create_contact(api, contact_payload(email=None, title="다른 직급"))
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    then_detail_is(response, DUPLICATE_MESSAGE)
    await then_total_contacts_are(api, 1)


async def test_the_same_email_ignoring_case_conflicts(api: Api) -> None:
    """Scenario: 이메일까지 같으면(대소문자 무시) 같은 사람이라 409이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, email="kim@neoine.example")
    # When
    response = await when_create_contact(api, contact_payload(email="KIM@Neoine.Example"))
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    await then_total_contacts_are(api, 1)


async def test_company_and_name_are_compared_ignoring_case(api: Api) -> None:
    """Scenario: 회사명·담당자명은 대소문자만 달라도 같은 사람으로 본다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, company="Acme", name="Kim", email=None)
    # When
    response = await when_create_contact(
        api, contact_payload(company="ACME", name="KIM", email=None)
    )
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")


async def test_a_different_email_is_a_namesake_and_is_registered(api: Api) -> None:
    """Scenario: 둘 다 이메일이 있고 서로 다르면 동명이인이라 새로 등록된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, email="kim1@neoine.example")
    # When
    response = await when_create_contact(api, contact_payload(email="kim2@neoine.example"))
    # Then
    then_status_is(response, 201)
    await then_total_contacts_are(api, 2)


async def test_filling_in_an_email_for_a_contact_without_one_conflicts(api: Api) -> None:
    """Scenario: 이메일 없는 기존 연락처에 이메일을 채워 등록하려 하면 같은 사람이라 409이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, email=None)
    # When
    response = await when_create_contact(api, contact_payload(email="kim@neoine.example"))
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    await then_total_contacts_are(api, 1)


async def test_registering_without_email_conflicts_with_a_namesake_that_has_one(api: Api) -> None:
    """Scenario: 이메일 없이 입력하면 같은 회사명·담당자명의 기존 연락처와 같은 사람이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, email="kim@neoine.example")
    # When
    response = await when_create_contact(api, contact_payload(email=None))
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")


async def test_the_same_person_in_the_other_kind_is_registered(api: Api) -> None:
    """Scenario: 같은 회사명·담당자명이라도 구분(고객/파트너)이 다르면 별개로 등록된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_contact(api, "customer", company="공용회사", name="공용이름", email=None)
    # When
    response = await when_create_contact(
        api, contact_payload("partner", company="공용회사", name="공용이름", email=None)
    )
    # Then
    then_status_is(response, 201)
    await then_total_contacts_are(api, 2)
