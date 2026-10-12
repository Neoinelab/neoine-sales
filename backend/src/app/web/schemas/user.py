from datetime import datetime

from pydantic import BaseModel

from app.domain.auth.principal import Role
from app.domain.user.entities import User
from app.web.schemas.common import Page, RequestModel


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
    created_by: str
    last_login_at: datetime | None

    @classmethod
    def from_entity(cls, user: User) -> UserResponse:
        return cls(
            id=str(user.id),
            login_id=user.login_id.value,
            role=user.role,
            display_name=user.display_name,
            email=user.email,
            created_at=user.created_at,
            created_by=user.created_by,
            last_login_at=user.last_login_at,
        )


UserPage = Page[UserResponse]
