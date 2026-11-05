from typing import TYPE_CHECKING

from app.application.attachment.storage_cleanup import remove_file_quietly
from app.application.ports.file_storage import StoredFileLocation
from app.application.storage.folders import license_contract_folder

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.license_contract.values import ContractAttachmentId


class DeleteContractAttachment:
    """계약 첨부를 지운다(Deal 이력·수정 시각은 건드리지 않는다). 없으면 404가 권한 오류보다 먼저다.

    같은 계약의 첨부 변경과 직렬화하려고 계약 행을 먼저 잠근다(업로드와 같은 순서).
    디스크 파일 하나만 커밋 뒤에 지운다(계약 폴더는 남긴다). 저장 위치 설정이 없으면 파일은 두고
    행만 지운다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def execute(self, attachment_id: ContractAttachmentId, actor: Actor) -> None:
        async with self._uow_factory() as uow:
            attachment = await uow.license_contract_attachments.get(attachment_id)
            await uow.license_contracts.get(attachment.contract_id, for_update=True)
            attachment = await uow.license_contract_attachments.get(attachment_id)
            refs = await uow.users.get_refs([attachment.uploaded_by])
            attachment.ensure_deletable_by(actor.user_id, actor.role, refs[attachment.uploaded_by])
            settings = await uow.storage_settings.get()
            await uow.license_contract_attachments.delete(attachment_id)
            await uow.commit()
        if settings is not None:
            location = StoredFileLocation(
                folder=license_contract_folder(attachment.contract_id), key=attachment.storage_key
            )
            await remove_file_quietly(self._storage, settings.path, location)
