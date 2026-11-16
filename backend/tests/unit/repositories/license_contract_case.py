"""계약·계약 첨부 저장소 계약 테스트 공용 case(Fake와 SQL 구현 양쪽).

계약은 Deal(소속·고객·Vendor·Product·파트너·Owner를 읽는 곳)과 사용자(등록자·수정자·업로더)를
참조하므로, case가 Deal 저장소 묶음(`DealCase`)을 함께 들고 필요한 행을 먼저 만든다. Fake는
`FakeUnitOfWork`가 연결한(FK 모사) 저장소를, SQL은 한 세션 위의 Sql 저장소들을 쓴다. SQL 구현
모듈은 사용 시점에 가져온다.
"""

import itertools
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

from app.domain.contact.values import ContactKind
from app.domain.user.errors import UserNotFoundError
from tests.factories import NOW, make_deal, make_deal_code
from tests.factories_auth import make_user
from tests.factories_license_contract import make_contract, make_contract_attachment
from tests.fakes.catalog_seed import seed_catalog
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.default_vendor import DEFAULT_VENDOR_ID, rolled_back_session_with_vendor
from tests.support.user_ids import OWNER_ID, uid
from tests.support.user_seed import ensure_users
from tests.unit.repositories.deal_case import DealCase, _sql_case

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

    from app.application.ports.license_contract_attachment_repository import (
        LicenseContractAttachmentRepository,
    )
    from app.application.ports.license_contract_repository import LicenseContractRepository
    from app.domain.deal.entities import Deal
    from app.domain.license_contract.attachment import ContractAttachment
    from app.domain.license_contract.entities import LicenseContract
    from app.domain.user.value_objects import UserId

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]
_CODES = itertools.count(1)
_CONTACTS = itertools.count(1)


class ContractCase:
    def __init__(
        self,
        deal_case: DealCase,
        contracts: LicenseContractRepository,
        files: LicenseContractAttachmentRepository,
    ) -> None:
        self.deal_case = deal_case
        self.repository = contracts
        self.files = files
        self.deals = deal_case.deals
        self.users = deal_case.users
        self._vendors: dict[str, Any] = {}

    # --- 사용자·Deal 준비 ---

    async def user(self, name: str, display_name: str | None = None) -> UserId:
        """로그인 아이디 name인 재직 사용자(이미 있으면 건드리지 않는다)."""
        user_id = uid(name)
        try:
            await self.users.get(user_id)
        except UserNotFoundError:
            await self.users.add(make_user(name, entity_id=user_id, display_name=display_name))
        return user_id

    async def resign(self, user_id: UserId) -> None:
        await self.deal_case.resign(user_id, NOW + timedelta(days=30))

    async def deal(  # noqa: PLR0913 - Deal에서 읽는 값이 모두 독립적인 선택지
        self,
        *,
        customer: str = "넥스트고객",
        product: str = "S/4HANA",
        vendor: str | None = None,
        partner: str | None = None,
        owner: str | None = None,
        owner_display: str | None = None,
        name: str = "ERP 구축",
        forecast_key: str = "pipeline",
    ) -> Deal:
        """주어진 값을 가진 Deal을 저장한다(고객·Vendor·파트너·Owner 행도 만든다)."""
        n = next(_CONTACTS)
        owner_id = OWNER_ID if owner is None else await self.user(owner, owner_display)
        customer_row = await self.deal_case.new_contact(
            ContactKind.CUSTOMER, company=customer, name=f"담당{n}", email=f"c{n}@lc.example"
        )
        partner_row = (
            None
            if partner is None
            else await self.deal_case.new_contact(
                ContactKind.PARTNER, company=partner, name=f"파트너{n}", email=f"p{n}@lc.example"
            )
        )
        vendor_row = None  # 생략하면 기본 Vendor(Vendor는 Deal의 필수 값)
        if vendor is not None:  # 같은 이름의 Vendor는 한 번만 만든다(이름은 고유)
            if vendor not in self._vendors:
                self._vendors[vendor] = await self.deal_case.new_vendor(vendor)
            vendor_row = self._vendors[vendor]
        deal = make_deal(
            code=make_deal_code(next(_CODES)),
            customer_id=customer_row.id,
            partner_id=None if partner_row is None else partner_row.id,
            owner_user_id=owner_id,
            vendor_id=DEFAULT_VENDOR_ID if vendor_row is None else vendor_row.id,
            product=product,
            name=name,
            status_key="contract_completed" if forecast_key == "won" else "prospecting",
            forecast_key=forecast_key,
        )
        await self.deal_case.add(deal)
        return deal

    # --- 계약·첨부 준비 ---

    async def add(self, contract: LicenseContract) -> LicenseContract:
        """등록자·수정자 행을 (없으면) 만들고 저장한다. Deal은 이미 있어야 한다."""
        await ensure_users(self.users, contract.created_by, contract.updated_by)
        await self.repository.add(contract)
        return contract

    async def contract(self, deal: Deal, **overrides: Any) -> LicenseContract:  # noqa: ANN401
        """Deal에 계약 하나를 저장한다(overrides는 `make_contract`와 같다)."""
        return await self.add(make_contract(deal_code=deal.id, **overrides))

    async def attach(
        self,
        contract: LicenseContract,
        name: str = "a.pdf",
        **overrides: Any,  # noqa: ANN401
    ) -> ContractAttachment:
        """계약에 첨부 하나를 저장한다(업로더 행도 만든다)."""
        attachment = make_contract_attachment(contract, name=name, **overrides)
        await ensure_users(self.users, attachment.uploaded_by)
        await self.files.add(attachment)
        return attachment

    async def row_ids(self, **criteria: Any) -> list[int]:  # noqa: ANN401
        """검색 결과의 계약 id(정렬 순서 그대로)."""
        from app.application.ports.license_contract_repository import (  # noqa: PLC0415
            LicenseContractQuery,
        )

        rows = await self.repository.search(LicenseContractQuery(limit=200, **criteria))
        return [r.contract.id for r in rows]

    async def total(self, **criteria: Any) -> int:  # noqa: ANN401
        from app.application.ports.license_contract_repository import (  # noqa: PLC0415
            LicenseContractQuery,
        )

        return await self.repository.count(LicenseContractQuery(**criteria))


def _fake_case() -> ContractCase:
    uow = FakeUnitOfWork()
    seed_catalog(uow)
    deal_case = DealCase(
        uow.deals,
        uow.deal_history,
        uow.deal_actions,
        uow.contacts,
        uow.users,
        uow.codes,
        uow.bant_labels,
        uow.vendors,
    )
    return ContractCase(deal_case, uow.license_contracts, uow.license_contract_attachments)


def _sql_contract_case(session: Any) -> ContractCase:  # noqa: ANN401
    from app.infra.db.license_contract_attachment_repository import (  # noqa: PLC0415
        SqlLicenseContractAttachmentRepository,
    )
    from app.infra.db.license_contract_repository import (  # noqa: PLC0415
        SqlLicenseContractRepository,
    )

    return ContractCase(
        _sql_case(session),
        SqlLicenseContractRepository(session),
        SqlLicenseContractAttachmentRepository(session),
    )


@asynccontextmanager
async def open_contract_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[ContractCase]:
    if implementation == "fake":
        yield _fake_case()
        return
    async with rolled_back_session_with_vendor(test_database_url) as session:  # type: ignore[arg-type]
        yield _sql_contract_case(session)
