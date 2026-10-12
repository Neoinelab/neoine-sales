from typing import TYPE_CHECKING

from app.domain.common.errors import DomainError

if TYPE_CHECKING:
    from app.application.ports.directory import VerificationStage

_STAGE_MESSAGES = {
    "connect": "AD 서버에 연결하지 못했습니다. 주소·포트·방화벽을 확인하세요",
    "tls": "TLS 연결에 실패했습니다. CA 인증서와 StartTLS 설정을 확인하세요",
    "bind": "AD 인증에 실패했습니다. 바인드 템플릿과 비밀번호를 확인하세요",
    "search": "사용자 조회에 실패했습니다. Base DN과 검색 필터를 확인하세요",
}


class DirectoryVerificationError(DomainError):
    """AD 설정을 확인하지 못했다. 실패 단계와 사용자용 안내만 담는다(원인 문구·비밀번호 제외)."""

    def __init__(self, stage: VerificationStage, message: str | None = None) -> None:
        text = message or _STAGE_MESSAGES.get(str(stage), "AD 설정을 확인하지 못했습니다")
        super().__init__(text)
        self.stage = stage
        self.message = text
