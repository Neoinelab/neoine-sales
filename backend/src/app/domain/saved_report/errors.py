from app.domain.auth.errors import AccessDeniedError
from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError


class ReportNotFoundError(NotFoundError):
    """없거나 볼 수 없는 리포트. 두 경우를 구분하지 않는다(존재를 숨긴다)."""

    def __init__(self, report_id: object) -> None:
        super().__init__("리포트", report_id, message="리포트를 찾을 수 없습니다.")


class DuplicateReportNameError(AlreadyExistsError):
    """대소문자 무시로 같은 이름의 리포트가 이미 있다(만든 사람·공개 범위와 무관)."""

    def __init__(self, name: object) -> None:
        super().__init__("리포트 이름", name, message="같은 이름의 리포트가 이미 있습니다.")


class ReportEditConflictError(InvalidStateError):
    def __init__(self) -> None:
        super().__init__(
            "다른 사용자가 먼저 이 리포트를 저장했습니다."
            " 다시 불러온 뒤 수정하거나 다른 이름으로 저장하세요."
        )


class ReportDeleteForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("리포트를 만든 사람 또는 admin만 삭제할 수 있습니다.")


class ReportVisibilityForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다.")


class ReportEditForbiddenError(AccessDeniedError):
    """보이는 리포트는 모두 수정할 수 있어 지금 규칙으로는 닿지 않는 방어용 오류."""

    def __init__(self) -> None:
        super().__init__("이 리포트를 수정할 권한이 없습니다.")
