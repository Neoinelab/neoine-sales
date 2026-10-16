"""Feature: 모든 사용자는 BANT Label을 보고, sales·admin은 새 Label을 만들 수 있다.

Label은 Budget·Authority·Need·Timeline 구분별 선택지이고 점수가 없다. 기본 Label 23개는
마이그레이션이 넣는다. 이름 변경·삭제는 `test_bant_label_changes.py`.
"""

from typing import TYPE_CHECKING

import pytest

from tests.fakes.catalog_seed import DEFAULT_LABELS
from tests.functional.steps.auth import RoleName, given_logged_in_as, given_logged_out
from tests.functional.steps.common import (
    then_body_includes,
    then_problem_is,
    then_status_is,
)
from tests.functional.steps.labels import (
    given_current_user_id,
    given_label_created,
    given_labels_created,
    then_every_label_has_the_documented_fields,
    then_label_count_is,
    then_label_creator_is,
    then_label_names_are,
    then_labels_are_the_defaults,
    then_location_points_to_the_created,
    when_create_label,
    when_delete_user_account,
    when_list_labels,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

DUPLICATE_MESSAGE = "같은 구분에 이미 있는 Label 이름입니다."
BLANK_MESSAGE = "Label 이름을 입력하세요."
TOO_LONG_MESSAGE = "Label 이름은 50자 이내로 입력하세요."


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_role_sees_the_23_default_labels_in_order(api: Api, role: RoleName) -> None:
    """Scenario: 어떤 역할이든 기본 Label 23개를 구분·시드 순서대로 본다(AC-10)."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await when_list_labels(api)
    # Then
    then_status_is(response, 200)
    then_labels_are_the_defaults(response)
    then_every_label_has_the_documented_fields(response)
    assert [len(DEFAULT_LABELS[c]) for c in DEFAULT_LABELS] == [7, 6, 5, 5]


async def test_anonymous_user_cannot_list_labels(api: Api) -> None:
    """Scenario: 로그인하지 않으면 Label 목록이 401이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_list_labels(api)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_sales_creates_a_label_and_is_recorded_as_its_creator(api: Api) -> None:
    """Scenario: sales가 Label을 만들면 201이고 만든 사람과 직접 만든 표시가 남는다(AC-11)."""
    # Given
    await given_logged_in_as(api, role="sales")
    sales_id = await given_current_user_id(api)
    # When
    response = await when_create_label(api, category="need", name="  규제 대응  ")
    # Then
    then_status_is(response, 201)
    then_location_points_to_the_created(response)
    then_body_includes(response, category="need", name="규제 대응", is_default=False, usage_count=0)
    assert response.json()["created_by"]["id"] == sales_id


async def test_admin_creates_a_label_and_is_recorded_as_its_creator(api: Api) -> None:
    """Scenario: admin도 Label을 만들 수 있다(AC-11)."""
    # Given
    await given_logged_in_as(api, role="admin")
    admin_id = await given_current_user_id(api)
    # When
    response = await when_create_label(api, category="timeline", name="분기 내 구매")
    # Then
    then_status_is(response, 201)
    assert response.json()["created_by"]["id"] == admin_id


async def test_user_role_cannot_create_a_label(api: Api) -> None:
    """Scenario: user(읽기 전용)는 Label을 만들 수 없고 403이다(AC-11)."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_create_label(api, category="need", name="규제 대응")
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_label_count_is(api, count=23)


async def test_anonymous_user_cannot_create_a_label(api: Api) -> None:
    """Scenario: 로그인하지 않으면 Label 생성이 401이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_logged_out(api)
    # When
    response = await when_create_label(api, category="need", name="규제 대응")
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_created_labels_are_listed_after_the_defaults_sorted_by_name(api: Api) -> None:
    """Scenario: 직접 만든 Label은 기본 Label 뒤에 이름순(대소문자 무시)으로 보인다(AC-10)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_labels_created(api, category="need", names=["나중에", "Zeta", "alpha"])
    # When
    response = await when_list_labels(api)
    # Then
    then_status_is(response, 200)
    need = [x["name"] for x in response.json() if x["category"] == "need"]
    assert need == [*DEFAULT_LABELS["need"], "alpha", "Zeta", "나중에"]


@pytest.mark.parametrize("name", ["", "   "], ids=["empty", "blank"])
async def test_creating_a_label_without_a_name_is_rejected(api: Api, name: str) -> None:
    """Scenario: 이름이 비어 있으면 422 "Label 이름을 입력하세요."다(AC-12)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_create_label(api, category="need", name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == BLANK_MESSAGE
    await then_label_count_is(api, count=23)


async def test_creating_a_label_with_a_name_over_50_characters_is_rejected(api: Api) -> None:
    """Scenario: 이름이 51자이면 422 "Label 이름은 50자 이내로 입력하세요."다(경계, AC-12)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_create_label(api, category="need", name="😀" * 51)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == TOO_LONG_MESSAGE
    await then_label_count_is(api, count=23)


async def test_label_name_of_50_code_points_is_accepted(api: Api) -> None:
    """Scenario: 이모지 50개(코드 포인트 50자)는 허용된다(경계, AC-12)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_create_label(api, category="need", name="😀" * 50)
    # Then
    then_status_is(response, 201)
    then_body_includes(response, name="😀" * 50)


async def test_creating_a_label_with_an_unknown_category_is_rejected(api: Api) -> None:
    """Scenario: 알 수 없는 구분이면 요청 형식 오류 422다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_create_label(api, category="money", name="규제 대응")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_label_count_is(api, count=23)


@pytest.mark.parametrize("name", ["CEO 보고 완료", "ceo 보고 완료", " Ceo 보고 완료 "])
async def test_creating_a_label_with_an_existing_name_in_the_category_conflicts(
    api: Api, name: str
) -> None:
    """Scenario: 같은 구분에 대소문자만 다른 이름을 만들면 409다(AC-12)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_create_label(api, category="authority", name=name)
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    assert response.json()["detail"] == DUPLICATE_MESSAGE
    await then_label_count_is(api, count=23)


async def test_creating_a_label_named_like_one_in_another_category_is_allowed(api: Api) -> None:
    """Scenario: 다른 구분의 같은 이름은 허용된다(Budget에는 "모름"이 없다, AC-12)."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_create_label(api, category="budget", name="모름")
    # Then
    then_status_is(response, 201)
    await then_label_names_are(api, category="budget", names=[*DEFAULT_LABELS["budget"], "모름"])


async def test_deleting_a_user_who_created_a_label_resigns_the_user(api: Api) -> None:
    """Scenario: Label을 만든 사용자를 삭제하면 지우지 않고 퇴사 처리된다(AC-15)."""
    # Given
    await given_logged_in_as(api, role="sales")
    sales_id = await given_current_user_id(api)
    await given_label_created(api, category="need", name="규제 대응")
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_user_account(api, user_id=sales_id)
    # Then
    then_status_is(response, 200)
    assert response.json() == {"outcome": "resigned"}
    await then_label_creator_is(api, name="규제 대응", user_id=sales_id, resigned=True)
