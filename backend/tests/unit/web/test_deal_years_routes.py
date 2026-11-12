"""GET /api/v1/deals/years(R2 AC2-1): 모든 로그인 역할, {"earliest_year": int | null}.

DB 없이 라우터·스키마를 확인하는 단위 테스트다(조회 규칙은 DL-049·050을 구현한
`application/test_deal_list_period_sort_cases.py`와 `application/test_get_deal_years.py`).
라우트는 /{code}보다 먼저 등록되어야 한다.
"""

from datetime import date
from typing import Any

import pytest

from app.application.deal.deal_years import DealYearsView
from app.domain.auth.principal import Role
from app.main import create_app
from app.web.schemas.deal_years import DealYearsResponse
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings
from tests.unit.web.vendor_http import UNUSED_DATABASE_URL, client_for, problem

URL = "/api/v1/deals/years"


@pytest.mark.parametrize(("view", "expected"), [(None, None), (2019, 2019)])
def test_deal_years_response_serializes_null_and_year(
    view: int | None, expected: int | None
) -> None:
    """연도 응답은 null과 연도를 JSON으로 직렬화한다."""
    # when: 연도 뷰를 응답으로 바꿔 직렬화한다
    response = DealYearsResponse.from_view(DealYearsView(earliest_year=view))

    # then: earliest_year가 그대로 나온다
    assert response.model_dump(mode="json") == {"earliest_year": expected}


async def _register_deal(use_cases: FakeUseCases, revenue_date: date) -> None:
    from tests.factories_deal import SALES, make_create_input  # noqa: PLC0415

    owner = await use_cases.user_id_of("owner")
    await use_cases.register_deal().execute(
        make_create_input(owner_user_id=owner, revenue_date=revenue_date), SALES
    )


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_gets_null_without_deals(role: Role) -> None:
    """Deal이 없으면 모든 역할이 null을 받는다."""
    # given: Deal이 없는 앱
    async with client_for(FakeUseCases(), role=role) as http:
        # when: 연도 API를 조회한다
        response = await http.get(URL)

    # then: 200이고 earliest_year는 null이다
    assert response.status_code == 200, response.text
    assert response.json() == {"earliest_year": None}


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_gets_the_earliest_expected_close_year(role: Role) -> None:
    """모든 역할이 가장 이른 Expected Close 연도를 받는다."""
    # given: Expected Close가 2024·2019·2027년인 Deal 세 건
    use_cases = FakeUseCases()
    from tests.fakes.catalog_seed import seed_catalog  # noqa: PLC0415

    seed_catalog(use_cases.uow)
    await use_cases.seed_user("owner", Role.SALES)  # 재직 owner는 한 명만 둔다
    for day in (date(2024, 5, 1), date(2019, 12, 31), date(2027, 1, 1)):
        await _register_deal(use_cases, day)
    async with client_for(use_cases, role=role) as http:
        # when: 연도 API를 조회한다
        response = await http.get(URL)

    # then: 200이고 가장 이른 2019다
    assert response.status_code == 200, response.text
    assert response.json() == {"earliest_year": 2019}


async def test_the_path_is_not_taken_for_a_deal_code() -> None:
    """/deals/years 경로는 Deal 코드로 해석되지 않는다."""
    # given: Deal이 없는 앱
    async with client_for(FakeUseCases(), role=Role.USER) as http:
        # when: 연도 API를 조회한다
        response = await http.get(URL)

    # then: 404가 아니라 200이다
    assert response.status_code == 200  # 404(Deal 없음)이 아니다


async def test_without_login_the_years_are_unauthorized() -> None:
    """로그인하지 않으면 연도 API는 401이다."""
    # given: 로그인하지 않은 클라이언트
    async with client_for(FakeUseCases(), role=None) as http:
        # when: 연도 API를 조회한다
        response = await http.get(URL)

    # then: 401 unauthenticated다
    problem(response, 401, "unauthenticated")


def test_openapi_documents_the_nullable_earliest_year() -> None:
    """OpenAPI가 null 가능한 earliest_year 응답을 문서화한다."""
    # when: OpenAPI 문서를 만든다
    spec: dict[str, Any] = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()

    # then: GET 경로와 정수·null 스키마가 있다
    assert "get" in spec["paths"][URL]
    schema = spec["components"]["schemas"]["DealYearsResponse"]
    assert set(schema["properties"]) == {"earliest_year"}
    assert schema["required"] == ["earliest_year"]
    types = {o.get("type") for o in schema["properties"]["earliest_year"]["anyOf"]}
    assert types == {"integer", "null"}
