from typing import TYPE_CHECKING

from app.application.ports.pagination import DEFAULT_LIMIT, check_page

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User


class ListUsers:
    """활성 사용자를 생성 순서로 돌려준다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[User]:
        check_page(offset, limit)
        async with self._uow_factory() as uow:
            return await uow.users.list_active(offset=offset, limit=limit)
