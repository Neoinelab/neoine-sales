"""Deal 상세·변경·이력·삭제 라우터 단위 테스트 공용 도우미(FakeUseCases 위의 ASGI 클라이언트, 시드).

세션 사용자의 id는 `uid(이름)`이라, 이름이 "owner"인 사용자가 기본 Deal의 Owner(`OWNER_ID`)다.
Deal은 `seed_deal`로 저장소에 직접 두고, 기본 코드(Status·Forecast)는 `seed_catalog`로 넣는다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Final

from httpx import ASGITransport, AsyncClient

from app.domain.user.errors import UserNotFoundError
from app.main import create_app
from tests.factories_auth import make_principal, make_user
from tests.factories_deal import seed_deal
from tests.fakes.catalog_seed import seed_catalog
from tests.support.app_settings import CSRF_HEADER, make_settings
from tests.support.user_ids import OWNER_ID, uid
from tests.support.user_seed import ensure_users
from tests.unit.web.saved_report_http import SESSION_COOKIE, UNUSED_DATABASE_URL, problem

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from app.domain.auth.principal import Role
    from app.domain.deal.entities import Deal
    from tests.fakes.use_cases import FakeUseCases

__all__ = [
    "BASE",
    "CODE",
    "NOT_FOUND",
    "READ_ONLY",
    "clients",
    "problem",
    "seed",
    "stored_deal_codes",
]

BASE: Final = "/api/v1/deals"
CODE: Final = "20261016-A001"
NOT_FOUND: Final = "Deal을 찾을 수 없습니다."
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"


@asynccontextmanager
async def clients(
    use_cases: FakeUseCases, users: Mapping[str, Role], *, csrf: bool = True
) -> AsyncIterator[dict[str, AsyncClient]]:
    """사용자 이름 -> 그 사용자 세션의 클라이언트(`uid(이름)`이 사용자 id). "anon"은 비로그인."""
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    made: dict[str, AsyncClient] = {}
    try:
        for name, role in users.items():
            cookies = {}
            if name != "anon":
                await _ensure_user(use_cases, name, role)
                principal = make_principal(name, role, user_id=uid(name))
                cookies[SESSION_COOKIE] = await use_cases.login_as(principal)
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


async def _ensure_user(use_cases: FakeUseCases, name: str, role: Role) -> None:
    """요청 권한은 저장소의 사용자 행 역할로 정해지므로, 없는 사용자는 그 역할로 만든다."""
    async with use_cases.uow as uow:
        try:
            await uow.users.get(uid(name))
        except UserNotFoundError:
            await uow.users.add(make_user(name, role, entity_id=uid(name)))
        await uow.commit()


async def seed(use_cases: FakeUseCases, code: str = CODE, **overrides: Any) -> Deal:  # noqa: ANN401
    """기본 코드·Owner 사용자·고객 연락처가 있는 Deal을 저장소에 둔다. overrides는 `make_deal`."""
    seed_catalog(use_cases.uow)
    async with use_cases.uow as uow:
        await ensure_users(uow.users, OWNER_ID)
        deal = await seed_deal(uow, code=code, commit=False, **overrides)
        await uow.commit()
    return deal


def stored_deal_codes(use_cases: FakeUseCases) -> set[str]:
    """저장소에 남은 Deal code."""
    return {deal_id.value for deal_id in use_cases.uow.deals._items}
