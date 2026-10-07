"""공통 동작: 헬스체크, 문서 노출, CORS, 오류 형식, 도메인 오류 매핑."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.common.errors import DomainError, InvalidStateError
from app.main import create_app
from tests.e2e.conftest import ALLOWED_ORIGIN, make_settings
from tests.fakes.use_cases import FakeUseCases

PROBLEM = "application/problem+json"


async def test_liveness_is_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_is_ok_when_dependencies_are_up(client: AsyncClient) -> None:
    response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readiness_is_503_without_leaking_the_cause(
    client: AsyncClient, use_cases: FakeUseCases
) -> None:
    use_cases.ready_error = ConnectionRefusedError("postgresql://user:secret@db:5432/x")

    response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["type"].endswith("not-ready")
    assert "secret" not in response.text
    assert "postgresql" not in response.text


async def test_docs_are_served_when_enabled(client: AsyncClient) -> None:
    assert (await client.get("/docs")).status_code == 200
    assert (await client.get("/openapi.json")).status_code == 200


async def test_docs_are_hidden_when_disabled() -> None:
    app = create_app(settings=make_settings(enable_docs=False), use_cases=FakeUseCases())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        assert (await http.get("/docs")).status_code == 404
        assert (await http.get("/redoc")).status_code == 404
        assert (await http.get("/openapi.json")).status_code == 404
        assert (await http.get("/healthz")).status_code == 200


async def test_cors_allows_the_configured_origin(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/customers",
        headers={"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


async def test_cors_does_not_allow_other_origins(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/customers",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in response.headers


async def test_unknown_route_is_a_404_problem(client: AsyncClient) -> None:
    response = await client.get("/api/v1/nothing-here")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["status"] == 404


async def test_wrong_method_is_a_405_problem(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/customers")

    assert response.status_code == 405
    assert response.headers["content-type"].startswith(PROBLEM)


async def test_problem_documents_carry_the_request_path(client: AsyncClient) -> None:
    response = await client.get("/api/v1/customers/00000000-0000-0000-0000-000000000000")

    assert response.json()["instance"] == "/api/v1/customers/00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize(
    ("error", "status", "type_suffix"),
    [
        (InvalidStateError("삭제된 항목은 수정할 수 없습니다"), 409, "invalid-state"),
        (DomainError("알 수 없는 도메인 오류"), 400, "domain-error"),
    ],
)
async def test_other_domain_errors_are_mapped(
    client: AsyncClient,
    use_cases: FakeUseCases,
    error: DomainError,
    status: int,
    type_suffix: str,
) -> None:
    class Failing:
        async def execute(self, *_: object, **__: object) -> None:
            raise error

    use_cases.list_customers = Failing  # type: ignore[method-assign, assignment]

    response = await client.get("/api/v1/customers")

    assert response.status_code == status
    assert response.json()["type"].endswith(type_suffix)
    assert response.json()["detail"] == str(error)
