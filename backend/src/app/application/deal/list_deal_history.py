from typing import TYPE_CHECKING

from app.application.deal.dto import HistoryEntryView
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.deal.history import HistoryCategory


class ListDealHistory:
    """Deal의 History를 최신순으로(구분으로 거를 수 있다). 없는 Deal은 DealNotFoundError."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, code: str, category: HistoryCategory | None) -> list[HistoryEntryView]:
        deal_code = DealCode.parse_or_none(code)
        if deal_code is None:
            raise DealNotFoundError(code)
        async with self._uow_factory() as uow:
            if not await uow.deals.exists(deal_code):
                raise DealNotFoundError(code)
            entries = await uow.deal_history.list(deal_code, category=category)
            refs = await uow.users.get_refs({entry.changed_by for entry in entries})
        return [HistoryEntryView(entry=entry, by=refs[entry.changed_by]) for entry in entries]
