import logging
from typing import TYPE_CHECKING

from app.application.auth.mode import current_mode
from app.domain.auth.mode import AuthMode
from app.domain.directory.errors import AuthModeUnreadableError, DirectoryLoginDomainMissingError

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory

logger = logging.getLogger(__name__)


class CheckAdLoginDomain:
    """기동 검사(AU-R7c): 인증 방식이 AD 연동인데 서버에 AD 로그인 도메인이 없으면 실패한다.

    인증 방식은 effective mode(저장값, 없으면 admin·AD 설정이 있는 기존 시스템은 AD)로 판단한다.
    DB는 읽기만 하고, 오류에는 환경변수 값·DB 주소·AD 설정 값을 싣지 않는다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, *, domain_configured: bool) -> None:
        self._uow_factory = uow_factory
        self._domain_configured = domain_configured

    async def execute(self) -> None:
        try:
            async with self._uow_factory() as uow:
                mode = await current_mode(uow)
        except Exception as error:
            # DB 오류 문구에는 주소·계정이 있을 수 있어 종류만 남긴다
            logger.critical("기동 검사 중 인증 방식을 읽지 못했습니다 (%s)", type(error).__name__)
            raise AuthModeUnreadableError from None
        if mode is AuthMode.AD and not self._domain_configured:
            raise DirectoryLoginDomainMissingError
