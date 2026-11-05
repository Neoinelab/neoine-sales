"""FakeUseCases에 섞어 쓰는 라이선스 계약 유스케이스 조립(mixin).

유스케이스 모듈은 사용 시점에 가져온다(구현 전에도 FakeUseCases를 쓰는 테스트가 수집된다).
메서드 이름은 web의 `UseCaseProvider` 계약이고, 생성자 인자·execute 시그니처는 아래가 정본이다
(구현자가 따른다). 모든 클래스는 `app.application.license_contract` 또는
`app.application.license_contract_attachment` 패키지에 둔다.

계약 (클래스(생성자 인자) -> execute(...) 반환)
- ListLicenseContracts(uow_factory) -> execute(query):
  LicenseContractPage(items, total, offset, limit)
- GetLicenseContract(uow_factory) -> execute(contract_id): LicenseContractRow
- UpdateLicenseContract(uow_factory, clock) -> execute(contract_id, fields, actor): Row
- IssueLicense(uow_factory, clock) -> execute(contract_id, data: LicenseIssueInput, actor): Row
- RenewLicense(uow_factory, clock) -> execute(contract_id, data: LicenseIssueInput, actor):
  새 계약의 Row
- EndLicenseContract(uow_factory, clock) -> execute(contract_id, actor): Row
- DeleteLicenseContract(uow_factory, storage) -> execute(contract_id, actor): None
- ListContractAttachments(uow_factory) -> execute(contract_id): Sequence[ContractAttachment]
- GetContractAttachment(uow_factory) -> execute(attachment_id): ContractAttachment
- UploadContractAttachment(uow_factory, clock, storage) -> execute(contract_id, data, actor):
  UploadOutcome(재사용)
- DownloadContractAttachment(uow_factory, storage) -> execute(attachment_id):
  (ContractAttachment, OpenedFile)
- DeleteContractAttachment(uow_factory, storage) -> execute(attachment_id, actor): None
`LicenseIssueInput(fields: ContractFields, start: date, term: LicenseTerm)`는
`app.application.license_contract.inputs`에 둔다.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.file_storage import FakeFileStorage


def _load(module: str, name: str) -> Any:  # noqa: ANN401 - 지연 import한 유스케이스 클래스
    import importlib  # noqa: PLC0415

    return getattr(importlib.import_module(module), name)


class LicenseContractUseCases:
    """`_license_uow_factory()`, `clock`, `file_storage`를 가진 클래스에 섞는다."""

    clock: Clock
    file_storage: FakeFileStorage

    def _license_uow_factory(self) -> UnitOfWorkFactory:
        raise NotImplementedError

    def list_license_contracts(self) -> Any:  # noqa: ANN401
        cls = _load(
            "app.application.license_contract.list_license_contracts", "ListLicenseContracts"
        )
        return cls(self._license_uow_factory())

    def get_license_contract(self) -> Any:  # noqa: ANN401
        cls = _load("app.application.license_contract.get_license_contract", "GetLicenseContract")
        return cls(self._license_uow_factory())

    def update_license_contract(self) -> Any:  # noqa: ANN401
        module = "app.application.license_contract.update_license_contract"
        return _load(module, "UpdateLicenseContract")(self._license_uow_factory(), self.clock)

    def issue_license(self) -> Any:  # noqa: ANN401
        return _load("app.application.license_contract.issue_license", "IssueLicense")(
            self._license_uow_factory(), self.clock
        )

    def renew_license(self) -> Any:  # noqa: ANN401
        return _load("app.application.license_contract.renew_license", "RenewLicense")(
            self._license_uow_factory(), self.clock
        )

    def end_license_contract(self) -> Any:  # noqa: ANN401
        module = "app.application.license_contract.end_license_contract"
        return _load(module, "EndLicenseContract")(self._license_uow_factory(), self.clock)

    def delete_license_contract(self) -> Any:  # noqa: ANN401
        module = "app.application.license_contract.delete_license_contract"
        return _load(module, "DeleteLicenseContract")(
            self._license_uow_factory(), self.file_storage
        )

    def list_contract_attachments(self) -> Any:  # noqa: ANN401
        module = "app.application.license_contract_attachment.list_contract_attachments"
        return _load(module, "ListContractAttachments")(self._license_uow_factory())

    def get_contract_attachment(self) -> Any:  # noqa: ANN401
        module = "app.application.license_contract_attachment.get_contract_attachment"
        return _load(module, "GetContractAttachment")(self._license_uow_factory())

    def upload_contract_attachment(self) -> Any:  # noqa: ANN401
        module = "app.application.license_contract_attachment.upload_contract_attachment"
        return _load(module, "UploadContractAttachment")(
            self._license_uow_factory(), self.clock, self.file_storage
        )

    def download_contract_attachment(self) -> Any:  # noqa: ANN401
        module = "app.application.license_contract_attachment.download_contract_attachment"
        return _load(module, "DownloadContractAttachment")(
            self._license_uow_factory(), self.file_storage
        )

    def delete_contract_attachment(self) -> Any:  # noqa: ANN401
        module = "app.application.license_contract_attachment.delete_contract_attachment"
        return _load(module, "DeleteContractAttachment")(
            self._license_uow_factory(), self.file_storage
        )
