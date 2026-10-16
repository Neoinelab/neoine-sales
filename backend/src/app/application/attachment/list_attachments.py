from typing import TYPE_CHECKING

from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.attachment.entities import Attachment


class ListAttachments:
    """한 Deal의 첨부를 최신순으로 돌려준다. 없는 Deal(형식 오류 포함)은 DealNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, code: str) -> Sequence[Attachment]:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        async with self._uow_factory() as uow:
            if not await uow.deals.exists(deal_code):
                raise DealNotFoundError(code)
            return await uow.attachments.list_by_deal(deal_code)
