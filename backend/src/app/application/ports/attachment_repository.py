from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.attachment.entities import Attachment
    from app.domain.attachment.values import AttachmentId, FileName
    from app.domain.deal.code import DealCode


class AttachmentRepository(Protocol):
    async def add(self, attachment: Attachment) -> None:
        """없는 Deal이면 DealNotFoundError, 같은 (Deal, 이름)이 있으면
        AttachmentNameTakenError.

        두 경우 모두 이후에도 같은 트랜잭션을 계속 쓸 수 있어야 한다.
        """
        ...

    async def get(self, attachment_id: AttachmentId) -> Attachment:
        """없으면 AttachmentNotFoundError."""
        ...

    async def find_by_name(self, deal_code: DealCode, file_name: FileName) -> Attachment | None:
        """같은 Deal의 같은 이름(대소문자 구분). 없으면 None."""
        ...

    async def list_by_deal(self, deal_code: DealCode) -> Sequence[Attachment]:
        """업로드 시각 내림차순, 같으면 id 내림차순."""
        ...

    async def update(self, attachment: Attachment) -> None:
        """내용 필드만 저장한다.

        description·size·mime·storage_key·uploaded_by·uploaded_at·updated_at. 없으면 NotFound.
        """
        ...

    async def delete(self, attachment_id: AttachmentId) -> None:
        """없으면 AttachmentNotFoundError."""
        ...
