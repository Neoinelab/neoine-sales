from app.domain.auth.errors import AccessDeniedError
from app.domain.common.errors import NotFoundError


class DealActionNotFoundError(NotFoundError):
    def __init__(self, action_id: object) -> None:
        super().__init__("Action", action_id, message="Action을 찾을 수 없습니다.")


class DealActionEditForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("본인 Action 또는 admin만 수정할 수 있습니다.")


class DealActionDeleteForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("본인 Action 또는 admin만 삭제할 수 있습니다.")
