"""첨부 테스트용 생성 도우미(P2b R2). 첨부 도메인 모듈은 사용 시점에 가져온다(수집 보호)."""

from typing import TYPE_CHECKING
from uuid import uuid4

from tests.factories import NOW, make_deal_code
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.attachment.entities import Attachment

    from app.domain.attachment.values import AttachmentId, FileName
    from app.domain.deal.code import DealCode
    from app.domain.user.value_objects import UserId


def make_file_name(raw: str = "a.pdf") -> FileName:
    from app.domain.attachment.values import FileName  # noqa: PLC0415

    return FileName.parse(raw)


def make_attachment(  # noqa: PLR0913 - 첨부 필드가 모두 독립적인 선택지
    now: datetime = NOW,
    *,
    deal_code: DealCode | None = None,
    name: str = "a.pdf",
    description: str = "",
    size: int = 10,
    mime: str = "application/pdf",
    storage_key: str | None = None,
    uploaded_by: UserId = ACTOR_ID,
    entity_id: AttachmentId | None = None,
) -> Attachment:
    """저장하지 않은 첨부(`Attachment.upload`). 업로드 시각 = now, 저장 키 기본은 uuid4 hex."""
    from app.domain.attachment.entities import Attachment  # noqa: PLC0415

    from app.domain.attachment.values import UploadCandidate  # noqa: PLC0415

    return Attachment.upload(
        deal_code=deal_code or make_deal_code(),
        candidate=UploadCandidate.check(file_name=name, description=description, size=size),
        size=size,
        mime=mime,
        storage_key=storage_key or uuid4().hex,
        uploaded_by=uploaded_by,
        now=now,
        entity_id=entity_id,
    )
