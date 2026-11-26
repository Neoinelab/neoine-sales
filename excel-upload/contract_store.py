from datetime import datetime
from secrets import choice
from string import ascii_uppercase, digits

from contract_plan import ExistingContract, Owner, already_imported, resolve_owner
from contract_workbook import ContractImportError, ContractInput
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.infra.db.models_auth import UserRow
from app.infra.db.models_catalog import VendorRow
from app.infra.db.models_contact import ContactRow
from app.infra.db.models_deal import DealHistoryRow, DealPartnerRow, DealRow
from app.infra.db.models_license_contract import LicenseContractRow


async def _existing(session: AsyncSession, item: ContractInput) -> list[ExistingContract]:
    deals = (
        await session.scalars(
            select(DealRow).where(func.lower(DealRow.name) == func.lower(item.deal_name))
        )
    ).all()
    found = []
    for deal in deals:
        customer = await session.get(ContactRow, deal.customer_id)
        vendor = await session.get(VendorRow, deal.vendor_id)
        contracts = (
            await session.scalars(
                select(LicenseContractRow).where(LicenseContractRow.deal_id == deal.id)
            )
        ).all()
        partners = (
            await session.scalars(
                select(ContactRow)
                .join(DealPartnerRow, DealPartnerRow.contact_id == ContactRow.id)
                .where(DealPartnerRow.deal_id == deal.id, DealPartnerRow.unlinked_at.is_(None))
            )
        ).all()
        if customer is None or vendor is None or len(contracts) != 1 or len(partners) > 1:
            raise ContractImportError(
                item.row, "기존 Deal의 연락처/Vendor/계약 연결이 일치하지 않습니다."
            )
        contract = contracts[0]
        if customer.kind != "customer" or (partners and partners[0].kind != "partner"):
            raise ContractImportError(item.row, "기존 Deal 연락처 종류가 다릅니다.")
        found.append(
            ExistingContract(
                customer.company.casefold(),
                customer.name,
                vendor.name.casefold(),
                deal.product,
                partners[0].company.casefold() if partners else "",
                partners[0].name if partners else "",
                deal.owner_user_id,
                contract.license_start,
                contract.license_end,
                contract.note,
                contract.tech_owner,
                contract.inspection_cycle,
                contract.status,
                deal.status_key,
                deal.forecast_key,
                deal.users,
                deal.revenue_amount,
                deal.revenue_date,
            )
        )
    return found


async def _contact(session: AsyncSession, identity: tuple[str, str, str], now: datetime) -> int:
    kind, company, name = identity
    matches = (
        await session.scalars(
            select(ContactRow)
            .where(
                ContactRow.kind == kind,
                func.lower(ContactRow.company) == func.lower(company),
                func.lower(ContactRow.name) == func.lower(name),
            )
            .order_by(ContactRow.id)
        )
    ).all()
    if matches:
        return matches[0].id
    contact = ContactRow(kind=kind, company=company, name=name, created_at=now, updated_at=now)
    session.add(contact)
    await session.flush()
    return contact.id


async def _vendor(session: AsyncSession, name: str, now: datetime) -> int:
    existing = await session.scalar(
        select(VendorRow).where(func.lower(VendorRow.name) == func.lower(name))
    )
    if existing is not None:
        return existing.id
    vendor = VendorRow(name=name, created_at=now, updated_at=now)
    session.add(vendor)
    await session.flush()
    return vendor.id


async def _code(session: AsyncSession, now: datetime) -> str:
    for _ in range(100):
        suffix = "".join(choice(ascii_uppercase + digits) for _ in range(4))
        code = f"{now:%Y%m%d}-{suffix}"
        if await session.scalar(select(DealRow.id).where(DealRow.deal_code == code)) is None:
            return code
    raise ContractImportError(0, "고유 Deal 코드를 발급하지 못했습니다.")


async def _insert(session: AsyncSession, entry: tuple[ContractInput, int], now: datetime) -> None:
    item, owner = entry
    customer = await _contact(session, ("customer", item.customer, "유지보수"), now)
    vendor = await _vendor(session, item.vendor, now)
    deal = DealRow(
        deal_code=await _code(session, now),
        name=item.deal_name,
        owner_user_id=owner,
        vendor_id=vendor,
        product=item.product,
        users=None,
        revenue_amount=None,
        revenue_date=item.start,
        customer_id=customer,
        status_kind="status",
        status_key="contract_completed",
        forecast_kind="forecast",
        forecast_key="won",
        status_changed_on=item.start,
        procurement="",
        created_at=now,
        updated_at=now,
    )
    session.add(deal)
    await session.flush()
    if item.partner:
        partner = await _contact(session, ("partner", item.partner, ""), now)
        session.add(DealPartnerRow(deal_id=deal.id, contact_id=partner, linked_at=now))
    session.add(
        LicenseContractRow(
            deal_id=deal.id,
            status="issued_new",
            license_start=item.start,
            license_end=item.end,
            term_amount=None,
            term_unit=None,
            tech_owner=item.tech_owner,
            inspection_cycle=item.inspection,
            note=item.note,
            created_by_user_id=owner,
            updated_by_user_id=owner,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        DealHistoryRow(
            deal_id=deal.id,
            changed_at=now,
            changed_by_user_id=owner,
            category="created",
            target="Deal",
            before_text="",
            after_text="Excel 계약 가져오기",
        )
    )
    await session.flush()


async def import_contracts(
    engine: AsyncEngine, rows: list[ContractInput], *, dry_run: bool
) -> tuple[int, int]:
    """전체 행을 먼저 계획하고 한 트랜잭션에 저장한다. dry-run은 SELECT만 실행한다."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        await session.execute(text("SET LOCAL statement_timeout = '30s'"))
        await session.execute(text("SET LOCAL lock_timeout = '10s'"))
        if dry_run:
            await session.execute(text("SET TRANSACTION READ ONLY"))
        else:
            await session.execute(
                text("LOCK TABLE deals, contacts, vendors IN SHARE ROW EXCLUSIVE MODE")
            )
        users = (
            await session.scalars(
                select(UserRow).where(
                    UserRow.deleted_at.is_(None), UserRow.role.in_(("sales", "admin"))
                )
            )
        ).all()
        owners = [Owner(user.id, user.login_id, user.display_name or "") for user in users]
        plan = []
        skipped = 0
        for item in rows:
            owner = resolve_owner(item, owners)
            if already_imported(item, owner, await _existing(session, item)):
                skipped += 1
            else:
                plan.append((item, owner))
        if not dry_run:
            now = datetime.now().astimezone()
            for entry in plan:
                try:
                    await _insert(session, entry, now)
                except SQLAlchemyError:
                    raise ContractImportError(
                        entry[0].row,
                        "DB 저장 실패: 마이그레이션과 DB 제약을 확인하세요. 전체 롤백합니다.",
                    ) from None
        return len(plan), skipped
