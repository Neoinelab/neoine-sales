from app.domain.common.errors import AlreadyExistsError, NotFoundError


class DealNotFoundError(NotFoundError):
    def __init__(self, deal_id: object) -> None:
        super().__init__("Deal", deal_id)


class DuplicateDealCodeError(AlreadyExistsError):
    def __init__(self, code: object) -> None:
        super().__init__("Deal Code", code)
