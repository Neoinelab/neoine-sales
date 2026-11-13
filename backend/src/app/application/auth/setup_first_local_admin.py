from typing import TYPE_CHECKING

from app.application.auth.messages import SETUP_CLOSED, STORAGE_FIRST
from app.application.auth.mode import ensure_local_mode
from app.application.ids import new_user_id
from app.domain.auth.credentials import LoginId
from app.domain.auth.password_policy import ensure_acceptable_password
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidStateError
from app.domain.user.entities import User
from app.domain.user.errors import AmbiguousLoginIdError
from app.domain.user.profile import normalize_email, normalize_name, normalize_phone
from app.domain.user.retired_login_ids import ensure_not_reserved_login_id

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.auth.issue_session import IssuedSession, IssueSession
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.auth.credentials import Password


class SetupFirstLocalAdmin:
    """local 모드 최초 설정 3단계: 입력한 아이디·비밀번호·이름으로 첫 admin을 만들고 로그인시킨다.

    검증할 기존 자격증명이 없으므로 AD도, 로그인 시도 제한도 쓰지 않는다.
    실패하면 설정은 열린 채 남는다. 해시 계산은 DB 트랜잭션 밖에서 한다.
    """

    def __init__(self, deps: AuthDeps, issue_session: IssueSession) -> None:
        self._deps = deps
        self._issue_session = issue_session

    async def execute(
        self,
        *,
        login_id: str,
        password: Password,
        display_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> IssuedSession:
        account = LoginId(login_id)
        ensure_not_reserved_login_id(account)
        ensure_acceptable_password(password, account)
        profile = {
            "display_name": normalize_name(display_name, required=True),
            "email": normalize_email(email),
            "phone": normalize_phone(phone),
        }
        async with self._deps.uow_factory() as uow:
            await self._ensure_open(uow)
            if await uow.storage_settings.get() is None:
                raise InvalidStateError(STORAGE_FIRST)
        password_hash = await self._deps.hasher.hash(password)
        now = self._deps.clock.now()
        async with self._deps.uow_factory() as uow:
            await uow.users.lock_roster()
            await ensure_local_mode(uow)
            await self._ensure_open(uow)
            try:
                exists = await uow.users.get_active_by_login_id(account) is not None
            except AmbiguousLoginIdError:  # 이미 둘 이상 있다 = 중복이라는 같은 결론
                exists = True
            if exists:
                raise AlreadyExistsError("사용자", account.value)
            user = User.register(
                account, Role.ADMIN, entity_id=await new_user_id(uow.ids), now=now, **profile
            )
            user.record_password_login(now)
            await uow.users.add(user)
            await uow.password_hashes.save(user.id, password_hash, now)
            await uow.commit()
        return await self._issue_session.execute(user.to_principal())

    @staticmethod
    async def _ensure_open(uow: UnitOfWork) -> None:
        if await uow.users.count_active_admins() > 0:
            raise InvalidStateError(SETUP_CLOSED)
