import logging
from typing import TYPE_CHECKING

from app.application.ports.file_storage import StorageNotWritableError
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWorkFactory

logger = logging.getLogger(__name__)


class DeleteDeal:
    """Deal을 물리 삭제한다(이력·Action·링크·BANT 선택이 함께 지워진다).

    검사 순서: 없음(형식 오류 포함), 삭제 권한, 삭제 확인 code. 커밋한 뒤 운영 로그 한 줄을 남기고,
    저장 위치가 설정돼 있으면 `<저장 위치>/<deal code>` 디스크 파일을 지운다(실패는 경고 로그만).
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._storage = storage

    async def execute(self, code: str, confirm_code: str, actor: Actor) -> None:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        now = self._clock.now()
        async with self._uow_factory() as uow:
            deal = await uow.deals.get(deal_code, for_update=True)
            deal.ensure_deletable_by(actor.user_id, actor.role)
            deal.ensure_confirm_code(confirm_code)
            settings = await uow.storage_settings.get()
            await uow.deals.delete(deal_code)
            await uow.commit()
        logger.info(
            "deal deleted code=%s by=%s at=%s", deal_code.value, actor.user_id, now.isoformat()
        )
        if settings is not None:
            try:
                await self._storage.delete_deal_files(settings.path, deal_code)
            except StorageNotWritableError:
                logger.warning("deal files cleanup failed code=%s", deal_code.value)
