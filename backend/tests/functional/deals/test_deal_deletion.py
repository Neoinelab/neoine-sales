"""Feature: Deal을 삭제한다.

Owner 본인 sales 또는 admin이 deal code를 정확히 입력해야 지울 수 있다. 확인 순서는 없음(404) →
권한(403) → code 확인(422)이다. 삭제하면 이력·활동·파트너 링크·Label 연결이 함께 지워지고 연락처·
Label·코드·사용자는 남는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_user_registered
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    CODE_MISMATCH,
    DELETE_FORBIDDEN,
    NOT_FOUND,
    given_deal,
    given_label_id,
    partner_draft,
    then_deal_count_is,
    when_delete_deal,
    when_get_deal,
    when_list_history,
    when_register_deal,
)
from tests.functional.steps.users import log_in

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_the_owner_deletes_the_deal_with_the_matching_code(api: Api) -> None:
    """Scenario: Owner 본인 sales가 code를 정확히 입력하면 204이고 Deal이 사라진다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_delete_deal(api, deal["code"])
    # Then
    then_status_is(response, 204)
    then_problem_is(await when_get_deal(api, deal["code"]), status=404, type_suffix="not-found")
    await then_deal_count_is(api, 0)


async def test_history_and_links_are_deleted_but_contacts_and_labels_stay(api: Api) -> None:
    """Scenario: 삭제하면 이력이 함께 지워지고 연락처·Label은 남아 같은 값으로 다시 쓸 수 있다."""
    # Given
    await given_logged_in_as(api, role="sales")
    label = await given_label_id(api, category="budget", name="풀 예산 확보")
    bant = {"budget": label, "authority": None, "need": None, "timeline": None}
    deal = await given_deal(api, partner=partner_draft(), bant=bant)
    # When
    await when_delete_deal(api, deal["code"])
    # Then
    then_problem_is(await when_list_history(api, deal["code"]), status=404, type_suffix="not-found")
    again = await when_register_deal(api, partner=partner_draft(), bant=bant)
    then_status_is(again, 201)
    assert again.json()["customer"]["id"] == deal["customer"]["id"]  # 연락처가 남아 재사용된다
    assert again.json()["active_partner"]["id"] == deal["active_partner"]["id"]
    assert again.json()["bant"] == bant


async def test_an_admin_deletes_a_deal_of_another_owner(api: Api) -> None:
    """Scenario: admin은 다른 사람의 Deal도 지울 수 있다."""
    # Given
    sales = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_delete_deal(api, deal["code"])
    # Then
    then_status_is(response, 204)
    assert sales == "sales-user"
    await then_deal_count_is(api, 0)


async def test_another_sales_user_cannot_delete_even_with_a_wrong_code(api: Api) -> None:
    """Scenario: 다른 영업이 지우려 하면 code가 틀려도 403이 먼저이고 Deal은 남는다."""
    # Given
    await given_logged_in_as(api, role="sales", login_id="alice")
    deal = await given_deal(api)
    await given_user_registered(api, login_id="bob", role="sales")
    await log_in(api, "bob")
    # When
    wrong = await when_delete_deal(api, deal["code"], confirm_code="wrong")
    right = await when_delete_deal(api, deal["code"])
    # Then
    for response in (wrong, right):
        then_problem_is(response, status=403, type_suffix="forbidden")
        assert response.json()["detail"] == DELETE_FORBIDDEN
    await then_deal_count_is(api, 1)


async def test_a_mismatched_confirmation_is_a_422_and_nothing_is_deleted(api: Api) -> None:
    """Scenario: 확인 code가 정확히 같지 않으면 422(invalid-value)이고 Deal은 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    code = str(deal["code"])
    # When
    responses = [
        await when_delete_deal(api, code, confirm_code=typed)
        for typed in ("wrong", "20260101-9999", code[:-1], f"{code}X")
    ]
    # Then
    for response in responses:
        then_problem_is(response, status=422, type_suffix="invalid-value")
        assert response.json()["detail"] == CODE_MISMATCH
    await then_deal_count_is(api, 1)


async def test_the_confirmation_query_is_required(api: Api) -> None:
    """Scenario: confirm_code를 보내지 않으면 422(request-validation)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await api.delete(f"/api/v1/deals/{deal['code']}")
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_deal_count_is(api, 1)


async def test_an_unknown_deal_is_not_found_before_the_other_checks(api: Api) -> None:
    """Scenario: 없는 Deal은 확인 code가 틀려도 404이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    unknown = await when_delete_deal(api, "20260101-ZZZZ", confirm_code="wrong")
    malformed = await when_delete_deal(api, "not-a-code", confirm_code="wrong")
    # Then
    for response in (unknown, malformed):
        then_problem_is(response, status=404, type_suffix="not-found")
        assert response.json()["detail"] == NOT_FOUND


async def test_a_read_only_user_cannot_delete(api: Api) -> None:
    """Scenario: 조회 전용(user)은 삭제할 수 없다(403)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_logged_in_as(api, role="user")
    # When
    response = await when_delete_deal(api, deal["code"])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    await then_deal_count_is(api, 1)
