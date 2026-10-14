from typing import TYPE_CHECKING

from app.application.ports.pagination import MAX_LIMIT, check_page

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.value_objects import UserRef


class ListUserOptions:
    """사용자 선택 UI용 후보. 이메일·역할 없이 표시용 참조(UserRef)만 돌려준다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        keyword: str | None = None,
        include_resigned: bool = False,
        limit: int = MAX_LIMIT,
    ) -> Sequence[UserRef]:
        check_page(0, limit)
        async with self._uow_factory() as uow:
            return await uow.users.search_refs(
                keyword=keyword, include_resigned=include_resigned, limit=limit
            )
