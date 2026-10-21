from typing import TYPE_CHECKING

from app.application.code.dto import CodeUsage
from app.application.ids import new_code_id
from app.domain.code.entities import Code
from app.domain.code.rules import ensure_unique_name, generate_key, normalize_code_name

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.code.values import CodeKind


class RegisterCode:
    """코드를 종류의 맨 끝에 추가한다. 같은 종류를 잠근 채 이름·key·order를 정한다."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, *, kind: CodeKind, name: str, probability_hint: str | None = None
    ) -> CodeUsage:
        clean = normalize_code_name(name)
        async with self._uow_factory() as uow:
            await uow.codes.lock_kind(kind)
            siblings = await uow.codes.list(kind, for_update=True)
            ensure_unique_name(siblings, clean)
            code = Code.create(
                entity_id=await new_code_id(uow.ids),
                kind=kind,
                name=clean,
                key=generate_key(clean, {c.key.value for c in siblings}),
                order=max((c.order for c in siblings), default=0) + 1,
                probability_hint=probability_hint,
                now=self._clock.now(),
            )
            await uow.codes.add(code)
            await uow.commit()
        return CodeUsage(code, 0)
