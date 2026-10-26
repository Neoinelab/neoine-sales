"""GET /api/v1/deals/years(R2 AC2-1): 모든 로그인 역할, {"earliest_year": int | null}.

DB 없이 라우터·스키마를 확인하는 단위 테스트다(DB 시나리오는 functional/deals/test_deal_years.py).
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
from tests.functional.conftest import make_settings
from tests.unit.web.vendor_http import UNUSED_DATABASE_URL, client_for, problem

URL = "/api/v1/deals/years"


@pytest.mark.parametrize(("view", "expected"), [(None, None), (2019, 2019)])
def test_deal_years_response_serializes_null_and_year(
    view: int | None, expected: int | None
) -> None:
    response = DealYearsResponse.from_view(DealYearsView(earliest_year=view))

    assert response.model_dump(mode="json") == {"earliest_year": expected}


async def _register_deal(use_cases: FakeUseCases, revenue_date: date) -> None:
    from tests.factories_deal import SALES, make_create_input  # noqa: PLC0415

    owner = await use_cases.user_id_of("owner")
    await use_cases.register_deal().execute(
        make_create_input(owner_user_id=owner, revenue_date=revenue_date), SALES
    )


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_gets_null_without_deals(role: Role) -> None:
    async with client_for(FakeUseCases(), role=role) as http:
        response = await http.get(URL)

    assert response.status_code == 200, response.text
    assert response.json() == {"earliest_year": None}


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_gets_the_earliest_expected_close_year(role: Role) -> None:
    use_cases = FakeUseCases()
    from tests.fakes.catalog_seed import seed_catalog  # noqa: PLC0415

    seed_catalog(use_cases.uow)
    await use_cases.seed_user("owner", Role.SALES)  # 재직 owner는 한 명만 둔다
    for day in (date(2024, 5, 1), date(2019, 12, 31), date(2027, 1, 1)):
        await _register_deal(use_cases, day)
    async with client_for(use_cases, role=role) as http:
        response = await http.get(URL)

    assert response.status_code == 200, response.text
    assert response.json() == {"earliest_year": 2019}


async def test_the_path_is_not_taken_for_a_deal_code() -> None:
    async with client_for(FakeUseCases(), role=Role.USER) as http:
        response = await http.get(URL)

    assert response.status_code == 200  # 404(Deal 없음)이 아니다


async def test_without_login_the_years_are_unauthorized() -> None:
    async with client_for(FakeUseCases(), role=None) as http:
        response = await http.get(URL)

    problem(response, 401, "unauthenticated")


def test_openapi_documents_the_nullable_earliest_year() -> None:
    spec: dict[str, Any] = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()

    assert "get" in spec["paths"][URL]
    schema = spec["components"]["schemas"]["DealYearsResponse"]
    assert set(schema["properties"]) == {"earliest_year"}
    assert schema["required"] == ["earliest_year"]
    types = {o.get("type") for o in schema["properties"]["earliest_year"]["anyOf"]}
    assert types == {"integer", "null"}
