"""Action 유형 라우터 단위 테스트 공용 도우미: 시드된 FakeUseCases와 Action을 쓰는 유형 준비."""

from typing import TYPE_CHECKING

from app.domain.common.errors import NotFoundError
from tests.factories import make_deal_action, make_deal_code
from tests.factories_deal import seed_deal
from tests.fakes.catalog_seed import seed_action_types, seed_catalog
from tests.fakes.use_cases import FakeUseCases
from tests.support.user_ids import ACTOR_ID, OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from httpx import AsyncClient

URL = "/api/v1/action-types"
TYPE_KEYS = {"id", "name", "is_default", "created_by", "usage_count", "created_at", "updated_at"}
DEFAULT_NAMES = ["통화", "미팅", "이메일", "데모", "제안", "협상", "계약", "기타"]


def seeded_use_cases() -> FakeUseCases:
    """기본 유형 8개가 시드된 FakeUseCases(마이그레이션이 넣는 상태와 같다)."""
    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    seed_action_types(use_cases.uow)
    return use_cases


async def use_type(use_cases: FakeUseCases, name: str, *, count: int = 1) -> None:
    """name 유형을 쓰는 Action을 count건 저장소에 직접 둔다(Deal 하나에)."""
    uow = use_cases.uow
    await ensure_users(uow.users, OWNER_ID, ACTOR_ID)
    code = make_deal_code()
    try:
        await uow.deals.get(code)
    except NotFoundError:
        await seed_deal(uow, code=code.value)
    for _ in range(count):
        await uow.deal_actions.add(make_deal_action(deal_code=code, action_type=name))
    await uow.commit()


async def type_id_of(http: AsyncClient, name: str) -> str:
    body = (await http.get(URL)).json()
    return str(next(item["id"] for item in body if item["name"] == name))
