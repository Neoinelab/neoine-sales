"""AttachmentRepository Port의 InMemory 구현(Fake). SqlAttachmentRepository와 같게 동작한다.

- add: 소속 Deal이 없으면 DealNotFoundError, 같은 Deal에 같은 이름(대소문자 구분)이 있으면
  AttachmentNameTakenError. 실패해도 이후 호출을 계속 쓸 수 있다(SAVEPOINT 모사).
- list_by_deal: 업로드 시각 내림차순, 같으면 id 내림차순. update는 description·size·mime·
  storage_key·uploaded_by·uploaded_at·updated_at만 저장한다(id·file_name·deal_code는 불변).
  Deal 삭제는 첨부를 함께 지운다(CASCADE, `remove_of_deal`).

도메인 모듈은 사용 시점에 가져온다(첨부 구현 전에도 이 Fake를 쓰는 다른 테스트가 수집된다).
"""

import copy
from typing import TYPE_CHECKING, Any, cast

from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.attachment.entities import Attachment
    from app.domain.attachment.values import AttachmentId, FileName
    from app.domain.common.errors import NotFoundError
    from app.domain.deal.code import DealCode


def _not_found(attachment_id: object) -> NotFoundError:
    from app.domain.attachment.errors import AttachmentNotFoundError  # noqa: PLC0415

    return AttachmentNotFoundError(attachment_id)


class FakeAttachmentRepository(InMemoryStore[Any]):
    def __init__(self) -> None:
        super().__init__("attachment", _not_found)
        self._deals: Any = None

    def wire(self, *, deals: Any) -> None:  # noqa: ANN401
        """소속 Deal 존재 확인(FK 모사)에 쓸 저장소를 연결한다."""
        self._deals = deals

    def remove_of_deal(self, code: DealCode) -> None:
        """Deal 삭제의 CASCADE."""
        for attachment_id in [i for i, a in self._items.items() if a.deal_code == code]:
            del self._items[attachment_id]

    async def add(self, attachment: Attachment) -> None:
        from app.domain.attachment.errors import AttachmentNameTakenError  # noqa: PLC0415
        from app.domain.deal.errors import DealNotFoundError  # noqa: PLC0415

        if self._deals is not None and attachment.deal_code not in self._deals._items:
            raise DealNotFoundError(attachment.deal_code.value)
        if await self.find_by_name(attachment.deal_code, attachment.file_name) is not None:
            raise AttachmentNameTakenError(attachment.file_name.value)
        self._insert(attachment)

    async def get(self, attachment_id: AttachmentId) -> Attachment:
        return cast("Attachment", self._fetch(attachment_id))

    async def find_by_name(self, deal_code: DealCode, file_name: FileName) -> Attachment | None:
        for item in self._items.values():
            if item.deal_code == deal_code and item.file_name == file_name:
                return cast("Attachment", copy.deepcopy(item))
        return None

    async def list_by_deal(self, deal_code: DealCode) -> Sequence[Attachment]:
        found = [a for a in self._items.values() if a.deal_code == deal_code]
        found.sort(key=lambda a: (a.uploaded_at, str(a.id)), reverse=True)
        return [copy.deepcopy(a) for a in found]

    async def update(self, attachment: Attachment) -> None:
        stored = self._fetch(attachment.id)
        for name in (
            "description",
            "size",
            "mime",
            "storage_key",
            "uploaded_by",
            "uploaded_at",
            "updated_at",
        ):
            setattr(stored, name, getattr(attachment, name))
        self._replace(stored)

    async def delete(self, attachment_id: AttachmentId) -> None:
        self._remove(attachment_id)
