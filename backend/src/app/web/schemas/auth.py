from pydantic import BaseModel, Field, SecretStr

from app.application.auth.auth_status import AuthStatus
from app.domain.auth.credentials import PASSWORD_MAX, Password
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.principal import Principal, Role
from app.domain.common.errors import InvalidValueError
from app.web.schemas.common import RequestModel

LOGIN_FAILED_DETAIL = "아이디 또는 비밀번호가 올바르지 않습니다"
LOGIN_ID_REQUEST_MAX = 128


class PrincipalResponse(BaseModel):
    subject: str
    email: str | None
    name: str
    role: Role

    @classmethod
    def from_principal(cls, principal: Principal) -> PrincipalResponse:
        return cls(
            subject=principal.subject,
            email=principal.email,
            name=principal.name,
            role=principal.role,
        )


class AuthConfigResponse(BaseModel):
    dev_login: bool
    directory_login: bool
    needs_directory_setup: bool
    needs_admin_setup: bool

    @classmethod
    def from_status(cls, status: AuthStatus, *, dev_login: bool) -> AuthConfigResponse:
        return cls(
            dev_login=dev_login,
            directory_login=status.directory_configured,
            needs_directory_setup=status.needs_directory_setup,
            needs_admin_setup=status.needs_admin_setup,
        )


class DevLoginRequest(RequestModel):
    role: Role


class CredentialsRequest(RequestModel):
    """아이디·비밀번호 본문. 비밀번호는 SecretStr이라 repr·로그에 값이 나오지 않는다."""

    login_id: str = Field(max_length=LOGIN_ID_REQUEST_MAX)
    password: SecretStr = Field(max_length=PASSWORD_MAX)

    def to_password(self) -> Password:
        """빈 값·NUL은 다른 로그인 실패와 같은 401로 처리한다(AD로 보내지 않는다)."""
        try:
            return Password(self.password.get_secret_value())
        except InvalidValueError:
            raise AuthenticationError(LOGIN_FAILED_DETAIL) from None


class LoginRequest(CredentialsRequest):
    pass


class SetupAdminRequest(CredentialsRequest):
    pass
