from typing import TYPE_CHECKING

from app.application.code.dto import CodeSet
from app.domain.code.values import CodeKind

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class ListCodeSet:
    """Status와 Forecast 코드를 order 순으로 돌려준다(로그인 사용자 누구나)."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> CodeSet:
        async with self._uow_factory() as uow:
            return CodeSet(
                statuses=await uow.codes.list(CodeKind.STATUS),
                forecasts=await uow.codes.list(CodeKind.FORECAST),
            )
