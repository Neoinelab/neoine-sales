"""응답 시각 표기: Deal 상세·목록·Dashboard 요약의 시각은 서버 오프셋이고 순간은 서버 시계와 같다.

DB 없이 FakeUseCases 위의 HTTP 계약으로 확인한다.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.domain.contact.values import ContactKind
from app.main import create_app
from tests.factories import make_deal
from tests.factories_auth import make_principal
from tests.factories_contact import make_contact
from tests.fakes.catalog_seed import seed_catalog
from tests.fakes.unit_of_work import FixedClock
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import CSRF_HEADER, make_settings
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
MOMENT = datetime(2026, 12, 31, 15, 0, tzinfo=UTC)  # 서울 2027-01-01 00:00


@asynccontextmanager
async def _client() -> AsyncIterator[tuple[AsyncClient, str]]:
    """서버 시계가 MOMENT에 고정되고 그 시각에 등록된 Deal이 하나 있는 앱. 둘째 값은 deal code."""
    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    await ensure_users(use_cases.uow.users, OWNER_ID)
    deal = make_deal(MOMENT, code="20261231-A001")
    await use_cases.uow.contacts.add(make_contact(ContactKind.CUSTOMER, entity_id=deal.customer_id))
    use_cases.uow.deals._items[deal.id] = deal
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookie = await use_cases.login_as(make_principal("root", Role.SALES))
    use_cases.clock = FixedClock(MOMENT)  # 로그인 뒤 서버 시계를 고정한다
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies={SESSION_COOKIE: cookie},
    ) as http:
        yield http, deal.id.value


def _assert_server_instant(stamp: str) -> None:
    assert stamp.endswith("+09:00"), stamp
    assert datetime.fromisoformat(stamp) == MOMENT, stamp


async def test_deal_detail_timestamps_carry_server_offset(local_tz: Callable[[str], None]) -> None:
    """Deal 상세의 시각은 서버 오프셋이고 순간은 서버 시계와 같다.

    테스트 코드: TM-021
    """
    # given: 서버 시간대 Asia/Seoul, 서버 시계와 같은 시각에 등록된 Deal
    local_tz("Asia/Seoul")
    async with _client() as (http, code):
        # when: Deal 상세를 조회한다
        response = await http.get(f"/api/v1/deals/{code}")

    # then: 시각 필드가 +09:00이고 순간은 서버 시계와 같다
    assert response.status_code == 200, response.text
    body = response.json()
    for field in ("created_at", "updated_at", "status_changed_at", "last_updated_at"):
        _assert_server_instant(body[field])


async def test_deal_list_timestamps_carry_server_offset(local_tz: Callable[[str], None]) -> None:
    """Deal 목록 행의 시각도 서버 오프셋이다.

    테스트 코드: TM-021
    """
    # given: 서버 시간대 Asia/Seoul, 서버 시계와 같은 시각에 등록된 Deal
    local_tz("Asia/Seoul")
    async with _client() as (http, _code):
        # when: Deal 목록을 조회한다
        response = await http.get("/api/v1/deals")

    # then: 행의 시각 필드가 +09:00이고 순간은 서버 시계와 같다
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    for field in ("created_at", "last_updated_at"):
        _assert_server_instant(items[0][field])


async def test_dashboard_as_of_carries_server_offset(local_tz: Callable[[str], None]) -> None:
    """Dashboard 요약의 as_of도 서버 오프셋이다.

    테스트 코드: TM-021
    """
    # given: 서버 시간대 Asia/Seoul, 서버 시계 고정
    local_tz("Asia/Seoul")
    async with _client() as (http, _code):
        # when: Dashboard 요약(year=2026)을 조회한다
        response = await http.get("/api/v1/dashboard/summary", params={"year": 2026})

    # then: as_of가 +09:00이고 순간은 서버 시계와 같다
    assert response.status_code == 200, response.text
    _assert_server_instant(response.json()["as_of"])
