"""local 모드 로그인: 저장된 비밀번호 해시로 인증한다. AD는 부르지 않는다."""

from typing import TYPE_CHECKING

from app.application.auth.active_user import find_active_user
from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.errors import AuthenticationError
from app.domain.user.errors import UserNotFoundError

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.domain.auth.credentials import LoginId, Password
    from app.domain.auth.principal import Principal


class LocalLogin:
    """없는 아이디·퇴사자·해시 없음·불일치는 같은 LOGIN_FAILED이고 같은 비용(verify(None) 더미)이다.

    scrypt 검증 동안 DB 트랜잭션을 잡지 않도록 읽기 -> 검증 -> 다시 확인·기록 순서로 나눈다.
    시도 제한은 호출한 쪽이 맡는다(실패하면 선점한 시도가 실패 1회로 남는다).
    """

    def __init__(self, deps: AuthDeps) -> None:
        self._deps = deps

    async def execute(self, account: LoginId, password: Password) -> Principal:
        async with self._deps.uow_factory() as uow:
            user = await find_active_user(uow.users, account, purpose="로그인")
            stored = None if user is None else await uow.password_hashes.get(user.id)
        matched = await self._deps.hasher.verify(password, stored)
        if user is None or not matched:
            raise AuthenticationError(LOGIN_FAILED)
        async with self._deps.uow_factory() as uow:
            current = await find_active_user(uow.users, account, purpose="로그인")
            if (
                current is None
                or current.id != user.id
                or await uow.password_hashes.get(current.id) != stored
            ):  # 검증 중 퇴사·교체·해시 변경
                raise AuthenticationError(LOGIN_FAILED)
            current.record_password_login(self._deps.clock.now())
            try:
                await uow.users.update(current)
            except UserNotFoundError:  # 조회와 갱신 사이에 삭제됨
                raise AuthenticationError(LOGIN_FAILED) from None
            await uow.commit()
        return current.to_principal()
