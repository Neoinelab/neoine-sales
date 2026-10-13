from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError


class DealNotFoundError(NotFoundError):
    def __init__(self, deal_id: object) -> None:
        super().__init__("Deal", deal_id)


class DuplicateDealCodeError(AlreadyExistsError):
    def __init__(self, code: object) -> None:
        super().__init__("Deal Code", code)


class DealInUseError(InvalidStateError):
    """활동 또는 단계 변경 이력이 있는 Deal은 삭제할 수 없다."""

    def __init__(self, deal_id: object) -> None:
        super().__init__(f"활동 또는 단계 변경 이력이 있어 삭제할 수 없습니다: {deal_id}")
