from pydantic import BaseModel

from app.domain.auth.principal import Principal, Role
from app.web.schemas.common import RequestModel


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


class CallbackQuery(BaseModel):
    """IdP가 돌려보내는 쿼리. IdP마다 부가 파라미터를 붙이므로 모르는 값은 무시한다."""

    code: str | None = None
    state: str | None = None
    error: str | None = None


class AuthConfigResponse(BaseModel):
    dev_login: bool
    oidc: bool


class DevLoginRequest(RequestModel):
    role: Role
