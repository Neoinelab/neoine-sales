from app.domain.common.errors import NotFoundError


class DealActionNotFoundError(NotFoundError):
    def __init__(self, action_id: object) -> None:
        super().__init__("Deal 활동", action_id)
