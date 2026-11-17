from app.domain.auth.errors import AccessDeniedError
from app.domain.common.errors import NotFoundError


class DealCommentNotFoundError(NotFoundError):
    def __init__(self, comment_id: object) -> None:
        super().__init__("Comment", comment_id, message="Comment를 찾을 수 없습니다.")


class DealCommentReadForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("Deal Owner만 Comment를 읽음 처리할 수 있습니다.")


class DealCommentDeleteForbiddenError(AccessDeniedError):
    def __init__(self) -> None:
        super().__init__("본인 Comment 또는 admin만 삭제할 수 있습니다.")
