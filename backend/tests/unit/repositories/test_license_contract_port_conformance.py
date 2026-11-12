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
    """Fake와 SQL 저장소가 모두 계약 Port를 만족한다."""
    # given: Fake·SQL 저장소 인스턴스
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    session = AsyncSession(engine)
    fake: LicenseContractRepository = FakeLicenseContractRepository()
    sql: LicenseContractRepository = SqlLicenseContractRepository(session)
    fake_files: LicenseContractAttachmentRepository = FakeLicenseContractAttachmentRepository()
    # when: Port 타입으로 받는다
    sql_files: LicenseContractAttachmentRepository = SqlLicenseContractAttachmentRepository(session)

    # then: 모두 만들어진다
    assert None not in (fake, sql, fake_files, sql_files)


def test_every_repository_method_is_a_coroutine_on_both_implementations() -> None:
    """Port의 모든 메서드가 두 구현에서 코루틴 함수다."""
    # given: Port와 두 구현
    pairs = (
        (LicenseContractRepository, FakeLicenseContractRepository, SqlLicenseContractRepository),
        (
            LicenseContractAttachmentRepository,
            FakeLicenseContractAttachmentRepository,
            SqlLicenseContractAttachmentRepository,
        ),
    )
    names = (CONTRACT_METHODS, ATTACHMENT_METHODS)
    # when: 메서드를 하나씩 확인한다
    for (port, fake, sql), methods in zip(pairs, names, strict=True):
        for name in methods:
            assert hasattr(port, name), name
            assert inspect.iscoroutinefunction(getattr(fake, name)), name
            assert inspect.iscoroutinefunction(getattr(sql, name)), name
    # then: 모두 코루틴 함수다


def test_unit_of_work_port_and_implementations_expose_the_repositories() -> None:
    """UoW Port와 구현이 두 저장소를 드러낸다."""
    # given: Fake UoW
    fake = FakeUnitOfWork()

    # when: 저장소 속성을 확인한다
    for name in ("license_contracts", "license_contract_attachments"):
        assert hasattr(UnitOfWork, name), name
        assert name in SqlUnitOfWork.__annotations__ or hasattr(SqlUnitOfWork, name), name
    # then: Port와 Fake 구현에 모두 있다
    assert isinstance(fake.license_contracts, FakeLicenseContractRepository)
    assert isinstance(fake.license_contract_attachments, FakeLicenseContractAttachmentRepository)


def test_the_id_allocator_has_kinds_for_both_tables() -> None:
    """id 할당기에 두 테이블의 종류가 있다."""
    # when: IdKind를 모은다
    kinds = {kind.name for kind in IdKind}

    # then: LICENSE_CONTRACT와 CONTRACT_ATTACHMENT가 있다
    assert {"LICENSE_CONTRACT", "CONTRACT_ATTACHMENT"} <= kinds


def test_the_web_port_exposes_the_license_contract_use_cases() -> None:
    """web Port가 계약 유스케이스 메서드를 드러낸다."""
    # when: UseCaseProvider를 확인한다
    for name in USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
    # then: 모든 유스케이스 메서드가 있다


def test_the_key_listing_methods_are_gone_from_the_attachment_port_and_implementations() -> None:
    """첨부 Port와 구현에서 키 목록 메서드가 없어졌다."""
    # when: Port와 구현의 메서드를 확인한다
    for implementation in (
        LicenseContractAttachmentRepository,
        FakeLicenseContractAttachmentRepository,
        SqlLicenseContractAttachmentRepository,
    ):
        for name in REMOVED_ATTACHMENT_METHODS:
            assert not hasattr(implementation, name), (implementation, name)
    # then: 키 목록 메서드가 없다


def test_the_deal_side_value_carries_is_won() -> None:
    """DealSide 값에 Won 여부 필드가 있다.

    테스트 코드: LC-028
    """
    from app.application.ports.license_contract_repository import DealSide  # noqa: PLC0415

    # when: 필드를 살핀다
    actual = DealSide.__dataclass_fields__
    # then: is_won이 있다
    assert "is_won" in actual


def test_the_deal_list_item_carries_has_issued_license_contract() -> None:
    """DealListItem에 발급 여부 필드가 있다.

    테스트 코드: LC-030
    """
    from app.application.ports.deal_repository import DealListItem  # noqa: PLC0415

    # when: 필드를 살핀다
    actual = DealListItem.__dataclass_fields__
    # then: has_issued_license_contract가 있다
    assert "has_issued_license_contract" in actual
