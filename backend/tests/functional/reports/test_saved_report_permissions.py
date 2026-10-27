"""Feature: 저장 리포트는 공개 범위와 만든 사람, 역할에 따라 보고 고치고 지운다.

볼 수 없는 리포트(남의 비공개)는 없는 id와 똑같이 404이고 문구도 같다. admin은 모든 리포트를 본다.
남의 공개 리포트는 고칠 수 있지만 지우거나 공개 범위를 바꿀 수는 없다(admin 제외).
(결정 표: artifacts/10-analysis/01-plan.md 4.3,
단위 테스트: tests/unit/domain/test_saved_report_policy.py)
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.saved_reports import (
    given_logged_in,
    given_logged_in_as_admin,
    given_report_overwritten,
    given_saved_report,
    given_users,
    report_body,
    then_hidden_looks_like_missing,
    then_listed_ids_are,
    then_report_equals,
    then_report_is_not_found,
    when_delete_report,
    when_get_report,
    when_list_reports,
    when_run_saved_report,
    when_touch_report,
    when_update_report,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
METHODS = ["GET", "PUT", "DELETE", "COPY", "RUN"]


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("role", ["sales", "user"])
async def test_others_private_report_is_hidden_like_a_missing_one(
    api: Api, role: str, method: str
) -> None:
    """Scenario: 남의 비공개 리포트는 보기·수정·삭제·복제·실행 모두 없는 id와 같은 404이다."""
    # Given
    await given_users(api, alice="sales", bob=role)  # type: ignore[arg-type]
    await given_logged_in(api, "alice")
    private = await given_saved_report(api, "비공개", visibility="private")
    await given_logged_in(api, "bob")
    # When
    response = await when_touch_report(api, method, private["id"])
    # Then
    then_report_is_not_found(response)
    await then_hidden_looks_like_missing(api, response, method)
    await given_logged_in(api, "alice")
    await then_report_equals(api, private["id"], private)


async def test_list_shows_public_and_own_reports_only(api: Api) -> None:
    """Scenario: 목록에는 공개 리포트와 내 리포트만 나온다(남의 비공개는 없다)."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    alice_private = await given_saved_report(api, "alice 비공개", visibility="private")
    alice_public = await given_saved_report(api, "alice 공개", visibility="public")
    await given_logged_in(api, "bob")
    bob_private = await given_saved_report(api, "bob 비공개", visibility="private")
    # When
    response = await when_list_reports(api)
    # Then
    then_listed_ids_are(response, [bob_private["id"], alice_public["id"]])
    assert alice_private["id"] not in [item["id"] for item in response.json()]


async def test_admin_sees_others_private_reports(api: Api) -> None:
    """Scenario: admin은 남의 비공개 리포트도 목록에서 보고 열고 실행한다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    private = await given_saved_report(api, "비공개", visibility="private")
    await given_logged_in_as_admin(api)
    # When
    response = await when_list_reports(api)
    # Then
    then_listed_ids_are(response, [private["id"]])
    then_status_is(await when_get_report(api, private["id"]), 200)
    then_status_is(await when_run_saved_report(api, private["id"]), 200)


@pytest.mark.parametrize("role", ["sales", "user"])
async def test_non_admin_can_overwrite_others_public_report(api: Api, role: str) -> None:
    """Scenario: sales·user도 남의 공개 리포트를 고칠 수 있고 만든 사람은 바뀌지 않는다."""
    # Given
    await given_users(api, alice="sales", bob=role)  # type: ignore[arg-type]
    await given_logged_in(api, "alice")
    public = await given_saved_report(api, "공개", visibility="public")
    await given_logged_in(api, "bob")
    # When
    response = await when_update_report(
        api, public["id"], {**report_body("bob이 고침", visibility="public"), "revision": 1}
    )
    # Then
    then_status_is(response, 200)
    assert response.json()["owner"] == public["owner"]
    assert response.json()["updated_by"]["id"] != public["owner"]["id"]
    assert response.json()["revision"] == 2


@pytest.mark.parametrize("role", ["sales", "user"])
async def test_non_admin_cannot_delete_others_public_report(api: Api, role: str) -> None:
    """Scenario: 남의 공개 리포트는 sales·user가 지울 수 없다(403 forbidden)."""
    # Given
    await given_users(api, alice="sales", bob=role)  # type: ignore[arg-type]
    await given_logged_in(api, "alice")
    public = await given_saved_report(api, "공개", visibility="public")
    await given_logged_in(api, "bob")
    # When
    response = await when_delete_report(api, public["id"])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == "리포트를 만든 사람 또는 admin만 삭제할 수 있습니다."
    await then_report_equals(api, public["id"], public)


@pytest.mark.parametrize("visibility", ["public", "private"])
async def test_owner_deletes_own_report_regardless_of_visibility(api: Api, visibility: str) -> None:
    """Scenario: 만든 사람은 공개·비공개와 무관하게 자기 리포트를 지울 수 있다(204)."""
    # Given
    await given_users(api, alice="user")
    await given_logged_in(api, "alice")
    own = await given_saved_report(api, "내 것", visibility=visibility)
    # When
    response = await when_delete_report(api, own["id"])
    # Then
    then_status_is(response, 204)
    then_listed_ids_are(await when_list_reports(api), [])


@pytest.mark.parametrize("visibility", ["public", "private"])
async def test_admin_deletes_any_report(api: Api, visibility: str) -> None:
    """Scenario: admin은 남이 만든 공개·비공개 리포트를 모두 지울 수 있다."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    others = await given_saved_report(api, "남의 것", visibility=visibility)
    await given_logged_in_as_admin(api)
    # When
    response = await when_delete_report(api, others["id"])
    # Then
    then_status_is(response, 204)
    then_report_is_not_found(await when_get_report(api, others["id"]))


async def test_non_owner_cannot_change_the_visibility(api: Api) -> None:
    """Scenario: 만든 사람이 아닌 편집자가 공개 범위를 바꾸면 403 forbidden이고 그대로다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    public = await given_saved_report(api, "공개", visibility="public")
    await given_logged_in(api, "bob")
    # When
    response = await when_update_report(
        api, public["id"], {**report_body("비공개로", visibility="private"), "revision": 1}
    )
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == "공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다."
    await then_report_equals(api, public["id"], public)


async def test_owner_can_change_the_visibility(api: Api) -> None:
    """Scenario: 만든 사람은 공개 범위를 바꿀 수 있고, 비공개가 되면 남에게는 사라진다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    public = await given_saved_report(api, "공개였음", visibility="public")
    # When
    response = await when_update_report(
        api, public["id"], {**report_body("공개였음", visibility="private"), "revision": 1}
    )
    # Then
    then_status_is(response, 200)
    await given_logged_in(api, "bob")
    then_report_is_not_found(await when_get_report(api, public["id"]))


async def test_admin_can_overwrite_others_private_report(api: Api) -> None:
    """Scenario: admin은 남의 비공개 리포트를 덮어쓸 수 있다(만든 사람은 그대로)."""
    # Given
    await given_users(api, alice="sales")
    await given_logged_in(api, "alice")
    private = await given_saved_report(api, "비공개", visibility="private")
    await given_logged_in_as_admin(api)
    # When
    response = await when_update_report(
        api, private["id"], {**report_body("admin이 고침", visibility="private"), "revision": 1}
    )
    # Then
    then_status_is(response, 200)
    assert response.json()["owner"] == private["owner"]
    assert response.json()["updated_by"]["id"] != private["owner"]["id"]


async def test_overwritten_report_shows_who_edited_it_last(api: Api) -> None:
    """Scenario: 남이 고치면 목록의 최종 수정자가 고친 사람이 되고 만든 사람은 그대로다."""
    # Given
    await given_users(api, alice="sales", bob="sales")
    await given_logged_in(api, "alice")
    public = await given_saved_report(api, "공개", visibility="public")
    await given_logged_in(api, "bob")
    await given_report_overwritten(api, public, "공개", visibility="public")
    # When
    response = await when_list_reports(api)
    # Then
    (item,) = response.json()
    assert item["owner"]["id"] == public["owner"]["id"]
    assert item["updated_by"]["id"] != item["owner"]["id"]
