from app.domain.common.errors import NotFoundError


class CustomerNotFoundError(NotFoundError):
    def __init__(self, customer_id: object) -> None:
        super().__init__("고객", customer_id)
