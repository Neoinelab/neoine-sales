"""LicenseContractAttachmentRepository Port의 InMemory 구현(Fake). SQL 구현과 같게 동작한다.

도메인 모듈은 사용 시점에 가져온다(FakeUnitOfWork가 항상 만들기 때문에 수집 보호).

계약(SQL 구현과 같다)
- add: 소속 계약이 없으면 LicenseContractNotFoundError, 같은 계약에 같은 이름(대소문자 구분)이
  있으면 AttachmentNameTakenError, 업로더 행이 없으면 InvalidReferenceError("사용자").
  실패해도 이후 호출을 계속 쓸 수 있다
- get/delete: 없으면 ContractAttachmentNotFoundError. get은 deal_code를 계약에서 읽어 채운다
- list_by_contract: 업로드 시각 내림차순, 같으면 id 내림차순
- update: description·size·mime·storage_key·uploaded_by·uploaded_at·updated_at만 저장한다
- 계약 삭제는 첨부 행을 함께 지운다(CASCADE, `remove_of_contract`)
"""

import copy
from typing import TYPE_CHECKING, Any, cast

from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.attachment.values import FileName
    from app.domain.common.errors import NotFoundError
    from app.domain.license_contract.attachment import ContractAttachment
    from app.domain.license_contract.values import ContractAttachmentId, LicenseContractId


def _not_found(attachment_id: object) -> NotFoundError:
    from app.domain.license_contract.errors import ContractAttachmentNotFoundError  # noqa: PLC0415

    return ContractAttachmentNotFoundError(attachment_id)


class FakeLicenseContractAttachmentRepository(InMemoryStore[Any]):
    def __init__(self) -> None:
        super().__init__("contract_attachment", _not_found)
        self._contracts: Any = None
        self._users: Any = None

    def wire(self, *, contracts: Any, users: Any) -> None:  # noqa: ANN401
        """소속 계약·업로더 존재 확인(FK 모사)에 쓸 저장소를 연결한다."""
        self._contracts, self._users = contracts, users

    def remove_of_contract(self, contract_id: LicenseContractId) -> None:
        """계약 삭제의 CASCADE."""
        for attachment_id in [i for i, a in self._items.items() if a.contract_id == contract_id]:
            del self._items[attachment_id]

    def count_of_contract(self, contract_id: LicenseContractId) -> int:
        return sum(1 for a in self._items.values() if a.contract_id == contract_id)

    async def add(self, attachment: ContractAttachment) -> None:
        from app.domain.attachment.errors import AttachmentNameTakenError  # noqa: PLC0415
        from app.domain.common.errors import InvalidReferenceError  # noqa: PLC0415
        from app.domain.license_contract.errors import LicenseContractNotFoundError  # noqa: PLC0415

        if attachment.contract_id not in self._contracts._items:
            raise LicenseContractNotFoundError(attachment.contract_id)
        if attachment.uploaded_by not in self._users._items:
            raise InvalidReferenceError("사용자", attachment.uploaded_by)
        if await self.find_by_name(attachment.contract_id, attachment.file_name) is not None:
            raise AttachmentNameTakenError(attachment.file_name.value)
        self._insert(attachment)

    async def get(self, attachment_id: ContractAttachmentId) -> ContractAttachment:
        return cast("ContractAttachment", self._fetch(attachment_id))

    async def find_by_name(
        self, contract_id: LicenseContractId, file_name: FileName
    ) -> ContractAttachment | None:
        for item in self._items.values():
            if item.contract_id == contract_id and item.file_name == file_name:
                return cast("ContractAttachment", copy.deepcopy(item))
        return None

    async def list_by_contract(
        self, contract_id: LicenseContractId
    ) -> Sequence[ContractAttachment]:
        found = [a for a in self._items.values() if a.contract_id == contract_id]
        found.sort(key=lambda a: (a.uploaded_at, a.id), reverse=True)
        return [copy.deepcopy(a) for a in found]

    async def update(self, attachment: ContractAttachment) -> None:
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

    async def delete(self, attachment_id: ContractAttachmentId) -> None:
        self._remove(attachment_id)
