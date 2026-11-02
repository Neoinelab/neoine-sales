from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.auth.dev_login import DEV_LOGIN_IDS
from app.application.auth.mode import current_mode
from app.domain.auth.mode import AuthMode

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from app.domain.user.entities import User


@dataclass(frozen=True, slots=True)
class MyProfile:
    """내 정보와 항목별 수정 가능 여부(전화는 두 모드 모두 수정 가능)."""

    user: User
    mode: AuthMode
    can_edit_name_email: bool
    can_change_password: bool


def build_my_profile(user: User, mode: AuthMode | None) -> MyProfile:
    effective = mode or AuthMode.AD
    local = effective is AuthMode.LOCAL
    return MyProfile(
        user=user,
        mode=effective,
        can_edit_name_email=local,
        can_change_password=local and user.login_id.value not in DEV_LOGIN_IDS,
    )


class GetMyProfile:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, actor: Principal) -> MyProfile:
        async with self._uow_factory() as uow:
            user = await uow.users.get(actor.user_id)
            mode = await current_mode(uow)
        return build_my_profile(user, mode)
