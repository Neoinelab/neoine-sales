from dataclasses import dataclass

from app.domain.auth.errors import AccessDeniedError
from app.domain.common.errors import InvalidValueError, NotFoundError

COMPANY_NOT_FOUND = "등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요."
DEAL_NOT_FOUND = "Deal을 찾을 수 없습니다. 목록에서 다시 선택하세요."
DEAL_NOT_LINKED = "선택한 파트너와 연결된 Deal이 아닙니다."
NO_ITEMS = "입력한 미팅이 없습니다."


class PartnerMeetingNotFoundError(NotFoundError):
    def __init__(self, meeting_id: object) -> None:
        super().__init__("미팅 기록", meeting_id, message="미팅 기록을 찾을 수 없습니다.")


class PartnerMeetingEditForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("본인 미팅 기록 또는 admin만 수정할 수 있습니다.")


class PartnerMeetingDeleteForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("본인 미팅 기록 또는 admin만 삭제할 수 있습니다.")


@dataclass(frozen=True, slots=True)
class MeetingIssue:
    """입력의 위반 한 건. location은 요청 안의 위치(예: ("items", 1, "deal_code"))다."""

    location: tuple[str | int, ...]
    message: str


class MeetingInputError(InvalidValueError):
    """미팅 입력의 위반 모음. 문구는 첫 위반이다."""

    def __init__(self, issues: tuple[MeetingIssue, ...]) -> None:
        if not issues:
            raise ValueError("위반이 하나 이상 있어야 합니다")
        super().__init__(issues[0].message)
        self.issues = issues
