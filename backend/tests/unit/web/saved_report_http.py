"""저장 리포트 라우터 단위 테스트 공용 도우미: FakeUseCases 위의 ASGI 클라이언트(사용자별 세션)."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.factories_auth import make_principal
from tests.functional.conftest import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from httpx import Response

    from app.domain.auth.principal import Role
    from tests.fakes.use_cases import FakeUseCases

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
URL = "/api/v1/reports"
VALID_DEFINITION: dict[str, Any] = {"columns": [{"field": "deal.code"}]}
DETAIL_KEYS = {
    "id",
    "name",
    "description",
    "visibility",
    "owner",
    "updated_by",
    "entities",
    "created_at",
    "updated_at",
    "revision",
    "definition",
    "generated_sql",
}
SUMMARY_KEYS = DETAIL_KEYS - {"revision", "definition", "generated_sql"}
NOT_FOUND_DETAIL = "리포트를 찾을 수 없습니다."


@asynccontextmanager
async def clients(
    use_cases: FakeUseCases, users: Mapping[str, Role], *, csrf: bool = True
) -> AsyncIterator[dict[str, AsyncClient]]:
    """사용자 이름 -> 그 사용자 세션을 가진 클라이언트(같은 앱·같은 Fake 저장소를 공유한다).

    이름이 "anon"이면 로그인하지 않은 클라이언트다.
    """
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    made: dict[str, AsyncClient] = {}
    try:
        for name, role in users.items():
            cookies = {}
            if name != "anon":
                cookies[SESSION_COOKIE] = await use_cases.login_as(make_principal(name, role))
            made[name] = AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers=CSRF_HEADER if csrf else {},
                cookies=cookies,
            )
        yield made
    finally:
        for client in made.values():
            await client.aclose()


def problem(response: Response, status: int, kind: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body = dict(response.json())
    assert str(body["type"]).endswith(kind), body
    return body


def create_body(name: object = "분기 Pipeline", **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    return {
        "name": name,
        "description": "",
        "visibility": "public",
        "definition": VALID_DEFINITION,
        **overrides,
    }


async def create(
    http: AsyncClient,
    name: str = "분기 Pipeline",
    **overrides: Any,  # noqa: ANN401
) -> dict[str, Any]:
    response = await http.post(URL, json=create_body(name, **overrides))
    assert response.status_code == 201, response.text
    return dict(response.json())


def update_body(revision: object = 1, name: str = "수정본", **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    return {**create_body(name), "revision": revision, **overrides}
