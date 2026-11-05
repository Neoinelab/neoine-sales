"""저장 폴더 규칙(F3): Deal 첨부는 `<deal_code>`, 계약 첨부는 `license-contracts/<계약 id>`."""

from app.domain.deal.code import DealCode
from app.domain.license_contract.values import LicenseContractId


def test_deal_folder_is_the_deal_code_alone() -> None:
    from app.application.storage.folders import deal_folder  # noqa: PLC0415

    from app.application.ports.file_storage import StorageFolder  # noqa: PLC0415

    assert deal_folder(DealCode("20261016-A001")) == StorageFolder(parts=("20261016-A001",))


def test_license_contract_folder_is_under_the_license_contracts_directory() -> None:
    from app.application.storage.folders import license_contract_folder  # noqa: PLC0415

    from app.application.ports.file_storage import StorageFolder  # noqa: PLC0415

    folder = license_contract_folder(LicenseContractId(42))

    assert folder == StorageFolder(parts=("license-contracts", "42"))


def test_the_license_contracts_directory_name_is_fixed() -> None:
    from app.application.storage.folders import LICENSE_CONTRACTS_DIR  # noqa: PLC0415

    assert LICENSE_CONTRACTS_DIR == "license-contracts"


def test_different_contracts_get_different_folders() -> None:
    from app.application.storage.folders import license_contract_folder  # noqa: PLC0415

    assert license_contract_folder(LicenseContractId(1)) != license_contract_folder(
        LicenseContractId(2)
    )


def test_a_deal_folder_never_equals_the_contracts_directory() -> None:
    from app.application.storage.folders import deal_folder  # noqa: PLC0415

    assert deal_folder(DealCode("20261016-A001")).parts != ("license-contracts",)


def test_storage_folder_and_location_are_value_objects() -> None:
    from app.application.ports.file_storage import (  # noqa: PLC0415
        StorageFolder,
        StoredFileLocation,
    )

    folder = StorageFolder(parts=("a", "b"))
    location = StoredFileLocation(folder=folder, key="k" * 32)

    assert location == StoredFileLocation(folder=StorageFolder(parts=("a", "b")), key="k" * 32)
    assert {"folder", "key"} == set(StoredFileLocation.__dataclass_fields__)
    assert {"deal_code"}.isdisjoint(StoredFileLocation.__dataclass_fields__)
