from typing import TYPE_CHECKING

from app.application.attachment.storage_cleanup import remove_folder_quietly
from app.application.storage.folders import license_contract_folder
from app.domain.license_contract.entities import LicenseContract

if TYPE_CHECKING:
    from app.application.deal.inputs import Actor
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.license_contract.values import LicenseContractId


class DeleteLicenseContract:
    """계약을 삭제한다(admin만, 상태 무관). 권한 판정이 계약 조회보다 먼저다.

    비admin은 계약 존재 여부와 무관하게 403이고 저장 위치도 읽지 않는다.
    없는 계약 404는 admin에게만 나간다.

    첨부 행은 함께 지워지고, 그 계약의 디스크 폴더는 커밋 뒤에 통째로 지운다. 저장 위치 설정이
    없으면 파일은 두고, 정리 실패는 경고 로그만 남긴다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, storage: FileStorage) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def execute(self, contract_id: LicenseContractId, actor: Actor) -> None:
        async with self._uow_factory() as uow:
            LicenseContract.ensure_deletable_by(actor.role)
            await uow.license_contracts.get(contract_id, for_update=True)
            settings = await uow.storage_settings.get()
            await uow.license_contracts.delete(contract_id)
            await uow.commit()
        if settings is not None:
            await remove_folder_quietly(
                self._storage, settings.path, license_contract_folder(contract_id)
            )
