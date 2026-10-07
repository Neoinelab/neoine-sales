from typing import TYPE_CHECKING

from app.domain.auth.principal import Principal

if TYPE_CHECKING:
    from app.application.auth.issue_session import IssuedSession, IssueSession
    from app.domain.auth.principal import Role


class DevLogin:
    """IdP 없이 로컬 개발용 사용자로 로그인한다. 켜고 끄는 것은 설정(local 전용)이 정한다."""

    def __init__(self, issue_session: IssueSession) -> None:
        self._issue_session = issue_session

    async def execute(self, role: Role) -> IssuedSession:
        principal = Principal("dev-user", "dev@local.test", f"개발 사용자({role.value})", role)
        return await self._issue_session.execute(principal)
