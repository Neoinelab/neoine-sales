from typing import TYPE_CHECKING

from app.application.code.usage import usage_by_key
from app.domain.code.errors import CodeNotFoundError

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.code.values import CodeId


class DeleteCode:
    """코드를 물리 삭제한다. 잠긴 코드(먼저), 쓰는 Deal이 있는 코드, 쓰는 Action이 있는 코드는
    삭제할 수 없다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, code_id: CodeId) -> None:
        async with self._uow_factory() as uow:
            kind = (await uow.codes.get(code_id)).kind
            await uow.codes.lock_kind(kind)
            siblings = await uow.codes.list(kind, for_update=True)
            code = next((c for c in siblings if c.id == code_id), None)
            if code is None:
                raise CodeNotFoundError(code_id)
            deals = await usage_by_key(uow, code.kind)
            actions = await uow.deal_actions.count_by_code(code.kind)
            code.ensure_deletable(deals.get(code.key.value, 0), actions.get(code.key.value, 0))
            await uow.codes.delete(code.id)
            await uow.commit()
