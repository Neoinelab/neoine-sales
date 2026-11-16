"""head 스키마의 vendors, deals의 Vendor 참조와 Product 텍스트 컬럼.

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
    """vendors 테이블은 기대한 컬럼·타입·기본 키를 가진다."""
    # when: 컬럼과 제약을 조회한다
    columns = await _columns(session, "vendors")
    constraints = await _constraints(session, "vendors")

    # then: 컬럼 집합, name 타입, id 타입, 기본 키가 기대와 같다
    assert set(columns) == {"id", "name", "created_at", "updated_at"}
    assert columns["name"] == ("character varying", 100, "NO")
    assert columns["id"][0] == "bigint"
    assert constraints["pk_vendors"][0] == "p"


async def test_vendor_name_is_unique_ignoring_case(session: AsyncSession) -> None:
    """Vendor 이름은 대소문자를 무시하고 유일하다."""
    # given: SAP Vendor가 있다
    await insert_vendor(session, "SAP")

    # when·then: sap를 넣으면 유니크 인덱스 위반이다
    with pytest.raises(IntegrityError, match="uq_vendors_name_lower"):
        await insert_vendor(session, "sap")


async def test_the_vendor_name_index_is_a_unique_lower_name_index(session: AsyncSession) -> None:
    """Vendor 이름 인덱스는 lower(name) 유니크 인덱스다."""
    # when: vendors의 인덱스 정의를 조회한다
    rows = (await session.execute(text(INDEX_DEFS), {"t": "vendors"})).all()
    definitions = {r[0]: r[1] for r in rows}

    # then: 유니크이고 lower를 쓴다
    assert "UNIQUE" in definitions["uq_vendors_name_lower"]
    assert "lower" in definitions["uq_vendors_name_lower"]


async def test_solutions_table_does_not_exist(session: AsyncSession) -> None:
    """solutions 테이블은 없다."""
    # when: solutions 테이블 존재를 조회한다
    exists = (await session.execute(text("select to_regclass('public.solutions')"))).scalar_one()

    # then: 없다
    assert exists is None


async def test_deals_product_is_not_null_varchar_200(session: AsyncSession) -> None:
    """deals.product는 NOT NULL varchar(200)이다."""
    # when: deals 컬럼을 조회한다
    columns = await _columns(session, "deals")

    # then: product가 NOT NULL varchar(200)이다
    assert columns["product"] == ("character varying", 200, "NO")


async def test_deals_product_has_no_database_default(session: AsyncSession) -> None:
    """deals.product에는 DB 기본값이 없다."""
    # when: product 컬럼의 기본값을 조회한다
    default = (
        await session.execute(
            text(
                "select column_default from information_schema.columns"
                " where table_name = 'deals' and column_name = 'product'"
            )
        )
    ).scalar_one()

    # then: 기본값이 없다
    assert default is None


async def test_deals_has_no_solution_id_or_its_constraints(session: AsyncSession) -> None:
    """deals에는 solution_id와 그 제약·인덱스가 없다."""
    # when: deals의 컬럼·제약·인덱스를 조회한다
    columns = await _columns(session, "deals")
    constraints = await _constraints(session, "deals")
    indexes = {r[0] for r in (await session.execute(text(INDEX_DEFS), {"t": "deals"})).all()}

    # then: 예전 컬럼·제약·인덱스가 없다
    assert "solution_id" not in columns
    assert "vendor" not in columns
    assert "fk_deals_solution" not in constraints
    assert "ck_deals_solution_needs_vendor" not in constraints
    assert "ix_deals_solution_id" not in indexes


async def test_deals_vendor_id_is_a_not_null_bigint(session: AsyncSession) -> None:
    """deals.vendor_id는 NULL을 허용하지 않는 bigint다(Vendor 필수)."""
    # when: deals 컬럼을 조회한다
    columns = await _columns(session, "deals")

    # then: vendor_id가 NOT NULL bigint다
    assert columns["vendor_id"][0] == "bigint"
    assert columns["vendor_id"][2] == "NO"


async def test_deals_reference_vendors_with_restrict(session: AsyncSession) -> None:
    """deals는 vendors를 RESTRICT로 참조한다."""
    # when: deals 제약을 조회한다
    constraints = await _constraints(session, "deals")

    # then: vendors를 RESTRICT로 참조하는 외래 키다
    assert constraints["fk_deals_vendor_id_vendors"][1:] == ("vendors", "r", 1)


async def test_deals_have_a_vendor_index_and_no_product_index(session: AsyncSession) -> None:
    """deals에는 vendor_id 인덱스가 있다."""
    # when: deals 인덱스를 조회한다
    rows = (await session.execute(text(INDEX_DEFS), {"t": "deals"})).all()

    # then: vendor_id 인덱스가 있다
    assert "ix_deals_vendor_id" in {r[0] for r in rows}


async def test_a_deal_vendor_cannot_be_null(session: AsyncSession) -> None:
    """Deal의 Vendor를 NULL로 바꿀 수 없다(Vendor 필수)."""
    # given: Deal 하나
    code = await _deal(session)

    # when·then: vendor_id를 NULL로 갱신하면 NOT NULL 위반이다
    with pytest.raises(DBAPIError, match="not-null"):
        await link_deal(session, code, None, "ITDR")


async def test_a_deal_may_have_a_product_text_with_a_vendor(session: AsyncSession) -> None:
    """Deal은 Vendor와 함께 Product 텍스트를 가질 수 있다."""
    # given: Deal 하나
    code = await _deal(session)

    # when: Vendor와 Product 텍스트를 연결한다
    await link_deal(session, code, await insert_vendor(session, "SAP"), "ITDR")

    # then: Product 텍스트가 저장된다
    stored = (
        await session.execute(
            text("select product from deals where deal_code = :code"), {"code": code}
        )
    ).scalar_one()
    assert stored == "ITDR"


async def test_a_deal_may_have_a_vendor_without_a_product_text(session: AsyncSession) -> None:
    """Deal은 Product 텍스트 없이 Vendor만 가질 수 있다."""
    # given: Deal 하나
    code = await _deal(session)

    # when·then: 빈 Product로 Vendor를 연결해도 오류가 없다
    await link_deal(session, code, await insert_vendor(session, "SAP"), "")


async def test_a_deal_product_longer_than_200_is_rejected(session: AsyncSession) -> None:
    """200자를 넘는 Product는 거부한다."""
    # given: Deal 하나
    code = await _deal(session)

    # when·then: 201자 Product를 연결하면 길이 초과 오류가 난다
    with pytest.raises(DBAPIError, match="too long"):
        await link_deal(session, code, await insert_vendor(session, "SAP"), "a" * 201)


async def test_a_deal_product_cannot_be_null(session: AsyncSession) -> None:
    """Product를 NULL로 바꿀 수 없다."""
    # given: Deal 하나
    code = await _deal(session)

    # when·then: product를 NULL로 갱신하면 NOT NULL 위반이다
    with pytest.raises(IntegrityError, match="product"):
        await session.execute(
            text("update deals set product = null where deal_code = :code"), {"code": code}
        )


async def test_a_vendor_used_by_a_deal_cannot_be_deleted(session: AsyncSession) -> None:
    """Deal이 쓰는 Vendor는 삭제할 수 없다."""
    # given: Vendor를 쓰는 Deal
    code = await _deal(session)
    sap = await insert_vendor(session, "SAP")
    await link_deal(session, code, sap)

    # when·then: Vendor를 지우면 외래 키 위반이다
    with pytest.raises(IntegrityError, match="fk_deals_vendor_id_vendors"):
        await session.execute(text("delete from vendors where id = :id"), {"id": sap})


async def test_deleting_the_deal_releases_the_vendor(session: AsyncSession) -> None:
    """Deal을 지우면 Vendor를 삭제할 수 있다."""
    # given: Vendor를 쓰던 Deal을 삭제했다
    code = await _deal(session)
    sap = await insert_vendor(session, "SAP")
    await link_deal(session, code, sap)
    await session.execute(text("delete from deals where deal_code = :code"), {"code": code})

    # when·then: Vendor를 지워도 오류가 없다
    await session.execute(text("delete from vendors where id = :id"), {"id": sap})
