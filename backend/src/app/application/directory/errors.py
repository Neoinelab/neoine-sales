from typing import TYPE_CHECKING

from app.application.ports.directory import DirectoryUnavailableError
from app.domain.common.errors import DomainError

if TYPE_CHECKING:
    from app.application.ports.directory import VerificationStage

_STAGE_MESSAGES = {
    "connect": "AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요",
    "tls": "TLS 연결에 실패했습니다. 보안 연결(SSL/StartTLS) 방식과 포트를 확인하세요",
    "service_bind": "바인드 계정으로 AD에 로그인하지 못했습니다. 계정과 비밀번호를 확인하세요",
    "base_dn": (
        "AD에서 Base DN(defaultNamingContext)을 찾지 못했습니다. 바인드 계정 권한을 확인하세요"
    ),
    "search": "사용자 조회에 실패했습니다. 사용자 필터를 확인하세요",
    "bind": "AD 인증에 실패했습니다. 관리자 비밀번호를 확인하세요",
}


class DirectoryVerificationError(DomainError):
    """AD 설정을 확인하지 못했다. 실패 단계와 사용자용 안내만 담는다(원인 문구·비밀번호 제외)."""

    def __init__(self, stage: VerificationStage, message: str | None = None) -> None:
        text = message or _STAGE_MESSAGES.get(str(stage), "AD 설정을 확인하지 못했습니다")
        super().__init__(text)
        self.stage = stage
        self.message = text


class DirectoryCredentialUnreadableError(DirectoryUnavailableError):
    """저장된 바인드 비밀번호를 풀 수 없다(암호화 키 변경·손상). 메시지는 고정이다."""

    def __init__(self) -> None:
        super().__init__("저장된 바인드 비밀번호를 읽을 수 없습니다")
