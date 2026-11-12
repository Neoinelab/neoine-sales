"""head 스키마의 deal_partners: Deal당 활성 링크 최대 1건(부분 유니크), 기간 CHECK, FK."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_contact, insert_deal, insert_partner_link
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

LINKED = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)
COLUMNS = {"id", "deal_id", "contact_id", "linked_at", "unlinked_at"}
INDEXES = {
    "uq_deal_partners_one_active",
    "ix_deal_partners_contact_id",
    "ix_deal_partners_deal_id_linked_at",
}
COLUMN_NAMES = (
    "select column_name from information_schema.columns where table_name = 'deal_partners'"
)
INDEX_DEFS = "select indexname, indexdef from pg_indexes where tablename = 'deal_partners'"
FOREIGN_KEYS = (
    "select confrelid::regclass::text, confdeltype::text from pg_constraint"
    " where conrelid = 'deal_partners'::regclass and contype = 'f'"
)


async def _deal_with_contacts(session: AsyncSession, count: int = 2) -> tuple[str, list[int]]:
    customer = await insert_contact(session)
    code = await insert_deal(session, customer)
    partners = [
        await insert_contact(session, kind="partner", company=f"파트너{n}") for n in range(count)
    ]
    return code, partners


async def test_the_columns_and_indexes_exist(session: AsyncSession) -> None:
    """deal_partners 테이블에 기대한 컬럼과 인덱스(활성 링크 부분 유니크 포함)가 있다."""
    # when: 컬럼과 인덱스 정의를 조회한다
    columns = {r[0] for r in (await session.execute(text(COLUMN_NAMES))).all()}
    indexes = {r[0]: r[1] for r in (await session.execute(text(INDEX_DEFS))).all()}

    # then: 컬럼이 같고 필수 인덱스가 있으며 활성 링크 인덱스는 unlinked_at이 null인 부분 유니크다
    assert columns == COLUMNS
    assert set(indexes) >= INDEXES
    assert "unique" in indexes["uq_deal_partners_one_active"].lower()
    assert "unlinked_at is null" in indexes["uq_deal_partners_one_active"].lower()


async def test_foreign_keys_cascade_from_the_deal_and_restrict_the_contact(
    session: AsyncSession,
) -> None:
    """외래 키는 Deal은 CASCADE, 연락처는 RESTRICT다."""
    # when: 외래 키 정의를 조회한다
    rows = (await session.execute(text(FOREIGN_KEYS))).all()

    # then: deals는 c(cascade), contacts는 r(restrict)다
    assert {(r[0], r[1].strip()) for r in rows} == {("deals", "c"), ("contacts", "r")}


async def test_a_second_active_link_for_the_same_deal_is_rejected(session: AsyncSession) -> None:
    """같은 Deal에 활성 링크를 하나 더 넣으면 부분 유니크 위반이다."""
    # given: 활성 링크가 하나 있는 Deal
    code, (first, second) = await _deal_with_contacts(session)
    await insert_partner_link(session, code, first)

    # when·then: 다른 파트너로 활성 링크를 또 넣으면 IntegrityError다
    with pytest.raises(IntegrityError, match="uq_deal_partners_one_active"):
        await insert_partner_link(session, code, second)


async def test_an_inactive_link_and_a_new_active_link_can_coexist(session: AsyncSession) -> None:
    """해제된 링크와 새 활성 링크는 함께 있을 수 있다."""
    # given: 해제된 링크가 있는 Deal
    code, (first, second) = await _deal_with_contacts(session)
    await insert_partner_link(session, code, first, unlinked_at=LATER)

    # when: 다른 파트너로 새 활성 링크를 넣는다
    await insert_partner_link(session, code, second, linked_at=LATER)

    # then: 링크가 2건 저장된다
    count = (await session.execute(text("select count(*) from deal_partners"))).scalar_one()
    assert count == 2


async def test_many_inactive_links_are_allowed(session: AsyncSession) -> None:
    """해제된 링크는 몇 건이든 넣을 수 있다."""
    # given: Deal과 파트너 둘, 해제된 링크 두 건
    code, (first, second) = await _deal_with_contacts(session)
    await insert_partner_link(session, code, first, unlinked_at=LATER)
    await insert_partner_link(session, code, second, unlinked_at=LATER)
    # when·then: 같은 파트너를 다시 연결했다 해제한 링크를 또 넣어도 오류가 없다
    await insert_partner_link(
        session, code, first, unlinked_at=LATER
    )  # 같은 파트너를 다시 연결했다 해제


async def test_each_deal_has_its_own_active_link(session: AsyncSession) -> None:
    """Deal마다 활성 링크는 따로 가질 수 있다."""
    # given: 고객 하나, 파트너 하나, Deal 둘
    customer = await insert_contact(session)
    partner = await insert_contact(session, kind="partner")
    first = await insert_deal(session, customer, code="20261016-A001")
    second = await insert_deal(session, customer, code="20261016-A002")

    # when·then: 두 Deal에 같은 파트너를 각각 연결해도 오류가 없다
    await insert_partner_link(session, first, partner)
    await insert_partner_link(session, second, partner)


async def test_unlinking_before_linking_is_rejected(session: AsyncSession) -> None:
    """해제 시각이 연결 시각보다 앞서면 기간 CHECK 위반이다."""
    # given: Deal과 파트너
    code, (first, _) = await _deal_with_contacts(session)

    # when·then: 해제가 연결보다 이른 링크를 넣으면 IntegrityError다
    with pytest.raises(IntegrityError, match="ck_deal_partners_period"):
        await insert_partner_link(session, code, first, linked_at=LATER, unlinked_at=LINKED)


async def test_an_unlink_at_the_same_moment_as_the_link_is_allowed(session: AsyncSession) -> None:
    """해제 시각이 연결 시각과 같아도 허용된다."""
    # given: Deal과 파트너
    code, (first, _) = await _deal_with_contacts(session)

    # when·then: 연결과 같은 시각에 해제한 링크를 넣어도 오류가 없다
    await insert_partner_link(session, code, first, linked_at=LINKED, unlinked_at=LINKED)


async def test_a_missing_contact_is_rejected(session: AsyncSession) -> None:
    """없는 연락처로 링크를 넣으면 FK 위반이다."""
    # given: 파트너 없는 Deal
    code, _ = await _deal_with_contacts(session, count=0)

    # when·then: 없는 연락처 id로 링크를 넣으면 IntegrityError다
    with pytest.raises(IntegrityError, match="fk_deal_partners_contact_id_contacts"):
        await insert_partner_link(session, code, MISSING_ID)


async def test_a_contact_with_a_link_cannot_be_deleted_even_if_the_link_is_inactive(
    session: AsyncSession,
) -> None:
    """링크가 해제됐어도 링크가 있는 연락처는 삭제할 수 없다."""
    # given: 해제된 링크가 있는 파트너
    code, (first, _) = await _deal_with_contacts(session)
    await insert_partner_link(session, code, first, unlinked_at=LATER)

    # when·then: 그 연락처를 삭제하면 IntegrityError다
    with pytest.raises(IntegrityError, match="fk_deal_partners_contact_id_contacts"):
        await session.execute(text("delete from contacts where id = :id"), {"id": first})


async def test_deleting_the_deal_deletes_its_links(session: AsyncSession) -> None:
    """Deal을 삭제하면 그 링크도 함께 삭제된다."""
    # given: 활성·해제 링크가 있는 Deal
    code, (first, second) = await _deal_with_contacts(session)
    await insert_partner_link(session, code, first, unlinked_at=LATER)
    await insert_partner_link(session, code, second)

    # when: Deal을 삭제한다
    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    # then: 링크가 남지 않는다
    count = (await session.execute(text("select count(*) from deal_partners"))).scalar_one()
    assert count == 0
