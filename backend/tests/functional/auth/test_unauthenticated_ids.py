"""Feature: 로그인하지 않은 요청은 id 기반 리소스에서 id가 있든 없든 401이다(존재 여부 비공개).

순차 정수 id는 추측하기 쉽다. 그래서 인증 판정이 리소스 조회보다 먼저여야 하고, 있는 id와 없는 id의
응답이 같아야 한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import ACTIONS, given_action
from tests.functional.steps.attachments import given_deal_with_files_enabled, given_file, item_url
from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is
from tests.functional.steps.deals import given_deal
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_anonymous_requests_get_401_whether_or_not_the_id_exists(api: Api) -> None:
    """Scenario: 로그아웃 상태에서 있는 첨부 id와 없는 첨부 id를 조회하면 둘 다 401이다."""
    # Given
    code = await given_deal_with_files_enabled(api)
    attachment = await given_file(api, code)
    await given_logged_out(api)
    # When
    existing = await api.get(item_url(attachment["id"]))
    missing = await api.get(item_url(MISSING_ID))
    # Then
    then_problem_is(existing, status=401, type_suffix="unauthenticated")
    then_problem_is(missing, status=401, type_suffix="unauthenticated")
    assert existing.json() == missing.json()


@pytest.mark.parametrize(
    ("method", "template"),
    [
        ("GET", "/api/v1/attachments/{}"),
        ("GET", "/api/v1/attachments/{}/download"),
        ("DELETE", "/api/v1/attachments/{}"),
        ("GET", f"{ACTIONS}/{{}}"),
        ("PUT", f"{ACTIONS}/{{}}"),
        ("DELETE", f"{ACTIONS}/{{}}"),
        ("PATCH", "/api/v1/vendors/{}"),
        ("DELETE", "/api/v1/vendors/{}"),
        ("PATCH", "/api/v1/action-types/{}"),
        ("DELETE", "/api/v1/action-types/{}"),
        ("PATCH", "/api/v1/codes/{}"),
        ("PATCH", "/api/v1/bant-labels/{}"),
        ("PUT", "/api/v1/contacts/{}"),
        ("DELETE", "/api/v1/contacts/{}"),
        ("DELETE", "/api/v1/users/{}"),
    ],
)
async def test_anonymous_requests_to_id_routes_are_401_even_for_absent_ids(
    api: Api, method: str, template: str
) -> None:
    """Scenario: 로그아웃 상태의 모든 id 경로 요청은 id가 없어도 401이다(404가 아니다)."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await api.request(
        method, template.replace("{}", str(MISSING_ID)), json={"name": "x"}
    )
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_anonymous_action_requests_do_not_reveal_which_actions_exist(api: Api) -> None:
    """Scenario: 로그아웃 상태에서 있는 Action id와 없는 Action id의 응답이 같다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    action = await given_action(api, deal["code"])
    await given_logged_out(api)
    # When
    existing = await api.get(f"{ACTIONS}/{action['id']}")
    missing = await api.get(f"{ACTIONS}/{MISSING_ID}")
    # Then
    then_problem_is(existing, status=401, type_suffix="unauthenticated")
    assert existing.json() == missing.json()
