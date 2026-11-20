from datetime import date
from typing import TYPE_CHECKING

from app.application.deal.dto import ApplyChangeResult
from app.application.deal.history_writer import record_deal_diff
from app.application.deal.sync_change import apply_sync_change, load_catalog
from app.application.deal.validation import EXPECTED_CLOSE_REQUIRED
from app.application.deal.views import build_views
from app.application.license_contract.won_follow_up import follow_won_change, remove_pending_folders
from app.domain.common.business_date import business_date
from app.domain.common.errors import InvalidValueError
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.values import check_amount

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor, DealChangeInput
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.entities import Deal
    from app.domain.deal.sync import CodeCatalog, SyncApplied


class ApplyDealChange:
    """단일 필드 변경(Status, Forecast, 매출금액, Expected Close).

    Status와 Forecast는 동기화 규칙에 따라 함께 바뀌는 값을 resolution으로 받아 같은 규칙으로
    다시 검증한다. 바뀐 필드마다 History 한 건(함께 바뀐 값은 표기), 바뀐 것이 없으면 이력도
    수정 시각 변경도 없다. Owner 검사는 하지 않는다(퇴사 Owner의 Deal도 바꿀 수 있다).
    코드 목록은 종류당 한 번만 읽는다. Won 진입·이탈에 따른 라이선스 계약 처리는 같은 트랜잭션에서
    하고, 삭제한 계약의 첨부 파일은 커밋 뒤에 지운다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._storage = storage

    async def execute(self, code: str, change: DealChangeInput, actor: Actor) -> ApplyChangeResult:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        now = self._clock.now()
        async with self._uow_factory() as uow:
            deal = await uow.deals.get(deal_code, for_update=True)
            catalog = await load_catalog(uow)
            before = deal.snapshot()
            before_sync = deal.sync
            applied = self._change(deal, change, catalog)
            co_changed = applied.co_changed if applied else ()
            await record_deal_diff(
                uow,
                deal,
                before,
                actor_id=actor.user_id,
                now=now,
                catalog=catalog,
                co_changed=co_changed,
            )
            removal = await follow_won_change(
                uow,
                deal_code,
                before_sync,
                deal.sync,
                delete_contracts=change.delete_license_contracts,
                actor=actor,
                now=now,
            )
            view = (
                await build_views(
                    uow, [await uow.deals.get_item(deal.id, today=business_date(now))], now=now
                )
            )[0]
            await uow.commit()
        await remove_pending_folders(self._storage, removal)
        return ApplyChangeResult(
            view=view,
            co_changed=co_changed,
            notice=applied.notice if applied else None,
        )

    def _change(
        self, deal: Deal, change: DealChangeInput, catalog: CodeCatalog
    ) -> SyncApplied | None:
        if change.field in ("status_key", "forecast_key"):
            return apply_sync_change(deal, change.field, change.value, change.resolution, catalog)
        if change.field == "revenue_amount":
            deal.change_revenue_amount(check_amount(change.value))
        elif isinstance(change.value, date):
            deal.change_revenue_date(change.value)
        else:
            raise InvalidValueError(EXPECTED_CLOSE_REQUIRED)
        return None
