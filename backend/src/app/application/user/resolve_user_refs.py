from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.value_objects import UserId, UserRef


class ResolveUserRefs:
    """사용자 id 묶음을 표시용 참조로 한 번에 바꾼다(퇴사자 포함, 없는 id는 빠짐)."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, user_ids: Collection[UserId]) -> Mapping[UserId, UserRef]:
        if not user_ids:
            return {}
        async with self._uow_factory() as uow:
            return await uow.users.get_refs(user_ids)
