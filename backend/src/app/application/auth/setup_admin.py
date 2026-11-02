from typing import TYPE_CHECKING

from app.application.auth.mode import current_mode
from app.application.auth.setup_first_admin import SetupFirstAdmin
from app.application.auth.setup_first_local_admin import SetupFirstLocalAdmin
from app.domain.auth.mode import AuthMode
from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.auth.issue_session import IssuedSession, IssueSession
    from app.domain.auth.credentials import Password

AD_PROFILE_NOT_ACCEPTED = "AD 연동에서는 이름·이메일·전화번호를 입력하지 않습니다(AD 값을 씁니다)."


class SetupAdmin:
    """최초 설정 3단계 진입점: 인증 방식에 따라 local 등록 또는 AD 인증 등록으로 보낸다."""

    def __init__(self, deps: AuthDeps, issue_session: IssueSession) -> None:
        self._deps = deps
        self._local = SetupFirstLocalAdmin(deps, issue_session)
        self._directory = SetupFirstAdmin(deps, issue_session)

    async def execute(  # noqa: PLR0913 - 계정 입력, 접속 IP, 프로필 3개가 모두 의미 있다
        self,
        *,
        login_id: str,
        password: Password,
        client_ip: str,
        display_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> IssuedSession:
        async with self._deps.uow_factory() as uow:
            mode = await current_mode(uow)
        if mode is AuthMode.LOCAL:
            return await self._local.execute(
                login_id=login_id,
                password=password,
                display_name=display_name,
                email=email,
                phone=phone,
            )
        if display_name is not None or email is not None or phone is not None:
            raise InvalidValueError(AD_PROFILE_NOT_ACCEPTED)
        return await self._directory.execute(
            login_id=login_id, password=password, client_ip=client_ip
        )
