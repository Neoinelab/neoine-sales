from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserDeleteReason
from app.web.schemas.common import Page, RequestModel
from app.web.schemas.user_ref import UserRef, ref_of

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.application.user.delete_user import DeleteOutcome
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef


class UserRequest(RequestModel):
    """등록 본문. 비밀번호는 받지 않는다(AD가 인증). 아이디 형식 검증은 도메인(LoginId)이 한다."""

    login_id: str
    role: Role


class UserResponse(BaseModel):
    id: str
    login_id: str
    role: Role
    display_name: str | None
    email: str | None
    created_at: datetime
    created_by: UserRef
    last_login_at: datetime | None
    status: Literal["active", "resigned"]
    deleted_at: datetime | None
    delete_reason: UserDeleteReason | None

    @classmethod
    def from_entity(cls, user: User, refs: Mapping[UserId, DomainUserRef]) -> UserResponse:
        return cls(
            id=str(user.id),
            login_id=user.login_id.value,
            role=user.role,
            display_name=user.display_name,
            email=user.email,
            created_at=user.created_at,
            created_by=ref_of(refs, user.created_by_user_id),
            last_login_at=user.last_login_at,
            status="active" if user.is_active else "resigned",
            deleted_at=user.deleted_at,
            delete_reason=user.delete_reason,
        )


UserPage = Page[UserResponse]
UserOptionPage = Page[UserRef]


class DeleteUserResponse(BaseModel):
    """outcome: 연결된 데이터가 없어 완전히 삭제(deleted) 또는 있어서 퇴사 처리(resigned)."""

    outcome: Literal["deleted", "resigned"]

    @classmethod
    def from_outcome(cls, outcome: DeleteOutcome) -> DeleteUserResponse:
        return cls(outcome=outcome.value)
