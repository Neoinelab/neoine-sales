from typing import TYPE_CHECKING

from app.application.code.dto import CodeUsage
from app.application.code.usage import usage_by_key
from app.domain.code.errors import CodeNotFoundError
from app.domain.code.rules import ensure_unique_name, normalize_code_name

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.code.values import CodeId


class RenameCode:
    """코드 이름을 바꾼다. 잠긴 코드도 가능하며 key는 바뀌지 않는다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, code_id: CodeId, name: str) -> CodeUsage:
        clean = normalize_code_name(name)
        async with self._uow_factory() as uow:
            kind = (await uow.codes.get(code_id)).kind
            await uow.codes.lock_kind(kind)
            siblings = await uow.codes.list(kind, for_update=True)
            code = next((c for c in siblings if c.id == code_id), None)
            if code is None:
                raise CodeNotFoundError(code_id)
            ensure_unique_name(siblings, clean, self_id=code.id)
            code.rename(clean, self._clock.now())
            await uow.codes.update(code)
            counts = await usage_by_key(uow, code.kind)
            await uow.commit()
        return CodeUsage(code, counts.get(code.key.value, 0))
