"""head 스키마의 vendors, deals의 Vendor 참조와 Solution 텍스트 컬럼(AC-17).

제약은 원시 SQL로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.support.head_rows import insert_contact, insert_deal
from tests.support.vendor_rows import insert_vendor, link_deal

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMNS = (
    "select column_name, data_type, character_maximum_length, is_nullable"
    " from information_schema.columns where table_name = :t"
)
CONSTRAINTS = (
    "select conname, contype::text, confrelid::regclass::text, confdeltype::text,"
    " array_length(conkey, 1) from pg_constraint where conrelid = cast(:t as regclass)"
)
INDEX_DEFS = (
    "select indexname, indexdef from pg_indexes where schemaname = 'public' and tablename = :t"
)


async def _columns(session: AsyncSession, table: str) -> dict[str, tuple[object, ...]]:
    rows = (await session.execute(text(COLUMNS), {"t": table})).all()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


async def _constraints(session: AsyncSession, table: str) -> dict[str, tuple[object, ...]]:
    rows = (await session.execute(text(CONSTRAINTS), {"t": table})).all()
    return {r[0]: (r[1], r[2], (r[3] or "").strip(), r[4]) for r in rows}


async def _deal(session: AsyncSession) -> str:
    return await insert_deal(session, await insert_contact(session))


async def test_vendors_table_has_the_expected_shape(session: AsyncSession) -> None:
    columns = await _columns(session, "vendors")
    constraints = await _constraints(session, "vendors")

    assert set(columns) == {"id", "name", "created_at", "updated_at"}
    assert columns["name"] == ("character varying", 100, "NO")
    assert columns["id"][0] == "bigint"
    assert constraints["pk_vendors"][0] == "p"


async def test_vendor_name_is_unique_ignoring_case(session: AsyncSession) -> None:
    await insert_vendor(session, "SAP")

    with pytest.raises(IntegrityError, match="uq_vendors_name_lower"):
        await insert_vendor(session, "sap")


async def test_the_vendor_name_index_is_a_unique_lower_name_index(session: AsyncSession) -> None:
    rows = (await session.execute(text(INDEX_DEFS), {"t": "vendors"})).all()
    definitions = {r[0]: r[1] for r in rows}

    assert "UNIQUE" in definitions["uq_vendors_name_lower"]
    assert "lower" in definitions["uq_vendors_name_lower"]


async def test_solutions_table_does_not_exist(session: AsyncSession) -> None:
    exists = (await session.execute(text("select to_regclass('public.solutions')"))).scalar_one()

    assert exists is None


async def test_deals_solution_is_not_null_varchar_200(session: AsyncSession) -> None:
    columns = await _columns(session, "deals")

    assert columns["solution"] == ("character varying", 200, "NO")


async def test_deals_solution_has_no_database_default(session: AsyncSession) -> None:
    default = (
        await session.execute(
            text(
                "select column_default from information_schema.columns"
                " where table_name = 'deals' and column_name = 'solution'"
            )
        )
    ).scalar_one()

    assert default is None


async def test_deals_has_no_solution_id_or_its_constraints(session: AsyncSession) -> None:
    columns = await _columns(session, "deals")
    constraints = await _constraints(session, "deals")
    indexes = {r[0] for r in (await session.execute(text(INDEX_DEFS), {"t": "deals"})).all()}

    assert "solution_id" not in columns
    assert "vendor" not in columns
    assert "fk_deals_solution" not in constraints
    assert "ck_deals_solution_needs_vendor" not in constraints
    assert "ix_deals_solution_id" not in indexes


async def test_deals_vendor_id_is_a_nullable_bigint(session: AsyncSession) -> None:
    columns = await _columns(session, "deals")

    assert columns["vendor_id"][0] == "bigint"
    assert columns["vendor_id"][2] == "YES"


async def test_deals_reference_vendors_with_restrict(session: AsyncSession) -> None:
    constraints = await _constraints(session, "deals")

    assert constraints["fk_deals_vendor_id_vendors"][1:] == ("vendors", "r", 1)


async def test_deals_have_a_vendor_index_and_no_solution_index(session: AsyncSession) -> None:
    rows = (await session.execute(text(INDEX_DEFS), {"t": "deals"})).all()

    assert "ix_deals_vendor_id" in {r[0] for r in rows}


async def test_a_deal_may_have_a_solution_text_without_a_vendor(session: AsyncSession) -> None:
    code = await _deal(session)

    await link_deal(session, code, None, "ITDR")

    stored = (
        await session.execute(
            text("select solution from deals where deal_code = :code"), {"code": code}
        )
    ).scalar_one()
    assert stored == "ITDR"


async def test_a_deal_may_have_a_vendor_without_a_solution_text(session: AsyncSession) -> None:
    code = await _deal(session)

    await link_deal(session, code, await insert_vendor(session, "SAP"), "")


async def test_a_deal_solution_longer_than_200_is_rejected(session: AsyncSession) -> None:
    code = await _deal(session)

    with pytest.raises(DBAPIError, match="too long"):
        await link_deal(session, code, None, "a" * 201)


async def test_a_deal_solution_cannot_be_null(session: AsyncSession) -> None:
    code = await _deal(session)

    with pytest.raises(IntegrityError, match="solution"):
        await session.execute(
            text("update deals set solution = null where deal_code = :code"), {"code": code}
        )


async def test_a_vendor_used_by_a_deal_cannot_be_deleted(session: AsyncSession) -> None:
    code = await _deal(session)
    sap = await insert_vendor(session, "SAP")
    await link_deal(session, code, sap)

    with pytest.raises(IntegrityError, match="fk_deals_vendor_id_vendors"):
        await session.execute(text("delete from vendors where id = :id"), {"id": sap})


async def test_deleting_the_deal_releases_the_vendor(session: AsyncSession) -> None:
    code = await _deal(session)
    sap = await insert_vendor(session, "SAP")
    await link_deal(session, code, sap)
    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    await session.execute(text("delete from vendors where id = :id"), {"id": sap})
