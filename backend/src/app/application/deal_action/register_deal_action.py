from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.deal.history_writer import record_deal_diff, write_history
from app.application.deal.sync_change import load_catalog, to_sync_step
from app.application.deal_action.type_choice import choose_action_type
from app.application.ids import new_deal_action_id
from app.application.license_contract.won_follow_up import follow_won_change, remove_pending_folders
from app.domain.common.errors import InvalidStateError
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.sync import SyncState, finalize_sequence
from app.domain.deal_action.acted_on import ensure_not_before_basis, resolve_acted_on
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.errors import PREVIOUS_NEXT_ACTION_CHANGED
from app.domain.deal_action.history import action_created_draft, next_action_status_draft

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date, datetime

    from app.application.deal.inputs import Actor
    from app.application.deal_action.inputs import DealActionInput, StatusChangeInput
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.deal.entities import Deal
    from app.domain.deal.history import HistoryDraft


@dataclass(frozen=True)
class _CloseRequest:
    """이전 Next Action을 닫는 데 필요한 값 묶음."""

    basis_id: int | None
    actor: Actor
    now: datetime
    acted_on: date


class RegisterDealAction:
    """Deal에 Action을 기록한다. 수행일·수행자는 서버가 정하고 Status/Forecast를 스냅숏한다.

    status_changes가 있으면 `ApplyDealChange`와 같은 규칙으로 순서대로 먼저 Deal을 바꾼다(같은
    트랜잭션, 모두 판정한 뒤에만 반영하며 하나라도 실패하면 아무것도 저장하지 않는다).
    없는 Deal은 입력 검증보다 먼저 DealNotFoundError다. 여러 단계로 바뀐 Deal은 처음과 끝만 견줘
    Won 진입·이탈에 따른 라이선스 계약 처리를 같은 트랜잭션에서 하고, 삭제한 계약의 첨부 파일은
    커밋 뒤에 지운다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._storage = storage

    async def execute(self, code: str, data: DealActionInput, actor: Actor) -> DealAction:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        now = self._clock.now()
        async with self._uow_factory() as uow:
            deal = await uow.deals.get(deal_code, for_update=True)
            action_type = await choose_action_type(
                uow, data.content.action_type, actor.user_id, now
            )
            content = data.content.to_content(action_type)
            acted_on = resolve_acted_on(data.acted_on, now=now, deal_registered_at=deal.created_at)
            close = _CloseRequest(data.close_previous_next_action_id, actor, now, acted_on)
            drafts = await self._close_previous(uow, deal_code, close)
            before_sync = deal.sync
            if data.status_changes:
                await self._change_deal(uow, deal, data.status_changes, actor, now)
            removal = await follow_won_change(
                uow,
                deal_code,
                before_sync,
                deal.sync,
                delete_contracts=data.delete_license_contracts,
                actor=actor,
                now=now,
            )
            action = DealAction.record(
                deal_code=deal_code,
                content=content,
                actor_user_id=actor.user_id,
                snapshot=deal.sync,
                now=now,
                acted_on=acted_on,
                entity_id=await new_deal_action_id(uow.ids),
            )
            await uow.deal_actions.add(action)
            drafts.append(action_created_draft(content))
            await write_history(uow, deal_code, actor.user_id, drafts, now)
            await uow.commit()
        await remove_pending_folders(self._storage, removal)
        return action

    async def _close_previous(
        self,
        uow: UnitOfWork,
        deal_code: DealCode,
        close: _CloseRequest,
    ) -> list[HistoryDraft]:
        """기준 행이면 종료(수행)로 닫고 이력 초안을 돌려준다. 이미 종료면 건너뛴다(빈 목록)."""
        if close.basis_id is None:
            return []
        basis = await uow.deal_actions.latest_with_next_action(deal_code)
        if basis is None or basis.id != close.basis_id:
            raise InvalidStateError(PREVIOUS_NEXT_ACTION_CHANGED)
        basis.ensure_status_changeable_by(close.actor.user_id, close.actor.role)
        ensure_not_before_basis(close.acted_on, basis.acted_on)
        change = basis.close_as_done_for_next_update(close.now)
        if change is None:
            return []
        await uow.deal_actions.update(basis)
        return [next_action_status_draft(basis.content, change)]

    async def _change_deal(
        self,
        uow: UnitOfWork,
        deal: Deal,
        changes: Sequence[StatusChangeInput],
        actor: Actor,
        now: datetime,
    ) -> None:
        catalog = await load_catalog(uow)
        steps = [to_sync_step(c.field, c.value, c.resolution, catalog) for c in changes]
        current = SyncState(deal.sync.status_key, deal.sync.forecast_key)
        for applied in finalize_sequence(current, steps, catalog):
            before = deal.snapshot()
            deal.apply_sync(applied)
            await record_deal_diff(
                uow,
                deal,
                before,
                actor_id=actor.user_id,
                now=now,
                catalog=catalog,
                co_changed=applied.co_changed,
            )
