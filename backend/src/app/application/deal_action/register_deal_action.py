from typing import TYPE_CHECKING

from app.application.deal.history_writer import record_deal_diff, write_history
from app.application.deal.sync_change import apply_sync_change, load_catalog
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.history import action_created_draft

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.deal.inputs import Actor
    from app.application.deal_action.inputs import DealActionInput, StatusChangeInput
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.deal.entities import Deal


class RegisterDealAction:
    """Deal에 Action을 기록한다. 수행 일시·수행자는 서버가 정하고 Status/Forecast를 스냅숏한다.

    status_change가 있으면 `ApplyDealChange`와 같은 규칙으로 먼저 Deal을 바꾼다(같은 트랜잭션,
    하나라도 실패하면 아무것도 저장하지 않는다). 없는 Deal은 입력 검증보다 먼저 DealNotFoundError다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, code: str, data: DealActionInput, actor: Actor) -> DealAction:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        now = self._clock.now()
        async with self._uow_factory() as uow:
            deal = await uow.deals.get(deal_code, for_update=True)
            content = data.content.to_content()
            if data.status_change is not None:
                await self._change_deal(uow, deal, data.status_change, actor, now)
            action = DealAction.record(
                deal_code=deal_code,
                content=content,
                actor_user_id=actor.user_id,
                snapshot=deal.sync,
                now=now,
            )
            await uow.deal_actions.add(action)
            await write_history(uow, deal_code, actor.user_id, [action_created_draft(content)], now)
            await uow.commit()
        return action

    async def _change_deal(
        self, uow: UnitOfWork, deal: Deal, change: StatusChangeInput, actor: Actor, now: datetime
    ) -> None:
        catalog = await load_catalog(uow)
        before = deal.snapshot()
        applied = apply_sync_change(deal, change.field, change.value, change.resolution, catalog)
        await record_deal_diff(
            uow,
            deal,
            before,
            actor_id=actor.user_id,
            now=now,
            catalog=catalog,
            co_changed=applied.co_changed,
        )
