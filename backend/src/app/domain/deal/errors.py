"""Deal 도메인 오류. 문구는 사용자에게 그대로 나가며 기반 클래스가 HTTP 상태를 정한다."""

from app.domain.auth.errors import AccessDeniedError
from app.domain.common.errors import (
    AlreadyExistsError,
    InvalidStateError,
    InvalidValueError,
    NotFoundError,
)

SYNC_MISMATCH_MESSAGE = "Status와 Forecast의 동기화가 맞지 않습니다."
STATUS_REQUIRED_MESSAGE = "Status를 선택하세요."
FORECAST_REQUIRED_MESSAGE = "Forecast를 선택하세요."
UNKNOWN_CODE_MESSAGE = "존재하지 않는 코드입니다."


class DealNotFoundError(NotFoundError):
    def __init__(self, code: object) -> None:
        super().__init__("Deal", code, message="Deal을 찾을 수 없습니다.")


class DuplicateDealCodeError(AlreadyExistsError):
    def __init__(self, code: object) -> None:
        super().__init__("Deal code", code, message="이미 사용 중인 Deal code입니다.")


class DealCodeIssueError(InvalidStateError):
    """Deal code를 정해진 횟수 안에 발급하지 못했다(같은 날 code 충돌이 이어짐)."""

    def __init__(self) -> None:
        super().__init__("Deal code를 발급하지 못했습니다. 다시 시도하세요.")


class DealDeleteForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("본인 Deal 또는 admin만 삭제할 수 있습니다.")


class DealCodeMismatchError(InvalidValueError):
    """삭제 확인용으로 입력한 code가 Deal code와 정확히 같지 않다."""

    def __init__(self) -> None:
        super().__init__("Deal code가 일치하지 않습니다.")


class SyncMismatchError(InvalidValueError):
    """Status와 Forecast가 `contract_completed` ⇔ `won` 규칙을 어긴다."""

    def __init__(self) -> None:
        super().__init__(SYNC_MISMATCH_MESSAGE)


class UnknownCodeError(InvalidValueError):
    """없는 Status·Forecast 코드. 문구는 상황에 맞게 고른다."""

    def __init__(self, message: str = UNKNOWN_CODE_MESSAGE) -> None:
        super().__init__(message)


class InvalidBantLabelError(InvalidValueError):
    """없는 BANT Label이거나 다른 구분의 Label이다."""

    def __init__(self) -> None:
        super().__init__("BANT Label이 올바르지 않습니다.")
