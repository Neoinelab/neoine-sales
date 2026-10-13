from app.domain.common.errors import InvalidStateError, NotFoundError


class PartnerNotFoundError(NotFoundError):
    def __init__(self, partner_id: object) -> None:
        super().__init__("파트너", partner_id)


class PartnerInUseError(InvalidStateError):
    """참조하는 Deal이 있는 파트너는 삭제할 수 없다."""

    def __init__(self, partner_id: object) -> None:
        super().__init__(f"이 파트너를 참조하는 Deal이 있어 삭제할 수 없습니다: {partner_id}")
