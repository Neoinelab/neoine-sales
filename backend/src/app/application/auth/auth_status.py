from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class AuthStatus:
    directory_configured: bool
    needs_directory_setup: bool
    needs_admin_setup: bool


class GetAuthStatus:
    """최초 설정이 어디까지 됐는지 알려 준다. 로그인 없이 호출된다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> AuthStatus:
        async with self._uow_factory() as uow:
            configured = await uow.directory_settings.get() is not None
            has_admin = await uow.users.count_active_admins() > 0
        return AuthStatus(
            directory_configured=configured,
            needs_directory_setup=not configured,
            needs_admin_setup=configured and not has_admin,
        )
