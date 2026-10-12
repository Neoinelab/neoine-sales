from app.domain.common.errors import NotFoundError


class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: object) -> None:
        super().__init__("사용자", user_id)
