"""경고 기준 응답의 저장자: updated_by를 그대로 UserRef로 바꾼다.

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
from tests.support.app_settings import CSRF_HEADER, make_settings

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
    """경고 기준 저장 응답이 참조 재조회 없이 저장자 참조를 담는지 확인한다."""
    # given: 사용자 참조 재조회가 실패하는 구성의 admin 클라이언트가 있다
    async with _admin_client() as http:
        # when: 경고 기준을 저장하고 내 정보를 조회한다
        response = await http.put(URL, json={"stale_days": 21})
        me = (await http.get("/api/v1/auth/me")).json()

    # then: 200이고 updated_by가 저장자의 id·역할·이름 라벨이다
    assert response.status_code == 200, response.text
    saver = response.json()["updated_by"]
    assert saver["id"] == me["user_id"]
    assert (saver["resigned"], saver["role"]) == (False, "admin")
    assert saver["label"] == saver["name"]


async def test_get_response_has_the_saver_reference_without_a_second_lookup() -> None:
    """경고 기준 조회 응답이 참조 재조회 없이 저장자 참조를 담는지 확인한다."""
    # given: 사용자 참조 재조회가 실패하는 구성의 admin 클라이언트가 있다
    async with _admin_client() as http:
        # when: 경고 기준을 저장한 뒤 조회하고 내 정보를 읽는다
        await http.put(URL, json={"stale_days": 21})
        response = await http.get(URL)
        me = (await http.get("/api/v1/auth/me")).json()

    # then: 200이고 저장한 기준과 저장자 id가 맞다
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stale_days"] == 21
    assert body["updated_by"]["id"] == me["user_id"]


async def test_get_before_any_save_needs_no_lookup_either() -> None:
    """저장 전 조회도 참조 조회 없이 기본값을 주는지 확인한다."""
    # given: 사용자 참조 재조회가 실패하는 구성의 admin 클라이언트가 있다
    async with _admin_client() as http:
        # when: 저장 전에 경고 기준을 조회한다
        response = await http.get(URL)

    # then: 200이고 기본 14일에 저장자·저장 시각이 비어 있다
    assert response.status_code == 200, response.text
    assert response.json() == {"stale_days": 14, "updated_at": None, "updated_by": None}
