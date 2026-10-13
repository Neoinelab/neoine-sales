from app.domain.common.errors import InvalidStateError, NotFoundError


class CustomerNotFoundError(NotFoundError):
    def __init__(self, customer_id: object) -> None:
        super().__init__("고객", customer_id)


class CustomerInUseError(InvalidStateError):
    """참조하는 Deal이 있는 고객은 삭제할 수 없다."""

    def __init__(self, customer_id: object) -> None:
        super().__init__(f"이 고객을 참조하는 Deal이 있어 삭제할 수 없습니다: {customer_id}")
