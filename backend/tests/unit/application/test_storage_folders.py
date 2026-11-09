"""저장 폴더 규칙(F3): Deal 첨부는 `<deal_code>`, 계약 첨부는 `license-contracts/<계약 id>`."""

from app.domain.deal.code import DealCode
from app.domain.license_contract.values import LicenseContractId


def test_deal_folder_is_the_deal_code_alone() -> None:
    """Deal 폴더는 Deal 코드 하나다.

    테스트 코드: LC-063
    """
    from app.application.ports.file_storage import StorageFolder  # noqa: PLC0415
    from app.application.storage.folders import deal_folder  # noqa: PLC0415

    # when: Deal 코드로 폴더를 구한다
    # then: 코드 하나짜리 StorageFolder다
    assert deal_folder(DealCode("20261016-A001")) == StorageFolder(parts=("20261016-A001",))


def test_license_contract_folder_is_under_the_license_contracts_directory() -> None:
    """계약 폴더는 license-contracts/<계약 id>다.

    테스트 코드: LC-063
    """
    from app.application.ports.file_storage import StorageFolder  # noqa: PLC0415
    from app.application.storage.folders import license_contract_folder  # noqa: PLC0415

    # when: 계약 id 42로 폴더를 구한다
    folder = license_contract_folder(LicenseContractId(42))

    # then: (license-contracts, 42)다
    assert folder == StorageFolder(parts=("license-contracts", "42"))


def test_the_license_contracts_directory_name_is_fixed() -> None:
    """계약 폴더의 상위 디렉터리 이름은 license-contracts로 고정이다."""
    from app.application.storage.folders import LICENSE_CONTRACTS_DIR  # noqa: PLC0415

    # when: 상수를 읽는다
    # then: license-contracts다
    assert LICENSE_CONTRACTS_DIR == "license-contracts"


def test_different_contracts_get_different_folders() -> None:
    """계약마다 폴더가 다르다.

    테스트 코드: LC-052
    """
    from app.application.storage.folders import license_contract_folder  # noqa: PLC0415

    # when: 계약 1과 2의 폴더를 구한다
    # then: 서로 다르다
    assert license_contract_folder(LicenseContractId(1)) != license_contract_folder(
        LicenseContractId(2)
    )


def test_a_deal_folder_never_equals_the_contracts_directory() -> None:
    """Deal 폴더는 계약 디렉터리와 같지 않다."""
    from app.application.storage.folders import deal_folder  # noqa: PLC0415

    # when: Deal 폴더를 구한다
    # then: (license-contracts,)가 아니다
    assert deal_folder(DealCode("20261016-A001")).parts != ("license-contracts",)


def test_storage_folder_and_location_are_value_objects() -> None:
    """폴더와 위치는 값 객체이고 위치에는 deal_code 필드가 없다."""
    from app.application.ports.file_storage import (  # noqa: PLC0415
        StorageFolder,
        StoredFileLocation,
    )

    folder = StorageFolder(parts=("a", "b"))
    # when: 같은 값으로 위치를 두 번 만든다
    location = StoredFileLocation(folder=folder, key="k" * 32)

    # then: 같고, 필드는 folder·key뿐이다
    assert location == StoredFileLocation(folder=StorageFolder(parts=("a", "b")), key="k" * 32)
    assert {"folder", "key"} == set(StoredFileLocation.__dataclass_fields__)
    assert {"deal_code"}.isdisjoint(StoredFileLocation.__dataclass_fields__)
