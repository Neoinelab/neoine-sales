from app.domain.common.errors import NotFoundError


class PartnerNotFoundError(NotFoundError):
    def __init__(self, partner_id: object) -> None:
        super().__init__("파트너", partner_id)
