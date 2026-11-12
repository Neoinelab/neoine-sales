"""GET /api/v1/deals의 쿼리 파라미터 계약: 폐지된 bant_* 와 새 overdue·stale·sort 값.

DB 없이 라우터·스키마·오류 매핑을 FakeUseCases 위에서 본다.
BDD 케이스의 HTTP 수준 검증은 `web/test_deal_list_http_cases.py`가, 조회 동작은
`application/test_deal_list_*_cases.py`가 맡는다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
URL = "/api/v1/deals"


@asynccontextmanager
async def _client() -> AsyncIterator[AsyncClient]:
    from tests.fakes.catalog_seed import seed_catalog  # noqa: PLC0415

    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookie = await use_cases.login_as(make_principal("root", Role.ADMIN))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies={SESSION_COOKIE: cookie},
    ) as http:
        yield http


@pytest.mark.parametrize("param", ["bant_budget", "bant_authority", "bant_need", "bant_timeline"])
async def test_listing_with_a_bant_parameter_is_request_validation(param: str) -> None:
    """목록에 BANT 파라미터를 보내면 request-validation 오류다."""
    # given: 카탈로그가 시드된 앱
    async with _client() as http:
        # when: bant 파라미터를 보내 조회한다
        response = await http.get(URL, params={param: 1})

    # then: 422 request-validation이다
    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


@pytest.mark.parametrize(
    "params", [{"overdue": "true"}, {"stale": "1"}, {"overdue": "true", "stale": "true"}]
)
async def test_listing_with_the_risk_filters_is_accepted(params: dict[str, str]) -> None:
    """경고 필터(overdue·stale)는 받아들이고 0건을 돌려준다."""
    # given: 카탈로그가 시드된 앱
    async with _client() as http:
        # when: 경고 필터를 보내 조회한다
        response = await http.get(URL, params=params)

    # then: 200이고 total은 0이다
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0


@pytest.mark.parametrize("param", ["overdue", "stale"])
async def test_listing_with_a_non_boolean_risk_filter_is_request_validation(param: str) -> None:
    """경고 필터에 불리언이 아닌 값을 보내면 request-validation 오류다."""
    # given: 카탈로그가 시드된 앱
    async with _client() as http:
        # when: overdue·stale에 abc를 보내 조회한다
        response = await http.get(URL, params={param: "abc"})

    # then: 422 request-validation이다
    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")


@pytest.mark.parametrize("sort", ["owner", "customer", "partner", "vendor", "forecast"])
async def test_listing_accepts_each_new_sort_value(sort: str) -> None:
    """새 정렬 값(owner·customer·partner·vendor·forecast)을 받아들인다."""
    # given: 카탈로그가 시드된 앱
    async with _client() as http:
        # when: 정렬 값을 내림차순으로 보내 조회한다
        response = await http.get(URL, params={"sort": sort, "order": "desc"})

    # then: 200이다
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("sort", ["forecastKey", "bant", "next_action", "risk"])
async def test_listing_rejects_a_sort_outside_the_list(sort: str) -> None:
    """목록에 없는 정렬 값은 request-validation 오류다."""
    # given: 카탈로그가 시드된 앱
    async with _client() as http:
        # when: 허용되지 않은 정렬 값으로 조회한다
        response = await http.get(URL, params={"sort": sort})

    # then: 422 request-validation이다
    assert response.status_code == 422, response.text
    assert str(response.json()["type"]).endswith("request-validation")
