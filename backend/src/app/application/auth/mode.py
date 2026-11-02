"""현재 인증 방식을 읽는 도우미(유스케이스가 공유한다)."""

from typing import TYPE_CHECKING

from app.application.auth.messages import DIRECTORY_MODE_ONLY, LOCAL_MODE_ONLY
from app.domain.auth.mode import AuthMode, effective_mode
from app.domain.common.errors import InvalidStateError

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWork


async def current_mode(uow: UnitOfWork) -> AuthMode | None:
    """저장된 방식, 없으면 admin이나 AD 설정이 있는 기존 시스템은 AD, 아니면 None(미선택)."""
    stored = await uow.auth_settings.get()
    if stored is not None:
        return stored.mode
    return effective_mode(
        None,
        has_admin=await uow.users.count_active_admins() > 0,
        has_directory=await uow.directory_settings.get() is not None,
    )


async def ensure_directory_mode(uow: UnitOfWork) -> None:
    """local 모드에서는 AD 설정을 저장하거나 시험할 수 없다."""
    if await current_mode(uow) is AuthMode.LOCAL:
        raise InvalidStateError(DIRECTORY_MODE_ONLY)


async def ensure_local_mode(uow: UnitOfWork) -> None:
    """해시 계산 뒤 잠금 안에서 방식이 여전히 local인지 다시 확인한다."""
    if await current_mode(uow) is not AuthMode.LOCAL:
        raise InvalidStateError(LOCAL_MODE_ONLY)
