from pydantic import BaseModel, Field, SecretStr

from app.application.account.get_my_profile import MyProfile
from app.domain.auth.credentials import PASSWORD_MAX
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.web.schemas.common import RequestModel
from app.web.schemas.profile_changes import ProfileChangesRequest


class EditableFlags(BaseModel):
    """항목별 수정 가능 여부(전화는 두 모드 모두 true)."""

    display_name: bool
    email: bool
    phone: bool
    password: bool


class MyProfileResponse(BaseModel):
    id: int
    login_id: str
    role: Role
    display_name: str | None
    email: str | None
    phone: str | None
    auth_mode: AuthMode
    editable: EditableFlags

    @classmethod
    def from_profile(cls, profile: MyProfile) -> MyProfileResponse:
        user = profile.user
        return cls(
            id=user.id,
            login_id=user.login_id.value,
            role=user.role,
            display_name=user.display_name,
            email=user.email,
            phone=user.phone,
            auth_mode=profile.mode,
            editable=EditableFlags(
                display_name=profile.can_edit_name_email,
                email=profile.can_edit_name_email,
                phone=True,
                password=profile.can_change_password,
            ),
        )


class MyProfileRequest(ProfileChangesRequest):
    pass


class MyPasswordRequest(RequestModel):
    current_password: SecretStr = Field(max_length=PASSWORD_MAX)
    new_password: SecretStr = Field(max_length=PASSWORD_MAX)
