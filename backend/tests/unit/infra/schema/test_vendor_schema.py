"""head 스키마의 vendors·solutions와 deals의 Vendor 참조(AC-24, 계획 4장 ORM).

제약은 원시 SQL로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_contact, insert_deal
from tests.support.ids import new_id
from tests.support.vendor_rows import insert_solution, insert_vendor, link_deal

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


async def test_solutions_table_has_the_expected_shape(session: AsyncSession) -> None:
    columns = await _columns(session, "solutions")
    constraints = await _constraints(session, "solutions")

    assert set(columns) == {"id", "vendor_id", "name", "created_at", "updated_at"}
    assert columns["name"] == ("character varying", 200, "NO")
    assert columns["vendor_id"][2] == "NO"
    assert constraints["pk_solutions"][0] == "p"
    assert constraints["uq_solutions_id_vendor_id"][0] == "u"
    assert constraints["uq_solutions_id_vendor_id"][3] == 2


async def test_vendor_name_is_unique_ignoring_case(session: AsyncSession) -> None:
    await insert_vendor(session, "SAP")

    with pytest.raises(IntegrityError, match="uq_vendors_name_lower"):
        await insert_vendor(session, "sap")


async def test_the_vendor_name_index_is_a_unique_lower_name_index(session: AsyncSession) -> None:
    rows = (await session.execute(text(INDEX_DEFS), {"t": "vendors"})).all()
    definitions = {r[0]: r[1] for r in rows}

    assert "UNIQUE" in definitions["uq_vendors_name_lower"]
    assert "lower" in definitions["uq_vendors_name_lower"]


async def test_solution_name_is_unique_per_vendor_ignoring_case_index(
    session: AsyncSession,
) -> None:
    sap = await insert_vendor(session, "SAP")
    await insert_solution(session, sap, "Cloud")

    with pytest.raises(IntegrityError, match="uq_solutions_vendor_id_name_lower"):
        await insert_solution(session, sap, "CLOUD")


async def test_the_same_solution_name_is_allowed_under_another_vendor(
    session: AsyncSession,
) -> None:
    await insert_solution(session, await insert_vendor(session, "SAP"), "Cloud")

    await insert_solution(session, await insert_vendor(session, "Oracle"), "Cloud")


async def test_a_solution_needs_an_existing_vendor(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="fk_solutions_vendor_id_vendors"):
        await insert_solution(session, new_id(), "Cloud")


async def test_solutions_cascade_with_their_vendor(session: AsyncSession) -> None:
    constraints = await _constraints(session, "solutions")
    sap = await insert_vendor(session, "SAP")
    await insert_solution(session, sap, "Cloud")

    await session.execute(text("delete from vendors where id = :id"), {"id": sap})

    assert constraints["fk_solutions_vendor_id_vendors"][2] == "c"
    count = (await session.execute(text("select count(*) from solutions"))).scalar_one()
    assert count == 0


async def test_deals_has_no_text_vendor_columns(session: AsyncSession) -> None:
    columns = await _columns(session, "deals")

    assert "vendor" not in columns
    assert "solution" not in columns
    assert columns["vendor_id"][0] == "bigint"
    assert columns["solution_id"][0] == "bigint"
    assert columns["vendor_id"][2] == "YES"
    assert columns["solution_id"][2] == "YES"


async def test_deals_reference_vendors_with_restrict(session: AsyncSession) -> None:
    constraints = await _constraints(session, "deals")

    assert constraints["fk_deals_vendor_id_vendors"][1:] == ("vendors", "r", 1)


async def test_deals_solution_fk_is_composite_with_vendor(session: AsyncSession) -> None:
    constraints = await _constraints(session, "deals")

    assert constraints["fk_deals_solution"][1:] == ("solutions", "r", 2)


async def test_deals_have_vendor_and_solution_indexes(session: AsyncSession) -> None:
    rows = (await session.execute(text(INDEX_DEFS), {"t": "deals"})).all()

    assert {"ix_deals_vendor_id", "ix_deals_solution_id"} <= {r[0] for r in rows}


async def test_deals_check_requires_vendor_for_solution(session: AsyncSession) -> None:
    code = await _deal(session)
    sap = await insert_vendor(session, "SAP")
    solution = await insert_solution(session, sap, "Cloud")

    with pytest.raises(IntegrityError, match="ck_deals_solution_needs_vendor"):
        await link_deal(session, code, None, solution)


async def test_a_deal_may_have_a_vendor_without_a_solution(session: AsyncSession) -> None:
    code = await _deal(session)

    await link_deal(session, code, await insert_vendor(session, "SAP"), None)


async def test_a_deal_with_a_solution_of_another_vendor_is_rejected(session: AsyncSession) -> None:
    code = await _deal(session)
    sap = await insert_vendor(session, "SAP")
    oracle = await insert_vendor(session, "Oracle")
    other_solution = await insert_solution(session, oracle, "EBS")

    with pytest.raises(IntegrityError, match="fk_deals_solution"):
        await link_deal(session, code, sap, other_solution)


async def test_a_deal_with_a_matching_vendor_and_solution_is_accepted(
    session: AsyncSession,
) -> None:
    code = await _deal(session)
    sap = await insert_vendor(session, "SAP")

    await link_deal(session, code, sap, await insert_solution(session, sap, "Cloud"))


async def test_a_vendor_used_by_a_deal_cannot_be_deleted(session: AsyncSession) -> None:
    code = await _deal(session)
    sap = await insert_vendor(session, "SAP")
    await link_deal(session, code, sap, None)

    with pytest.raises(IntegrityError, match="fk_deals_vendor_id_vendors"):
        await session.execute(text("delete from vendors where id = :id"), {"id": sap})


async def test_a_solution_used_by_a_deal_cannot_be_deleted(session: AsyncSession) -> None:
    code = await _deal(session)
    sap = await insert_vendor(session, "SAP")
    solution = await insert_solution(session, sap, "Cloud")
    await link_deal(session, code, sap, solution)

    with pytest.raises(IntegrityError, match="fk_deals_solution"):
        await session.execute(text("delete from solutions where id = :id"), {"id": solution})


async def test_deleting_the_deal_releases_the_vendor(session: AsyncSession) -> None:
    code = await _deal(session)
    sap = await insert_vendor(session, "SAP")
    await link_deal(session, code, sap, None)
    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    await session.execute(text("delete from vendors where id = :id"), {"id": sap})
