from typing import TYPE_CHECKING

from app.application.ports.pagination import DEFAULT_LIMIT, check_page
from app.domain.user.value_objects import UserStatusFilter

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User


class ListUsers:
    """사용자를 생성 순서로 돌려준다. 기본은 재직자만, status로 퇴사자·전체를 고른다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        status: UserStatusFilter = UserStatusFilter.ACTIVE,
        offset: int = 0,
        limit: int = DEFAULT_LIMIT,
    ) -> Sequence[User]:
        check_page(offset, limit)
        async with self._uow_factory() as uow:
            return await uow.users.list_users(status=status, offset=offset, limit=limit)
