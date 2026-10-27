"""Feature: 저장한 리포트를 덮어쓰거나 다른 이름으로 저장하고, 복제한다.

수정은 revision이 맞을 때만 되고(낙관적 잠금), 이름은 모든 리포트 사이에서 대소문자 무시로
고유하다. 공개 범위는 만든 사람 또는 admin만 바꾼다.
(관련 단위 테스트: tests/unit/domain/test_saved_report_entity.py,
tests/unit/web/test_saved_report_*.py)
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is
from tests.functional.steps.saved_reports import (
    OTHER_DEFINITION,
    SIMPLE_DEFINITION,
    given_logged_in,
    given_report_overwritten,
    given_saved_report,
    given_users,
    report_body,
    then_listed_ids_are,
    then_report_equals,
    when_copy_report,
    when_list_reports,
    when_save_report,
    when_update_report,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_overwrite_replaces_the_content_and_bumps_the_revision(api: Api) -> None:
    """Scenario: 현재 revision으로 덮어쓰면 내용·SQL이 바뀌고 revision 2가 되며 만든 사람은 같다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "원본", definition=SIMPLE_DEFINITION)
    # When
    response = await when_update_report(
        api,
        saved["id"],
        {
            **report_body("수정본", description="새 설명", definition=OTHER_DEFINITION),
            "revision": 1,
        },
    )
    # Then
    then_status_is(response, 200)
    body = response.json()
    then_body_includes(response, name="수정본", description="새 설명", revision=2)
    assert body["owner"] == saved["owner"]
    assert body["definition"]["columns"][0]["field"] == "deal.vendor"
    assert body["generated_sql"] != saved["generated_sql"]  # 새 정의로 다시 만든 SQL
    assert body["updated_at"] > saved["updated_at"]
    assert body["created_at"] == saved["created_at"]
    await then_report_equals(api, saved["id"], body)


async def test_save_as_creates_a_new_report_and_keeps_the_original(api: Api) -> None:
    """Scenario: 다른 이름으로 저장하면 새 id·revision 1의 리포트가 생기고 원본은 그대로다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "원본")
    original = await given_report_overwritten(api, saved, "원본")
    # When
    response = await when_save_report(api, report_body("원본 복사본", definition=OTHER_DEFINITION))
    # Then
    then_status_is(response, 201)
    assert response.json()["id"] != saved["id"]
    then_body_includes(response, name="원본 복사본", revision=1)
    await then_report_equals(api, saved["id"], original)
    then_listed_ids_are(await when_list_reports(api), [response.json()["id"], saved["id"]])


async def test_copy_takes_the_definition_from_the_original(api: Api) -> None:
    """Scenario: 복제하면 정의는 원본 그대로이고 만든 사람은 복제한 사람이다."""
    # Given
    await given_users(api, alice="sales", bob="user")
    await given_logged_in(api, "alice")
    source = await given_saved_report(api, "원본", definition=OTHER_DEFINITION)
    await given_logged_in(api, "bob")
    # When
    response = await when_copy_report(
        api, source["id"], {"name": "원본 복사본", "description": "복제", "visibility": "private"}
    )
    # Then
    then_status_is(response, 201)
    body = response.json()
    assert response.headers["location"] == f"/api/v1/reports/{body['id']}"
    assert body["definition"] == source["definition"]
    assert body["owner"]["id"] != source["owner"]["id"]
    then_body_includes(
        response, name="원본 복사본", description="복제", visibility="private", revision=1
    )


async def test_stale_revision_is_rejected(api: Api) -> None:
    """Scenario: 이전 revision으로 덮어쓰면 409 invalid-state이고 내용은 그대로다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "원본", visibility="public")
    await given_logged_in(api, "bob")
    first = await given_report_overwritten(api, saved, "bob의 수정", visibility="public")
    # When
    response = await when_update_report(
        api, saved["id"], {**report_body("늦은 수정", visibility="public"), "revision": 1}
    )
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"].startswith("다른 사용자가 먼저 이 리포트를 저장했습니다")
    await then_report_equals(api, saved["id"], first)


async def test_duplicate_name_ignoring_case_is_rejected(api: Api) -> None:
    """Scenario: 대소문자만 다른 같은 이름으로 또 저장하면 409이고 하나만 남는다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "Sales Report")
    # When
    response = await when_save_report(api, report_body("sales report"))
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == "같은 이름의 리포트가 이미 있습니다."
    then_listed_ids_are(await when_list_reports(api), [saved["id"]])


async def test_renaming_to_another_own_report_name_is_rejected(api: Api) -> None:
    """Scenario: 자기 다른 리포트의 이름으로 바꾸면 409 already-exists이고 그대로다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    await given_saved_report(api, "첫째")
    second = await given_saved_report(api, "둘째")
    # When
    response = await when_update_report(api, second["id"], {**report_body("첫째"), "revision": 1})
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    await then_report_equals(api, second["id"], second)


async def test_same_name_as_another_users_private_report_is_rejected(api: Api) -> None:
    """Scenario: 다른 사람의 비공개 리포트와 같은 이름(대소문자 무시)으로 저장하면 409이다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    await given_saved_report(api, "공통 이름", visibility="private")
    await given_logged_in(api, "bob")
    # When
    response = await when_save_report(api, report_body("공통 이름"))
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == "같은 이름의 리포트가 이미 있습니다."
    then_listed_ids_are(await when_list_reports(api), [])


async def test_copy_checks_names_of_every_report(api: Api) -> None:
    """Scenario: 복제할 이름이 다른 리포트와 겹치면 409 already-exists이다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    source = await given_saved_report(api, "원본", visibility="public")
    await given_logged_in(api, "bob")
    await given_saved_report(api, "내 리포트")
    # When
    response = await when_copy_report(
        api, source["id"], {"name": "내 리포트", "visibility": "public"}
    )
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")


async def test_editing_with_a_bad_definition_keeps_the_stored_report(api: Api) -> None:
    """Scenario: 규칙을 어긴 정의로 덮어쓰려 하면 invalid-report이고 저장된 리포트는 그대로다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    saved = await given_saved_report(api, "원본")
    # When
    response = await when_update_report(
        api,
        saved["id"],
        {
            **report_body("망가진 수정", definition={"columns": [{"field": "nope.x"}]}),
            "revision": 1,
        },
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-report")
    await then_report_equals(api, saved["id"], saved)
