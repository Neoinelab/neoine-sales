"""Feature: 폐지된 고객·파트너 API 경로는 더 이상 없다(AC-16).

`/api/v1/customers*`, `/api/v1/partners*`는 contacts로 통합되어 사라졌다(공개 API 호환이 깨지는
결정, 사용자 승인). 로그인한 admin이 불러도 404이고 어디로도 리다이렉트하지 않는다. 구 라우터가
되살아나면 이 시나리오가 실패한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.requests import when_request

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

ID = "00000000-0000-4000-8000-000000000000"
RETIRED_ROUTES = [
    ("GET", "/api/v1/customers"),
    ("POST", "/api/v1/customers"),
    ("GET", f"/api/v1/customers/{ID}"),
    ("PUT", f"/api/v1/customers/{ID}"),
    ("DELETE", f"/api/v1/customers/{ID}"),
    ("GET", "/api/v1/partners"),
    ("POST", "/api/v1/partners"),
    ("GET", f"/api/v1/partners/{ID}"),
    ("PUT", f"/api/v1/partners/{ID}"),
    ("DELETE", f"/api/v1/partners/{ID}"),
]


@pytest.mark.parametrize(
    ("method", "path"),
    RETIRED_ROUTES,
    ids=[f"{method} {path.replace(ID, '{id}')}" for method, path in RETIRED_ROUTES],
)
async def test_retired_customer_and_partner_routes_do_not_exist(
    api: Api, method: str, path: str
) -> None:
    """Scenario: 고객·파트너 경로는 admin이 불러도 404이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_request(api, method, path, json={} if method in {"POST", "PUT"} else None)
    # Then
    then_status_is(response, 404)
    assert "location" not in response.headers
