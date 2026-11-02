from app.domain.user.profile import UNSET, ProfileChanges
from app.web.schemas.common import RequestModel


class ProfileChangesRequest(RequestModel):
    """이름·이메일·전화 변경 본문. 보낸 키만 바꾸고(PATCH) null은 비운다. 값 검증은 도메인."""

    display_name: str | None = None
    email: str | None = None
    phone: str | None = None

    def to_changes(self) -> ProfileChanges:
        sent = self.model_fields_set
        return ProfileChanges(
            display_name=self.display_name if "display_name" in sent else UNSET,
            email=self.email if "email" in sent else UNSET,
            phone=self.phone if "phone" in sent else UNSET,
        )
