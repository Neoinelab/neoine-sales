"""계약·계약 첨부 Port의 구현체 적합성과 UoW·Provider·Container 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.id_allocator import IdKind
from app.application.ports.license_contract_attachment_repository import (
    LicenseContractAttachmentRepository,
)
from app.application.ports.license_contract_repository import LicenseContractRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.license_contract_attachment_repository import (
    SqlLicenseContractAttachmentRepository,
)
from app.infra.db.license_contract_repository import SqlLicenseContractRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.license_contract_attachments import FakeLicenseContractAttachmentRepository
from tests.fakes.license_contracts import FakeLicenseContractRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases

CONTRACT_METHODS = (
    "add",
    "get",
    "get_row",
    "update",
    "delete",
    "count_of_deal",
    "delete_of_deal",
    "issued_of_deal",
    "ids_of_deal",
    "search",
    "count",
)
ATTACHMENT_METHODS = (
    "add",
    "get",
    "find_by_name",
    "list_by_contract",
    "update",
    "delete",
)
REMOVED_ATTACHMENT_METHODS = ("storage_keys_of_contract", "storage_keys_of_deal")
USE_CASES = (
    "list_license_contracts",
    "get_license_contract",
    "update_license_contract",
    "issue_license",
    "renew_license",
    "end_license_contract",
    "delete_license_contract",
    "list_contract_attachments",
    "get_contract_attachment",
    "upload_contract_attachment",
    "download_contract_attachment",
    "delete_contract_attachment",
)


def test_contract_repositories_satisfy_the_ports() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    session = AsyncSession(engine)
    fake: LicenseContractRepository = FakeLicenseContractRepository()
    sql: LicenseContractRepository = SqlLicenseContractRepository(session)
    fake_files: LicenseContractAttachmentRepository = FakeLicenseContractAttachmentRepository()
    sql_files: LicenseContractAttachmentRepository = SqlLicenseContractAttachmentRepository(session)

    assert None not in (fake, sql, fake_files, sql_files)


def test_every_repository_method_is_a_coroutine_on_both_implementations() -> None:
    pairs = (
        (LicenseContractRepository, FakeLicenseContractRepository, SqlLicenseContractRepository),
        (
            LicenseContractAttachmentRepository,
            FakeLicenseContractAttachmentRepository,
            SqlLicenseContractAttachmentRepository,
        ),
    )
    names = (CONTRACT_METHODS, ATTACHMENT_METHODS)
    for (port, fake, sql), methods in zip(pairs, names, strict=True):
        for name in methods:
            assert hasattr(port, name), name
            assert inspect.iscoroutinefunction(getattr(fake, name)), name
            assert inspect.iscoroutinefunction(getattr(sql, name)), name


def test_unit_of_work_port_and_implementations_expose_the_repositories() -> None:
    fake = FakeUnitOfWork()

    for name in ("license_contracts", "license_contract_attachments"):
        assert hasattr(UnitOfWork, name), name
        assert name in SqlUnitOfWork.__annotations__ or hasattr(SqlUnitOfWork, name), name
    assert isinstance(fake.license_contracts, FakeLicenseContractRepository)
    assert isinstance(fake.license_contract_attachments, FakeLicenseContractAttachmentRepository)


def test_the_id_allocator_has_kinds_for_both_tables() -> None:
    kinds = {kind.name for kind in IdKind}

    assert {"LICENSE_CONTRACT", "CONTRACT_ATTACHMENT"} <= kinds


def test_the_web_port_exposes_the_license_contract_use_cases() -> None:
    for name in USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name


def test_the_key_listing_methods_are_gone_from_the_attachment_port_and_implementations() -> None:
    for implementation in (
        LicenseContractAttachmentRepository,
        FakeLicenseContractAttachmentRepository,
        SqlLicenseContractAttachmentRepository,
    ):
        for name in REMOVED_ATTACHMENT_METHODS:
            assert not hasattr(implementation, name), (implementation, name)


def test_the_deal_side_value_carries_is_won() -> None:
    from app.application.ports.license_contract_repository import DealSide  # noqa: PLC0415

    assert "is_won" in DealSide.__dataclass_fields__


def test_the_deal_list_item_carries_has_issued_license_contract() -> None:
    from app.application.ports.deal_repository import DealListItem  # noqa: PLC0415

    assert "has_issued_license_contract" in DealListItem.__dataclass_fields__
