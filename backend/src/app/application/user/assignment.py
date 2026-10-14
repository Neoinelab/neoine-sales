"""담당자·활동자로 새로 지정하는 사용자가 재직 중인지 확인한다."""

from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidReferenceError

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.user.value_objects import UserId


async def ensure_assignable(
    uow: UnitOfWork, user_id: UserId, *, unchanged_from: UserId | None = None
) -> None:
    """재직 사용자가 아니면(퇴사·없음) InvalidReferenceError.

    수정에서 기존 값과 같은 id를 그대로 두면(unchanged_from) 퇴사자여도 검증하지 않는다.
    통과하면 삭제와의 경쟁을 막도록 users 행이 잠긴다(lock_assignable).
    """
    if unchanged_from is not None and user_id == unchanged_from:
        return
    if not await uow.users.lock_assignable(user_id):
        raise InvalidReferenceError("사용자", user_id)
