from typing import TYPE_CHECKING

from app.application.auth.mode import current_mode, ensure_local_mode
from app.application.ids import new_user_id
from app.domain.auth.credentials import LoginId
from app.domain.auth.mode import AuthMode
from app.domain.auth.password_policy import ensure_acceptable_password
from app.domain.common.errors import AlreadyExistsError, InvalidValueError
from app.domain.user.entities import User
from app.domain.user.errors import AmbiguousLoginIdError
from app.domain.user.profile import normalize_email, normalize_name, normalize_phone
from app.domain.user.retired_login_ids import ensure_not_reserved_login_id

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.password_hasher import PasswordHasher
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.credentials import Password
    from app.domain.auth.password_hash import PasswordHash
    from app.domain.auth.principal import Principal, Role


AD_CREDENTIAL_NOT_ACCEPTED = "AD 연동에서는 비밀번호를 입력하지 않습니다."
CREDENTIAL_REQUIRED = "비밀번호를 입력하세요."


class RegisterUser:
    """admin이 사용자를 등록한다. 아이디는 AD 계정에 있는지 묻지 않는다(AD 모드).

    local 모드는 비밀번호·이름이 필수이고 해시를 같은 트랜잭션에 저장한다(해시 계산은 트랜잭션 밖).
    AD 모드는 비밀번호를 받지 않는다. 퇴사자의 아이디도 다시 등록할 수 있고, 그때마다 새 행(새 id)이
    생긴다. 재직자 중복은 DB가 아니라 roster 잠금 안에서 확인한다.
    """

    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, hasher: PasswordHasher
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._hasher = hasher

    async def execute(  # noqa: PLR0913 - 등록 입력(아이디·역할·요청자·프로필 3개·비밀번호)이 모두 의미 있다
        self,
        *,
        login_id: str,
        role: Role,
        actor: Principal,
        display_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        password: Password | None = None,
    ) -> User:
        account = LoginId(login_id)
        ensure_not_reserved_login_id(account)
        async with self._uow_factory() as uow:
            local = await current_mode(uow) is AuthMode.LOCAL
        profile = {
            "display_name": normalize_name(display_name, required=local),
            "email": normalize_email(email),
            "phone": normalize_phone(phone),
        }
        password_hash = await self._hash(account, password, local=local)
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()
            if local:
                await ensure_local_mode(uow)
            user = User.register(
                account,
                role,
                entity_id=await new_user_id(uow.ids),
                now=self._clock.now(),
                **profile,
            )
            try:
                exists = await uow.users.get_active_by_login_id(account) is not None
            except AmbiguousLoginIdError:  # 이미 둘 이상 있다 = 중복이라는 같은 결론
                exists = True
            if exists:
                raise AlreadyExistsError("사용자", account.value)
            await uow.users.add(user)
            if password_hash is not None:
                await uow.password_hashes.save(user.id, password_hash, self._clock.now())
            await uow.commit()
        return user

    async def _hash(
        self, account: LoginId, password: Password | None, *, local: bool
    ) -> PasswordHash | None:
        if not local:
            if password is not None:
                raise InvalidValueError(AD_CREDENTIAL_NOT_ACCEPTED)
            return None
        if password is None:
            raise InvalidValueError(CREDENTIAL_REQUIRED)
        ensure_acceptable_password(password, account)
        return await self._hasher.hash(password)
