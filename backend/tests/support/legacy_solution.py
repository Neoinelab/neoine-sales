"""Solution 도입 전 레거시 Deal(`solution == ''`)을 저장소에 만들어 두는 도우미.

구현이 값 객체 검증을 어떻게 바꾸든 같은 상태가 되도록 frozen 필드를 직접 비운다.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal
    from tests.unit.application.deal_env import DealEnv


def blank_solution(deal: Deal) -> Deal:
    """Deal의 Solution을 레거시 값 ''로 만든다(검증 없이)."""
    object.__setattr__(deal.details, "solution", "")
    return deal


async def new_legacy_deal(env: DealEnv, **overrides: Any) -> str:  # noqa: ANN401
    """Solution이 ''인 저장된 Deal을 만들고 code를 돌려준다. overrides는 `env.new_deal`과 같다."""
    from app.domain.deal.code import DealCode  # noqa: PLC0415 - 도메인 지연 import

    view = await env.new_deal(**overrides)
    code = view.item.deal.id.value
    deal = await env.uow.deals.get(DealCode(code))
    await env.uow.deals.update(blank_solution(deal))
    return code
