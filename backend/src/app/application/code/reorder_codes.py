from typing import TYPE_CHECKING

from app.application.code.dto import CodeUsage
from app.application.code.usage import usage_by_key
from app.domain.code.rules import reorder

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.code.values import CodeId, CodeKind


class ReorderCodes:
    """한 종류의 코드 전부를 주어진 순서로 1부터 다시 매긴다. 바뀐 행만 저장한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, kind: CodeKind, ordered_ids: Sequence[CodeId]) -> list[CodeUsage]:
        async with self._uow_factory() as uow:
            await uow.codes.lock_kind(kind)
            codes = await uow.codes.list(kind, for_update=True)
            before = {c.id: c.order for c in codes}
            ordered = reorder(codes, ordered_ids, self._clock.now())
            for code in ordered:
                if code.order != before[code.id]:
                    await uow.codes.update(code)
            counts = await usage_by_key(uow, kind)
            await uow.commit()
        return [CodeUsage(c, counts.get(c.key.value, 0)) for c in ordered]
