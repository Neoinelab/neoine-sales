from app.domain.common.errors import InvalidStateError, NotFoundError


class PartnerNotFoundError(NotFoundError):
    def __init__(self, partner_id: object) -> None:
        super().__init__("파트너", partner_id)


class PartnerInUseError(InvalidStateError):
    """진행 중인(삭제되지 않은) Deal이 참조하는 파트너는 삭제할 수 없다."""

    def __init__(self, partner_id: object) -> None:
        super().__init__(f"진행 중인 Deal이 있는 파트너는 삭제할 수 없습니다: {partner_id}")
