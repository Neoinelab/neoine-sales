from app.domain.auth.errors import AccessDeniedError
from app.domain.common.errors import InvalidStateError, NotFoundError

NOT_ISSUED_ONLY = "미발급 계약만 발급할 수 있습니다."
ISSUED_ONLY = "발급 상태 계약만 갱신할 수 있습니다."
ALREADY_ENDED = "이미 종료된 계약입니다."
WON_EXIT_BLOCKED = (
    "발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. "
    "계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요."
)
DEAL_NOT_WON = "Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다."


class LicenseContractNotFoundError(NotFoundError):
    def __init__(self, contract_id: object) -> None:
        super().__init__("라이선스 계약", contract_id, message="라이선스 계약을 찾을 수 없습니다.")


class ContractAttachmentNotFoundError(NotFoundError):
    def __init__(self, attachment_id: object) -> None:
        super().__init__("계약 첨부 파일", attachment_id, message="첨부 파일을 찾을 수 없습니다.")


class LicenseAlreadyIssuedError(InvalidStateError):
    def __init__(self) -> None:
        super().__init__("이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다.")


class ContractTransitionError(InvalidStateError):
    """현재 상태에서 할 수 없는 발급·갱신·종료. 문구는 위 상수 셋 중 하나다."""


class WonExitBlockedError(InvalidStateError):
    def __init__(self) -> None:
        super().__init__(WON_EXIT_BLOCKED)


class LicenseRequiresWonError(InvalidStateError):
    def __init__(self) -> None:
        super().__init__(DEAL_NOT_WON)


class ContractDeleteForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("계약 삭제는 관리자만 할 수 있습니다.")
