"""Feature: admin만 BANT Label의 이름을 바꾸거나 삭제할 수 있다.

기본 Label도 이름 변경·삭제 대상이다. sales·user는 403, 로그인하지 않으면 401이다.
"사용 중인 Label은 삭제할 수 없다"(AC-14)는 P0에 Deal 연결이 없어 application 단위 테스트(Fake)로
검증하고, 실제 DB 집계는 P1 테스트에서 다룬다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.fakes.catalog_seed import DEFAULT_LABELS
from tests.functional.steps.auth import RoleName, given_logged_in_as, given_logged_out
from tests.functional.steps.codes import unknown_id
from tests.functional.steps.common import (
    then_body_includes,
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.labels import (
    given_label_created,
    given_label_id,
    then_label_count_is,
    then_label_exists,
    then_label_is_gone,
    then_label_names_are,
    when_delete_label,
    when_rename_label,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

DUPLICATE_MESSAGE = "같은 구분에 이미 있는 Label 이름입니다."
NON_ADMIN = ["sales", "user"]


# --- 이름 변경 (AC-12·13) ---


async def test_admin_renames_a_default_label(api: Api) -> None:
    """Scenario: admin이 기본 Label 이름을 바꾸면 같은 자리에 새 이름이 보인다(AC-13)."""
    # Given
    await given_logged_in_as(api, role="admin")
    label_id = await given_label_id(api, category="budget", name="예산 없음")
    # When
    response = await when_rename_label(api, label_id=label_id, name="  예산 미확보  ")
    # Then
    then_status_is(response, 200)
    then_body_includes(
        response, id=label_id, category="budget", name="예산 미확보", is_default=True
    )
    expected = ["예산 미확보" if n == "예산 없음" else n for n in DEFAULT_LABELS["budget"]]
    await then_label_names_are(api, category="budget", names=expected)


async def test_admin_renames_a_label_made_by_someone_else(api: Api) -> None:
    """Scenario: 다른 사람이 만든 Label도 admin은 이름을 바꿀 수 있고 만든 사람은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    created = await given_label_created(api, category="need", name="규제 대응")
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_rename_label(api, label_id=created["id"], name="컴플라이언스 대응")
    # Then
    then_status_is(response, 200)
    then_body_includes(response, name="컴플라이언스 대응", is_default=False)
    assert response.json()["created_by"] == created["created_by"]


async def test_renaming_a_label_to_another_labels_name_ignoring_case_conflicts(api: Api) -> None:
    """Scenario: 같은 구분의 다른 Label과 같은 이름으로 바꾸면 409다(AC-12)."""
    # Given
    await given_logged_in_as(api, role="admin")
    label_id = await given_label_id(api, category="authority", name="CISO 보고 완료")
    # When
    response = await when_rename_label(api, label_id=label_id, name="ceo 보고 완료")
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == DUPLICATE_MESSAGE
    await then_label_exists(api, category="authority", name="CISO 보고 완료")


async def test_renaming_a_label_to_its_own_name_in_another_case_is_allowed(api: Api) -> None:
    """Scenario: 자기 이름의 대소문자만 바꾸는 것은 중복이 아니다(AC-12)."""
    # Given
    await given_logged_in_as(api, role="admin")
    label_id = await given_label_id(api, category="authority", name="CEO 보고 완료")
    # When
    response = await when_rename_label(api, label_id=label_id, name="ceo 보고 완료")
    # Then
    then_status_is(response, 200)
    then_body_includes(response, name="ceo 보고 완료")


async def test_renaming_a_label_to_a_name_of_another_category_is_allowed(api: Api) -> None:
    """Scenario: 다른 구분에 있는 이름으로는 바꿀 수 있다(AC-12). Budget에는 "모름"이 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    label_id = await given_label_id(api, category="budget", name="미확인")
    # When
    response = await when_rename_label(api, label_id=label_id, name="모름")
    # Then
    then_status_is(response, 200)
    then_body_includes(response, category="budget", name="모름")


@pytest.mark.parametrize(
    ("name", "detail"),
    [
        ("   ", "Label 이름을 입력하세요."),
        ("가" * 51, "Label 이름은 50자 이내로 입력하세요."),
    ],
    ids=["blank", "51-chars"],
)
async def test_renaming_a_label_with_an_invalid_name_is_rejected(
    api: Api, name: str, detail: str
) -> None:
    """Scenario: 빈 이름이나 51자 이름으로 바꾸면 422이고 이름은 그대로다(AC-12)."""
    # Given
    await given_logged_in_as(api, role="admin")
    label_id = await given_label_id(api, category="budget", name="예산 없음")
    # When
    response = await when_rename_label(api, label_id=label_id, name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == detail
    await then_label_exists(api, category="budget", name="예산 없음")


async def test_renaming_a_missing_label_is_not_found(api: Api) -> None:
    """Scenario: 없는 Label의 이름을 바꾸면 404다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_rename_label(api, label_id=unknown_id(), name="아무거나")
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


# --- 삭제 (AC-13) ---


async def test_admin_deletes_an_unused_default_label(api: Api) -> None:
    """Scenario: admin이 쓰이지 않는 기본 Label을 삭제하면 204로 목록에서 사라진다(AC-13)."""
    # Given
    await given_logged_in_as(api, role="admin")
    label_id = await given_label_id(api, category="budget", name="예산 없음")
    # When
    response = await when_delete_label(api, label_id=label_id)
    # Then
    then_status_is(response, 204)
    await then_label_is_gone(api, category="budget", name="예산 없음")
    await then_label_count_is(api, count=22)


async def test_admin_deletes_a_label_made_by_someone_else(api: Api) -> None:
    """Scenario: 다른 사람이 만든 Label도 admin은 삭제할 수 있다."""
    # Given
    await given_logged_in_as(api, role="sales")
    created = await given_label_created(api, category="need", name="규제 대응")
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_label(api, label_id=created["id"])
    # Then
    then_status_is(response, 204)
    await then_label_count_is(api, count=23)


async def test_deleting_a_missing_label_is_not_found(api: Api) -> None:
    """Scenario: 없는 Label을 삭제하면 404다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_label(api, label_id=unknown_id())
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


# --- 권한 (AC-13) ---


@pytest.mark.parametrize("role", NON_ADMIN)
async def test_non_admin_cannot_rename_a_label(api: Api, role: RoleName) -> None:
    """Scenario: sales·user는 Label 이름을 바꿀 수 없고 403이다(AC-13)."""
    # Given
    await given_logged_in_as(api, role=role)
    label_id = await given_label_id(api, category="budget", name="예산 없음")
    # When
    response = await when_rename_label(api, label_id=label_id, name="예산 미확보")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_label_exists(api, category="budget", name="예산 없음")


@pytest.mark.parametrize("role", NON_ADMIN)
async def test_non_admin_cannot_delete_a_label(api: Api, role: RoleName) -> None:
    """Scenario: sales·user는 Label을 삭제할 수 없고 403이다(AC-13)."""
    # Given
    await given_logged_in_as(api, role=role)
    label_id = await given_label_id(api, category="budget", name="예산 없음")
    # When
    response = await when_delete_label(api, label_id=label_id)
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_label_exists(api, category="budget", name="예산 없음")


async def test_sales_cannot_delete_the_label_they_created(api: Api) -> None:
    """Scenario: sales는 자기가 만든 Label도 삭제할 수 없다(생성만 허용, AC-13)."""
    # Given
    await given_logged_in_as(api, role="sales")
    created = await given_label_created(api, category="need", name="규제 대응")
    # When
    response = await when_delete_label(api, label_id=created["id"])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_label_exists(api, category="need", name="규제 대응")


async def test_anonymous_user_cannot_rename_a_label(api: Api) -> None:
    """Scenario: 로그인하지 않으면 Label 이름 변경이 401이다(403보다 먼저)."""
    # Given
    await given_logged_in_as(api, role="admin")
    label_id = await given_label_id(api, category="budget", name="예산 없음")
    await given_logged_out(api)
    # When
    response = await when_rename_label(api, label_id=label_id, name="예산 미확보")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_anonymous_user_cannot_delete_a_label(api: Api) -> None:
    """Scenario: 로그인하지 않으면 Label 삭제가 401이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    label_id = await given_label_id(api, category="budget", name="예산 없음")
    await given_logged_out(api)
    # When
    response = await when_delete_label(api, label_id=label_id)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")
