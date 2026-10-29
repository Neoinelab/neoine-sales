from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.user.errors import UserInUseError
from app.domain.user.policy import ensure_deletable
from app.domain.user.value_objects import UserDeleteReason

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.auth.principal import Principal
    from app.domain.user.value_objects import UserId


class DeleteOutcome(StrEnum):
    DELETED = "deleted"  # 연결된 데이터가 없어 물리 삭제
    RESIGNED = "resigned"  # 연결된 데이터가 있어 퇴사 처리(행 보존)


class DeleteUser:
    """사용자를 삭제한다. 다른 데이터가 참조하면 퇴사 처리하고, 없으면 물리 삭제한다.

    어느 쪽이든 세션 행과 대체 로그인용 비밀번호 해시는 모두 지우고
    자기 자신·마지막 admin 보호를 똑같이 적용한다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self,
        *,
        user_id: UserId,
        actor: Principal,
        reason: UserDeleteReason = UserDeleteReason.RESIGNED,
    ) -> DeleteOutcome:
        async with self._uow_factory() as uow:
            await uow.users.lock_roster()  # 잠금 순서: roster -> 대상 users 행
            target = await uow.users.get_for_update(user_id)
            ensure_deletable(
                target,
                actor_user_id=actor.user_id,
                active_admin_count=await uow.users.count_active_admins(),
            )
            await uow.sessions.delete_all_for_user(user_id)
            await uow.password_hashes.delete(user_id)
            outcome = await self._remove(uow, user_id, reason)
            await uow.commit()
        return outcome

    async def _remove(
        self, uow: UnitOfWork, user_id: UserId, reason: UserDeleteReason
    ) -> DeleteOutcome:
        if not await uow.users.has_links(user_id):
            try:
                await uow.users.delete(user_id)
            except UserInUseError:  # has_links가 놓친 경쟁 연결을 FK가 잡음 -> 퇴사로 전환
                pass
            else:
                return DeleteOutcome.DELETED
        user = await uow.users.get_for_update(user_id)
        user.resign(self._clock.now(), reason)
        await uow.users.update(user)
        return DeleteOutcome.RESIGNED
