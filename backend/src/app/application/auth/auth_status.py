from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.auth.mode import AuthMode, effective_mode

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class AuthStatus:
    directory_configured: bool
    storage_configured: bool
    needs_directory_setup: bool
    needs_storage_setup: bool
    needs_admin_setup: bool
    auth_mode: AuthMode | None


class GetAuthStatus:
    """최초 설정이 어디까지 됐는지 알려 준다(방식·AD -> 저장 위치 -> admin). 로그인 없이 쓴다."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> AuthStatus:
        async with self._uow_factory() as uow:
            directory = await uow.directory_settings.get() is not None
            storage = await uow.storage_settings.get() is not None
            has_admin = await uow.users.count_active_admins() > 0
            stored = await uow.auth_settings.get()
        mode = effective_mode(stored)
        setup_open = stored is None or stored.setup_pending or not has_admin
        storage_done = storage and stored is not None and not stored.setup_pending
        directory_step_done = mode is AuthMode.LOCAL or (mode is AuthMode.AD and directory)
        return AuthStatus(
            directory_configured=directory,
            storage_configured=storage,
            needs_directory_setup=setup_open and not directory_step_done,
            needs_storage_setup=setup_open and not storage_done,
            needs_admin_setup=not has_admin and storage_done and directory_step_done,
            auth_mode=mode,
        )
