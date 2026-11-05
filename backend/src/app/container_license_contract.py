"""라이선스 계약 유스케이스 조립 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

from app.application.license_contract.delete_license_contract import DeleteLicenseContract
from app.application.license_contract.end_license_contract import EndLicenseContract
from app.application.license_contract.get_license_contract import GetLicenseContract
from app.application.license_contract.issue_license import IssueLicense
from app.application.license_contract.list_license_contracts import ListLicenseContracts
from app.application.license_contract.renew_license import RenewLicense
from app.application.license_contract.update_license_contract import UpdateLicenseContract
from app.application.license_contract_attachment.delete_contract_attachment import (
    DeleteContractAttachment,
)
from app.application.license_contract_attachment.download_contract_attachment import (
    DownloadContractAttachment,
)
from app.application.license_contract_attachment.get_contract_attachment import (
    GetContractAttachment,
)
from app.application.license_contract_attachment.list_contract_attachments import (
    ListContractAttachments,
)
from app.application.license_contract_attachment.upload_contract_attachment import (
    UploadContractAttachment,
)

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.file_storage import FileStorage
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class LicenseContractUseCases:
    _uow: UnitOfWorkFactory
    _clock: Clock
    _file_storage: FileStorage

    def list_license_contracts(self) -> ListLicenseContracts:
        return ListLicenseContracts(self._uow)

    def get_license_contract(self) -> GetLicenseContract:
        return GetLicenseContract(self._uow)

    def update_license_contract(self) -> UpdateLicenseContract:
        return UpdateLicenseContract(self._uow, self._clock)

    def issue_license(self) -> IssueLicense:
        return IssueLicense(self._uow, self._clock)

    def renew_license(self) -> RenewLicense:
        return RenewLicense(self._uow, self._clock)

    def end_license_contract(self) -> EndLicenseContract:
        return EndLicenseContract(self._uow, self._clock)

    def delete_license_contract(self) -> DeleteLicenseContract:
        return DeleteLicenseContract(self._uow, self._file_storage)

    def list_contract_attachments(self) -> ListContractAttachments:
        return ListContractAttachments(self._uow)

    def get_contract_attachment(self) -> GetContractAttachment:
        return GetContractAttachment(self._uow)

    def upload_contract_attachment(self) -> UploadContractAttachment:
        return UploadContractAttachment(self._uow, self._clock, self._file_storage)

    def download_contract_attachment(self) -> DownloadContractAttachment:
        return DownloadContractAttachment(self._uow, self._file_storage)

    def delete_contract_attachment(self) -> DeleteContractAttachment:
        return DeleteContractAttachment(self._uow, self._file_storage)
