from typing import TYPE_CHECKING

from app.domain.auth.credentials import LoginId
from app.domain.common.errors import AlreadyExistsError
from app.domain.user.entities import User

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal, Role


class RegisterUser:
    """admin이 AD 계정의 로그인 아이디를 사용자로 등록한다(AD에 계정 존재 여부는 묻지 않는다)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, *, login_id: str, role: Role, actor: Principal) -> User:
        account = LoginId(login_id)
        user = User.register(account, role, created_by=actor.subject, now=self._clock.now())
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()
            if await uow.users.get_active_by_login_id(account) is not None:
                raise AlreadyExistsError("사용자", account.value)
            await uow.users.add(user)
            await uow.commit()
        return user
