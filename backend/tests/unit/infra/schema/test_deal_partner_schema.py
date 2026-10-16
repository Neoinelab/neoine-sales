"""head 스키마의 deal_partners(AC-11·28): Deal당 활성 링크 최대 1건(부분 유니크), 기간 CHECK, FK."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_contact, insert_deal, insert_partner_link

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

LINKED = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)
COLUMNS = {"id", "deal_code", "contact_id", "linked_at", "unlinked_at"}
INDEXES = {
    "uq_deal_partners_one_active",
    "ix_deal_partners_contact_id",
    "ix_deal_partners_deal_code_linked_at",
}
COLUMN_NAMES = (
    "select column_name from information_schema.columns where table_name = 'deal_partners'"
)
INDEX_DEFS = "select indexname, indexdef from pg_indexes where tablename = 'deal_partners'"
FOREIGN_KEYS = (
    "select confrelid::regclass::text, confdeltype::text from pg_constraint"
    " where conrelid = 'deal_partners'::regclass and contype = 'f'"
)


async def _deal_with_contacts(session: AsyncSession, count: int = 2) -> tuple[str, list[str]]:
    customer = await insert_contact(session)
    code = await insert_deal(session, customer)
    partners = [
        await insert_contact(session, kind="partner", company=f"파트너{n}") for n in range(count)
    ]
    return code, partners


async def test_the_columns_and_indexes_exist(session: AsyncSession) -> None:
    columns = {r[0] for r in (await session.execute(text(COLUMN_NAMES))).all()}
    indexes = {r[0]: r[1] for r in (await session.execute(text(INDEX_DEFS))).all()}

    assert columns == COLUMNS
    assert set(indexes) >= INDEXES
    assert "unique" in indexes["uq_deal_partners_one_active"].lower()
    assert "unlinked_at is null" in indexes["uq_deal_partners_one_active"].lower()


async def test_foreign_keys_cascade_from_the_deal_and_restrict_the_contact(
    session: AsyncSession,
) -> None:
    rows = (await session.execute(text(FOREIGN_KEYS))).all()

    assert {(r[0], r[1].strip()) for r in rows} == {("deals", "c"), ("contacts", "r")}


async def test_a_second_active_link_for_the_same_deal_is_rejected(session: AsyncSession) -> None:
    code, (first, second) = await _deal_with_contacts(session)
    await insert_partner_link(session, code, first)

    with pytest.raises(IntegrityError, match="uq_deal_partners_one_active"):
        await insert_partner_link(session, code, second)


async def test_an_inactive_link_and_a_new_active_link_can_coexist(session: AsyncSession) -> None:
    code, (first, second) = await _deal_with_contacts(session)
    await insert_partner_link(session, code, first, unlinked_at=LATER)

    await insert_partner_link(session, code, second, linked_at=LATER)

    count = (await session.execute(text("select count(*) from deal_partners"))).scalar_one()
    assert count == 2


async def test_many_inactive_links_are_allowed(session: AsyncSession) -> None:
    code, (first, second) = await _deal_with_contacts(session)
    await insert_partner_link(session, code, first, unlinked_at=LATER)
    await insert_partner_link(session, code, second, unlinked_at=LATER)
    await insert_partner_link(
        session, code, first, unlinked_at=LATER
    )  # 같은 파트너를 다시 연결했다 해제


async def test_each_deal_has_its_own_active_link(session: AsyncSession) -> None:
    customer = await insert_contact(session)
    partner = await insert_contact(session, kind="partner")
    first = await insert_deal(session, customer, code="20261016-A001")
    second = await insert_deal(session, customer, code="20261016-A002")

    await insert_partner_link(session, first, partner)
    await insert_partner_link(session, second, partner)


async def test_unlinking_before_linking_is_rejected(session: AsyncSession) -> None:
    code, (first, _) = await _deal_with_contacts(session)

    with pytest.raises(IntegrityError, match="ck_deal_partners_period"):
        await insert_partner_link(session, code, first, linked_at=LATER, unlinked_at=LINKED)


async def test_an_unlink_at_the_same_moment_as_the_link_is_allowed(session: AsyncSession) -> None:
    code, (first, _) = await _deal_with_contacts(session)

    await insert_partner_link(session, code, first, linked_at=LINKED, unlinked_at=LINKED)


async def test_a_missing_contact_is_rejected(session: AsyncSession) -> None:
    code, _ = await _deal_with_contacts(session, count=0)

    with pytest.raises(IntegrityError, match="fk_deal_partners_contact_id_contacts"):
        await insert_partner_link(session, code, str(uuid4()))


async def test_a_contact_with_a_link_cannot_be_deleted_even_if_the_link_is_inactive(
    session: AsyncSession,
) -> None:
    code, (first, _) = await _deal_with_contacts(session)
    await insert_partner_link(session, code, first, unlinked_at=LATER)

    with pytest.raises(IntegrityError, match="fk_deal_partners_contact_id_contacts"):
        await session.execute(text("delete from contacts where id = :id"), {"id": first})


async def test_deleting_the_deal_deletes_its_links(session: AsyncSession) -> None:
    code, (first, second) = await _deal_with_contacts(session)
    await insert_partner_link(session, code, first, unlinked_at=LATER)
    await insert_partner_link(session, code, second)

    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    count = (await session.execute(text("select count(*) from deal_partners"))).scalar_one()
    assert count == 0
