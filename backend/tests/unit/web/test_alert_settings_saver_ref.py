"""경고 기준 응답의 저장자(P3 R1 리뷰 Minor): updated_by를 그대로 UserRef로 바꾼다.

응답을 만들 때 사용자 참조를 다시 조회하지 않는다. 다시 조회하면 조회 시점이 저장 트랜잭션과
달라지고 요청마다 읽기가 늘어난다. 참조 조회 유스케이스가 호출되면 실패하는 구성으로 고정한다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.user.resolve_user_refs import ResolveUserRefs

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
URL = "/api/v1/alert-settings"


class _NoRefLookupUseCases(FakeUseCases):
    """사용자 참조 일괄 조회를 부르면 실패하는 유스케이스 묶음."""

    def resolve_user_refs(self) -> ResolveUserRefs:
        raise AssertionError("경고 기준 응답은 사용자 참조를 다시 조회하지 않아야 합니다")


@asynccontextmanager
async def _admin_client() -> AsyncIterator[AsyncClient]:
    use_cases = _NoRefLookupUseCases()
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookie = await use_cases.login_as(make_principal("root", Role.ADMIN))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies={SESSION_COOKIE: cookie},
    ) as http:
        yield http


async def test_put_response_has_the_saver_reference_without_a_second_lookup() -> None:
    async with _admin_client() as http:
        response = await http.put(URL, json={"stale_days": 21})
        me = (await http.get("/api/v1/auth/me")).json()

    assert response.status_code == 200, response.text
    saver = response.json()["updated_by"]
    assert saver["id"] == me["user_id"]
    assert (saver["resigned"], saver["role"]) == (False, "admin")
    assert saver["label"] == saver["name"]


async def test_get_response_has_the_saver_reference_without_a_second_lookup() -> None:
    async with _admin_client() as http:
        await http.put(URL, json={"stale_days": 21})
        response = await http.get(URL)
        me = (await http.get("/api/v1/auth/me")).json()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stale_days"] == 21
    assert body["updated_by"]["id"] == me["user_id"]


async def test_get_before_any_save_needs_no_lookup_either() -> None:
    async with _admin_client() as http:
        response = await http.get(URL)

    assert response.status_code == 200, response.text
    assert response.json() == {"stale_days": 14, "updated_at": None, "updated_by": None}
