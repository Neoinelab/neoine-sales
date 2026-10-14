from typing import TYPE_CHECKING

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.user.entities import User

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession, IssueSession
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory

DEV_LOGIN_IDS = frozenset(f"dev-{role.value}" for role in Role)
DEV_EMAIL = "dev@local.test"


def ensure_not_reserved_login_id(account: LoginId) -> None:
    """개발 로그인 전용 아이디로는 사용자를 등록할 수 없다(InvalidValueError)."""
    if account.value in DEV_LOGIN_IDS:
        raise InvalidValueError(f"개발 로그인 전용 아이디는 등록할 수 없습니다: {account.value}")


class DevLogin:
    """AD 없이 로컬 개발용 사용자로 로그인한다. 켜고 끄는 것은 설정(local 전용)이 정한다.

    dev-admin|dev-sales|dev-user 아이디의 재직 행을 users에 두고(없으면 스스로 등록) 일반 사용자와
    같은 경로로 세션을 발급한다. 퇴사 처리된 dev 행은 되살리지 않고 새 행을 만든다.
    """

    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, issue_session: IssueSession
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._issue_session = issue_session

    async def execute(self, role: Role) -> IssuedSession:
        account = LoginId(f"dev-{role.value}")
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()  # 재직 확인과 INSERT를 같은 잠금 안에서
            user = await uow.users.get_active_by_login_id(account)
            if user is None:
                user = self._register(account, role)
                await uow.users.add(user)
                await uow.commit()
        return await self._issue_session.execute(user.to_principal())

    def _register(self, account: LoginId, role: Role) -> User:
        now = self._clock.now()
        user = User.register_self(account, role, now=now)
        user.record_login(now, display_name=f"개발 사용자({role.value})", email=DEV_EMAIL)
        return user
