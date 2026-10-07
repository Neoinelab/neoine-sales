from app.domain.common.errors import InvalidStateError, NotFoundError


class CustomerNotFoundError(NotFoundError):
    def __init__(self, customer_id: object) -> None:
        super().__init__("고객", customer_id)


class CustomerInUseError(InvalidStateError):
    """진행 중인(삭제되지 않은) Deal이 참조하는 고객은 삭제할 수 없다."""

    def __init__(self, customer_id: object) -> None:
        super().__init__(f"진행 중인 Deal이 있는 고객은 삭제할 수 없습니다: {customer_id}")
