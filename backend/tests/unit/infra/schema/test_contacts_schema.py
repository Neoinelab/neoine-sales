"""contacts 테이블과 deals FK의 head 스키마 점검(AC-16): 열·제약 이름·인덱스·FK 동작.

고객·파트너 두 테이블이 contacts 하나로 통합됐다. 공백 문자 금지 CHECK는 DB 로케일에 따라 전각
공백을 못 거를 수 있어(로케일 의존) 여기서는 ASCII 공백·탭·줄바꿈만 확인하고, 전각 공백은 응용
검증(tests/unit/domain/test_contact_values.py, functional contacts)이 맡는다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_contact

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMNS = {
    "id": ("uuid", None, "NO"),
    "kind": ("character varying", 10, "NO"),
    "company": ("character varying", 200, "NO"),
    "name": ("character varying", 100, "NO"),
    "title": ("character varying", 100, "YES"),
    "email": ("character varying", 254, "YES"),
    "phone": ("character varying", 40, "YES"),
    "created_at": ("timestamp with time zone", None, "NO"),
    "updated_at": ("timestamp with time zone", None, "NO"),
}


async def _names(session: AsyncSession, sql: str) -> set[str]:
    return {str(row[0]) for row in (await session.execute(text(sql))).all()}


async def test_contacts_table_has_the_planned_columns(session: AsyncSession) -> None:
    rows = (
        await session.execute(
            text(
                "select column_name, data_type, character_maximum_length, is_nullable"
                " from information_schema.columns"
                " where table_schema = 'public' and table_name = 'contacts'"
            )
        )
    ).all()

    assert {r[0]: (r[1], r[2], r[3]) for r in rows} == COLUMNS


async def test_customers_and_partners_tables_are_gone(session: AsyncSession) -> None:
    tables = await _names(session, "select tablename from pg_tables where schemaname = 'public'")

    assert "contacts" in tables
    assert not {"customers", "partners"} & tables


async def test_contacts_has_the_planned_constraints_and_indexes(session: AsyncSession) -> None:
    constraints = await _names(
        session, "select conname from pg_constraint where conrelid = 'contacts'::regclass"
    )
    indexes = await _names(session, "select indexname from pg_indexes where tablename = 'contacts'")

    assert {"ck_contacts_kind_valid", "ck_contacts_no_space"} <= constraints
    assert {
        "ix_contacts_kind_company_lower",
        "ix_contacts_identity",
        "ix_contacts_created_at_id",
    } <= indexes


async def test_the_lookup_indexes_are_case_insensitive_expression_indexes(
    session: AsyncSession,
) -> None:
    rows = (
        await session.execute(
            text(
                "select indexname, indexdef from pg_indexes where tablename = 'contacts'"
                " and indexname in ('ix_contacts_kind_company_lower', 'ix_contacts_identity')"
            )
        )
    ).all()

    definitions = {str(r[0]): str(r[1]).lower() for r in rows}
    assert "lower(" in definitions["ix_contacts_kind_company_lower"]
    assert definitions["ix_contacts_identity"].count("lower(") == 2


async def test_unknown_kind_is_rejected_by_the_database(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_contacts_kind_valid"):
        await insert_contact(session, kind="supplier")


@pytest.mark.parametrize("kind", ["customer", "partner"])
async def test_both_kinds_are_accepted(session: AsyncSession, kind: str) -> None:
    contact_id = await insert_contact(session, kind=kind)

    stored = await session.execute(
        text("select kind from contacts where id = :id"), {"id": contact_id}
    )

    assert stored.scalar_one() == kind


@pytest.mark.parametrize("field", ["company", "name", "email", "phone"])
@pytest.mark.parametrize("value", ["a b", "a\tb", "a\nb", " a", "a "])
async def test_whitespace_in_company_name_email_or_phone_is_rejected_by_the_database(
    session: AsyncSession, field: str, value: str
) -> None:
    with pytest.raises(IntegrityError, match="ck_contacts_no_space"):
        await insert_contact(session, **{field: value})


async def test_title_may_contain_spaces(session: AsyncSession) -> None:
    contact_id = await insert_contact(session, title="수석 과장")

    stored = await session.execute(
        text("select title from contacts where id = :id"), {"id": contact_id}
    )

    assert stored.scalar_one() == "수석 과장"


@pytest.mark.parametrize("field", ["company", "name"])
async def test_company_and_name_are_required_by_the_database(
    session: AsyncSession, field: str
) -> None:
    with pytest.raises(IntegrityError, match=field):
        await insert_contact(session, **{field: None})


async def test_deal_references_to_contacts_are_restrict_foreign_keys(
    session: AsyncSession,
) -> None:
    rows = (
        await session.execute(
            text(
                "select c.conrelid::regclass::text, c.conname, c.confdeltype::text,"
                " c.condeferrable from pg_constraint c where c.contype = 'f'"
                " and c.conrelid in ('deals'::regclass, 'deal_partners'::regclass)"
                " and c.confrelid = 'contacts'::regclass"
            )
        )
    ).all()

    assert {(str(r[0]), str(r[1])): (str(r[2]).strip(), bool(r[3])) for r in rows} == {
        ("deals", "fk_deals_customer_id_contacts"): ("r", False),
        ("deal_partners", "fk_deal_partners_contact_id_contacts"): ("r", False),
    }


async def test_no_foreign_key_still_points_at_the_dropped_tables(session: AsyncSession) -> None:
    names = await _names(session, "select conname from pg_constraint where contype = 'f'")

    assert "fk_deals_customer_id_customers" not in names
    assert "fk_deals_partner_id_partners" not in names
