from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, SecretStr

from app.domain.auth.credentials import PASSWORD_MAX
from app.domain.auth.principal import Role
from app.web.schemas.common import Page, RequestModel
from app.web.schemas.password_field import to_new_password
from app.web.schemas.profile_changes import ProfileChangesRequest
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef

if TYPE_CHECKING:
    from app.application.user.delete_user import DeleteOutcome
    from app.domain.auth.credentials import Password
    from app.domain.user.entities import User


class UserRequest(RequestModel):
    """등록 본문. 비밀번호는 local 모드에서만 받는다(AD는 422). 값 검증은 도메인이 한다."""

    login_id: str
    role: Role
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    password: SecretStr | None = Field(default=None, max_length=PASSWORD_MAX)

    def to_password(self) -> Password | None:
        if self.password is None:
            return None
        return to_new_password(self.password, "password")


class UserProfileRequest(ProfileChangesRequest):
    """admin의 사용자 정보 수정 본문(아이디·역할·비밀번호는 받지 않는다)."""


class UserPasswordRequest(RequestModel):
    """admin의 비밀번호 재설정 본문."""

    password: SecretStr = Field(max_length=PASSWORD_MAX)

    def to_password(self) -> Password:
        return to_new_password(self.password, "password")


class UserRoleRequest(RequestModel):
    """역할 변경 본문. 다음 요청부터 적용되며 세션은 유지된다."""

    role: Role


class UserResponse(BaseModel):
    id: int
    login_id: str
    role: Role
    display_name: str | None
    email: str | None
    phone: str | None
    created_at: ServerDateTime
    last_login_at: ServerDateTime | None
    status: Literal["active", "resigned"]
    deleted_at: ServerDateTime | None

    @classmethod
    def from_entity(cls, user: User) -> UserResponse:
        return cls(
            id=user.id,
            login_id=user.login_id.value,
            role=user.role,
            display_name=user.display_name,
            email=user.email,
            phone=user.phone,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            status="active" if user.is_active else "resigned",
            deleted_at=user.deleted_at,
        )


UserPage = Page[UserResponse]


class UserOptionPage(BaseModel):
    """선택 UI용 후보 전체. 조건에 맞는 사용자를 모두 돌려주므로 페이징 필드가 없다."""

    items: list[UserRef]


class DeleteUserResponse(BaseModel):
    """outcome: 연결된 데이터가 없어 완전히 삭제(deleted) 또는 있어서 퇴사 처리(resigned)."""

    outcome: Literal["deleted", "resigned"]

    @classmethod
    def from_outcome(cls, outcome: DeleteOutcome) -> DeleteUserResponse:
        return cls(outcome=outcome.value)
