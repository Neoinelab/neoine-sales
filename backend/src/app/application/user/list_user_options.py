from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Role
    from app.domain.user.value_objects import UserRef


class ListUserOptions:
    """사용자 선택 UI용 후보. 조건에 맞는 사용자 전부를 UserRef(이메일 없음, role 포함)로."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        keyword: str | None = None,
        include_resigned: bool = False,
        role: Role | None = None,
    ) -> Sequence[UserRef]:
        async with self._uow_factory() as uow:
            return await uow.users.search_refs(
                keyword=keyword,
                include_resigned=include_resigned,
                limit=None,
                role=role,
            )
