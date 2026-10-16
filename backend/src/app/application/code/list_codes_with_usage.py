from typing import TYPE_CHECKING

from app.application.code.dto import CodeUsage
from app.application.code.usage import usage_by_key

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.code.values import CodeKind


class ListCodesWithUsage:
    """한 종류의 코드를 order 순으로, 쓰는 Deal 수와 함께 돌려준다(관리자용)."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, kind: CodeKind) -> list[CodeUsage]:
        async with self._uow_factory() as uow:
            counts = await usage_by_key(uow, kind)
            return [CodeUsage(c, counts.get(c.key.value, 0)) for c in await uow.codes.list(kind)]
