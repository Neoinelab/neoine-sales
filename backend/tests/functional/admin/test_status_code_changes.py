"""Feature: admin은 Status 코드의 이름·순서를 바꾸고 쓰지 않는 코드만 지울 수 있다.

잠긴 Status는 기회발굴(prospecting)·계약완료(contract_completed) 둘이다. 잠긴 코드도 이름과
순서는 바꿀 수 있고, 내부 key는 바뀌지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.fakes.catalog_seed import DEFAULT_STATUSES
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.codes import (
    BLANK_MESSAGE,
    DUPLICATE_MESSAGE,
    LOCKED_MESSAGE,
    REORDER_MESSAGE,
    given_code_id,
    given_code_ids,
    given_deal_in_status,
    in_use_message,
    then_code_count_is,
    then_code_exists,
    then_code_is_gone,
    then_code_name_is,
    then_detail_is,
    then_kind_order_is,
    unknown_id,
    when_delete_code,
    when_rename_code,
    when_reorder_codes,
)
from tests.functional.steps.common import then_body_includes, then_problem_is, then_status_is

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

STATUS_KEYS = [key for key, _ in DEFAULT_STATUSES]


# --- 이름 변경 (AC-05) ---


async def test_admin_renames_a_locked_status_code_and_its_key_stays(api: Api) -> None:
    """Scenario: 잠긴 계약완료도 이름을 바꿀 수 있고 key와 잠금은 그대로다(AC-05)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="contract_completed")
    # When
    response = await when_rename_code(api, code_id=code_id, name="수주 완료")
    # Then
    then_status_is(response, 200)
    then_body_includes(
        response, id=code_id, key="contract_completed", name="수주 완료", locked=True, order=7
    )
    await then_code_name_is(api, kind="status", key="contract_completed", name="수주 완료")


async def test_admin_renames_an_unlocked_status_code(api: Api) -> None:
    """Scenario: 일반 Status의 이름을 바꾸면 목록에 새 이름이 보인다(AC-05)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="introduction")
    # When
    response = await when_rename_code(api, code_id=code_id, name="  소개  ")
    # Then
    then_status_is(response, 200)
    then_body_includes(response, key="introduction", name="소개", locked=False)
    await then_code_name_is(api, kind="status", key="introduction", name="소개")


async def test_renaming_a_status_code_to_another_codes_name_conflicts(api: Api) -> None:
    """Scenario: 같은 종류의 다른 코드와 같은 이름으로 바꾸면 409다(AC-04)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="introduction")
    # When
    response = await when_rename_code(api, code_id=code_id, name="기회발굴")
    # Then
    then_problem_is(response, status=409, type_suffix="already-exists")
    then_detail_is(response, DUPLICATE_MESSAGE)
    await then_code_name_is(api, kind="status", key="introduction", name="제품소개")


async def test_renaming_a_status_code_to_its_own_name_in_another_case_is_allowed(api: Api) -> None:
    """Scenario: 자기 자신과만 겹치는 이름(대소문자만 변경)은 허용된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="poc_completed")
    # When
    response = await when_rename_code(api, code_id=code_id, name="poc완료")
    # Then
    then_status_is(response, 200)
    then_body_includes(response, key="poc_completed", name="poc완료")


async def test_renaming_a_status_code_to_a_blank_name_is_rejected(api: Api) -> None:
    """Scenario: 빈 이름으로 바꾸면 422이고 이름은 그대로다(AC-04)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="introduction")
    # When
    response = await when_rename_code(api, code_id=code_id, name="   ")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, BLANK_MESSAGE)
    await then_code_name_is(api, kind="status", key="introduction", name="제품소개")


async def test_renaming_a_status_code_to_a_name_over_50_characters_is_rejected(api: Api) -> None:
    """Scenario: 51자 이름으로 바꾸면 422다(경계)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="introduction")
    # When
    response = await when_rename_code(api, code_id=code_id, name="가" * 51)
    # Then
    then_status_is(response, 422)
    await then_code_name_is(api, kind="status", key="introduction", name="제품소개")


async def test_renaming_a_missing_code_is_not_found(api: Api) -> None:
    """Scenario: 없는 코드의 이름을 바꾸면 404다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_rename_code(api, code_id=unknown_id(), name="아무거나")
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")


# --- 순서 변경 (AC-06) ---


async def test_admin_reorders_status_codes_and_orders_restart_from_one(api: Api) -> None:
    """Scenario: 전체 id 목록으로 순서를 바꾸면 order가 1부터 다시 매겨진다(AC-06)."""
    # Given
    await given_logged_in_as(api, role="admin")
    ids = await given_code_ids(api, kind="status")
    # When
    response = await when_reorder_codes(api, kind="status", ordered_ids=list(reversed(ids)))
    # Then
    then_status_is(response, 200)
    assert [c["id"] for c in response.json()] == list(reversed(ids))
    assert [c["order"] for c in response.json()] == [1, 2, 3, 4, 5, 6, 7]
    await then_kind_order_is(api, kind="status", keys=list(reversed(STATUS_KEYS)))


async def test_reordering_with_a_missing_id_is_rejected_and_keeps_the_order(api: Api) -> None:
    """Scenario: 목록에서 id가 빠지면 422 "순서 목록이 올바르지 않습니다."다(AC-06)."""
    # Given
    await given_logged_in_as(api, role="admin")
    ids = await given_code_ids(api, kind="status")
    # When
    response = await when_reorder_codes(api, kind="status", ordered_ids=ids[:-1])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, REORDER_MESSAGE)
    await then_kind_order_is(api, kind="status", keys=STATUS_KEYS)


async def test_reordering_with_a_duplicate_id_is_rejected(api: Api) -> None:
    """Scenario: 같은 id가 두 번 있으면 422다(AC-06)."""
    # Given
    await given_logged_in_as(api, role="admin")
    ids = await given_code_ids(api, kind="status")
    # When
    response = await when_reorder_codes(api, kind="status", ordered_ids=[*ids[:-1], ids[0]])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, REORDER_MESSAGE)
    await then_kind_order_is(api, kind="status", keys=STATUS_KEYS)


async def test_reordering_with_an_id_of_the_other_kind_is_rejected(api: Api) -> None:
    """Scenario: 다른 종류(Forecast)의 id가 섞이면 422다(AC-06)."""
    # Given
    await given_logged_in_as(api, role="admin")
    ids = await given_code_ids(api, kind="status")
    foreign = (await given_code_ids(api, kind="forecast"))[0]
    # When
    response = await when_reorder_codes(api, kind="status", ordered_ids=[*ids[:-1], foreign])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_detail_is(response, REORDER_MESSAGE)
    await then_kind_order_is(api, kind="status", keys=STATUS_KEYS)


# --- 삭제 (AC-07·08) ---


@pytest.mark.parametrize("key", ["prospecting", "contract_completed"])
async def test_admin_cannot_delete_a_locked_status_code_even_without_deals(
    api: Api, key: str
) -> None:
    """Scenario: 참조가 없어도 잠긴 Status는 삭제할 수 없다(409, AC-07)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key=key)
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, LOCKED_MESSAGE)
    await then_code_exists(api, kind="status", key=key)


async def test_admin_deletes_an_unused_status_code(api: Api) -> None:
    """Scenario: 쓰이지 않고 잠기지 않은 Status는 삭제된다(204, AC-08)."""
    # Given
    await given_logged_in_as(api, role="admin")
    code_id = await given_code_id(api, kind="status", key="poc_completed")
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_status_is(response, 204)
    await then_code_is_gone(api, kind="status", key="poc_completed")
    await then_code_count_is(api, kind="status", count=6)


async def test_admin_cannot_delete_a_status_code_used_by_deals(api: Api) -> None:
    """Scenario: Deal이 쓰는 Status는 삭제할 수 없고 문구에 건수가 들어간다(409, AC-08)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_deal_in_status(api, status_key="poc_preparation", number=1)
    await given_deal_in_status(api, status_key="poc_preparation", number=2)
    code_id = await given_code_id(api, kind="status", key="poc_preparation")
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    then_detail_is(response, in_use_message(2))
    await then_code_exists(api, kind="status", key="poc_preparation")


async def test_deleting_a_status_code_ignores_deals_in_other_statuses(api: Api) -> None:
    """Scenario: 다른 Status를 쓰는 Deal은 삭제를 막지 않는다(AC-08)."""
    # Given
    await given_logged_in_as(api, role="admin")
    await given_deal_in_status(api, status_key="introduction", number=1)
    code_id = await given_code_id(api, kind="status", key="poc_completed")
    # When
    response = await when_delete_code(api, code_id=code_id)
    # Then
    then_status_is(response, 204)


async def test_deleting_a_missing_code_is_not_found(api: Api) -> None:
    """Scenario: 없는 코드를 삭제하면 404다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_code(api, code_id=unknown_id())
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
