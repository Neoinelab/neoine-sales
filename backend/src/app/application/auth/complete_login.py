import hmac
from typing import TYPE_CHECKING

from app.domain.auth.errors import AccessDeniedError, AuthenticationError
from app.domain.auth.principal import Principal

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession, IssueSession
    from app.application.auth.login_state import LoginStateCodec
    from app.application.auth.role_mapping import RoleMapper
    from app.application.ports.identity_provider import IdentityProvider


class CompleteLogin:
    """IdP에서 돌아온 사용자를 검증하고 세션을 발급한다.

    state가 맞지 않으면 IdP를 호출하지 않는다(CSRF 방어). 매핑된 그룹이 없으면 AccessDeniedError.
    """

    def __init__(
        self,
        idp: IdentityProvider,
        codec: LoginStateCodec,
        mapper: RoleMapper,
        issue_session: IssueSession,
    ) -> None:
        self._idp = idp
        self._codec = codec
        self._mapper = mapper
        self._issue_session = issue_session

    async def execute(self, *, code: str, state: str, pending_token: str | None) -> IssuedSession:
        if not pending_token:
            raise AuthenticationError("로그인 요청 정보가 없습니다. 다시 시도하세요")
        pending = self._codec.decode(pending_token)
        if not hmac.compare_digest(pending.state.encode(), state.encode()):
            raise AuthenticationError("로그인 요청이 일치하지 않습니다. 다시 시도하세요")
        identity = await self._idp.complete(
            code=code, code_verifier=pending.code_verifier, nonce=pending.nonce
        )
        role = self._mapper.map(identity.groups)
        if role is None:
            raise AccessDeniedError("이 시스템을 사용할 권한이 없습니다")
        principal = Principal(identity.subject, identity.email, identity.name, role)
        return await self._issue_session.execute(principal)
