from typing import TYPE_CHECKING

from app.application.auth.dev_login import ensure_not_reserved_login_id
from app.application.auth.messages import LOGIN_REQUIRED
from app.domain.auth.credentials import LoginId
from app.domain.auth.errors import AuthenticationError
from app.domain.common.errors import AlreadyExistsError
from app.domain.user.entities import User
from app.domain.user.errors import AmbiguousLoginIdError, UserNotFoundError

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal, Role


class RegisterUser:
    """admin이 AD 계정의 로그인 아이디를 사용자로 등록한다(AD에 계정 존재 여부는 묻지 않는다).

    퇴사자의 아이디도 다시 등록할 수 있고, 그때마다 새 행(새 id)이 생긴다. 재직자 중복은 DB가
    아니라 roster 잠금 안에서 확인한다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self, *, login_id: str, role: Role, actor: Principal, display_name: str | None = None
    ) -> User:
        account = LoginId(login_id)
        ensure_not_reserved_login_id(account)
        user = User.register(
            account,
            role,
            created_by_user_id=actor.user_id,
            now=self._clock.now(),
            display_name=display_name,
        )
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()
            try:
                exists = await uow.users.get_active_by_login_id(account) is not None
            except AmbiguousLoginIdError:  # 이미 둘 이상 있다 = 중복이라는 같은 결론
                exists = True
            if exists:
                raise AlreadyExistsError("사용자", account.value)
            try:
                await uow.users.add(user)
            except UserNotFoundError:  # 요청한 admin이 그 사이 삭제됨(created_by FK 위반)
                raise AuthenticationError(LOGIN_REQUIRED) from None
            await uow.commit()
        return user
