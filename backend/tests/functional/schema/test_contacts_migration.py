"""Feature: 운영자는 연락처 통합 리비전을 올리고 내려 customers·partners가 contacts로 바뀐 걸 본다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 `c5d8e2f4a916`(코드·Label) 다음에 오는
새 리비전이다. 올리면 contacts가 생기고 deals의 고객·파트너 FK가 contacts를 가리키며 customers·
partners는 없다(AC-16). 내리면 구조만 복원하고(데이터 복원 없음) 다시 올릴 수 있다.
보존 데이터 없음 전제(사용자 결정 2026-10-15)라 데이터 이전은 검증하지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    column_names,
    given_schema_at,
    index_names,
    table_names,
    table_structure,
    then_schema_is_at,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.revisions import CODES_REVISION, contacts_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

RETIRED = {"customers", "partners"}
RESTORED_TABLES = (
    "customers",
    "partners",
    "deals",
)  # 내리면 이전 리비전 구조로 돌아와야 하는 테이블
DEAL_FKS = (  # deals의 고객·파트너 FK(이름, 가리키는 테이블, 삭제 동작)
    "select c.conname, c.confrelid::regclass::text, c.confdeltype::text from pg_constraint c"
    " where c.conrelid = 'deals'::regclass and c.contype = 'f'"
    " and c.conname in ('fk_deals_customer_id_contacts', 'fk_deals_partner_id_contacts',"
    " 'fk_deals_customer_id_customers', 'fk_deals_partner_id_partners')"
)
COUNT_CODES = "select kind, count(*) from codes group by kind order by kind"
SEEDED_CODES = [("forecast", 6), ("status", 7)]


async def test_upgrade_creates_contacts_and_drops_customers_and_partners(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 contacts가 생기고 customers·partners는 사라진다."""
    # Given
    await given_schema_at(blank_database, CODES_REVISION)
    assert await table_names(blank_database) >= RETIRED
    # When
    await when_operator_upgrades(blank_database, target=contacts_revision())
    # Then
    await then_schema_is_at(blank_database, contacts_revision())
    tables = await table_names(blank_database)
    assert "contacts" in tables
    assert not RETIRED & tables
    assert await column_names(blank_database, "contacts") == {
        "id",
        "kind",
        "company",
        "name",
        "title",
        "email",
        "phone",
        "created_at",
        "updated_at",
    }


async def test_upgrade_repoints_the_deal_foreign_keys_to_contacts(blank_database: URL) -> None:
    """Scenario: 올리면 deals의 고객·파트너 FK가 contacts를 RESTRICT로 가리킨다."""
    # Given
    await given_schema_at(blank_database, CODES_REVISION)
    # When
    await when_operator_upgrades(blank_database, target=contacts_revision())
    # Then
    rows = await run_sql(blank_database, DEAL_FKS)
    assert {(str(r[0]), str(r[1]), str(r[2]).strip()) for r in rows} == {
        ("fk_deals_customer_id_contacts", "contacts", "r"),
        ("fk_deals_partner_id_contacts", "contacts", "r"),
    }


async def test_upgrade_creates_the_contact_constraints_and_indexes(blank_database: URL) -> None:
    """Scenario: 올리면 contacts의 CHECK 제약과 조회 인덱스가 생긴다."""
    # Given
    await given_schema_at(blank_database, CODES_REVISION)
    # When
    await when_operator_upgrades(blank_database, target=contacts_revision())
    # Then
    constraints = await run_sql(
        blank_database, "select conname from pg_constraint where conrelid = 'contacts'::regclass"
    )
    assert {"ck_contacts_kind_valid", "ck_contacts_no_space"} <= {str(r[0]) for r in constraints}
    assert {
        "ix_contacts_kind_company_lower",
        "ix_contacts_identity",
        "ix_contacts_created_at_id",
    } <= await index_names(blank_database, "contacts")


async def test_upgrade_keeps_the_codes_and_labels_from_the_previous_revision(
    blank_database: URL,
) -> None:
    """Scenario: 올려도 앞 리비전이 만든 코드·Label 시드는 그대로다."""
    # Given
    await given_schema_at(blank_database, CODES_REVISION)
    # When
    await when_operator_upgrades(blank_database, target=contacts_revision())
    # Then
    assert await run_sql(blank_database, COUNT_CODES) == SEEDED_CODES
    assert await run_sql(blank_database, "select count(*) from bant_labels") == [(23,)]


async def test_downgrade_restores_the_old_tables_empty_and_drops_contacts(
    blank_database: URL,
) -> None:
    """Scenario: 내리면 customers·partners 구조가 빈 테이블로 복원되고 contacts는 사라진다."""
    # Given
    await given_schema_at(blank_database, contacts_revision())
    await run_sql(
        blank_database,
        "insert into contacts (id, kind, company, name, created_at, updated_at)"
        " values (gen_random_uuid(), 'customer', '회사', '담당', now(), now())",
    )
    # When
    await when_operator_downgrades(blank_database, target=CODES_REVISION)
    # Then
    await then_schema_is_at(blank_database, CODES_REVISION)
    tables = await table_names(blank_database)
    assert tables >= RETIRED
    assert "contacts" not in tables
    assert {"company_name", "contact_name", "email", "phone", "employee_count"} <= (
        await column_names(blank_database, "customers")
    )
    assert {"company_name", "contact_name", "email", "phone"} <= (
        await column_names(blank_database, "partners")
    )
    assert await run_sql(blank_database, "select count(*) from customers") == [(0,)]
    assert await run_sql(blank_database, "select count(*) from partners") == [(0,)]


async def test_downgrade_restores_the_exact_structure_of_the_previous_revision(
    blank_database: URL,
) -> None:
    """Scenario: 내리면 customers·partners·deals가 이전 리비전과 열·제약·인덱스까지 같다."""
    # Given
    await given_schema_at(blank_database, CODES_REVISION)
    before = {table: await table_structure(blank_database, table) for table in RESTORED_TABLES}
    await when_operator_upgrades(blank_database, target=contacts_revision())
    # When
    await when_operator_downgrades(blank_database, target=CODES_REVISION)
    # Then
    after = {table: await table_structure(blank_database, table) for table in RESTORED_TABLES}
    assert after == before


async def test_downgrade_restores_the_old_deal_foreign_keys(blank_database: URL) -> None:
    """Scenario: 내리면 deals의 FK가 다시 customers·partners를 RESTRICT로 가리킨다."""
    # Given
    await given_schema_at(blank_database, contacts_revision())
    # When
    await when_operator_downgrades(blank_database, target=CODES_REVISION)
    # Then
    rows = await run_sql(blank_database, DEAL_FKS)
    assert {(str(r[0]), str(r[1]), str(r[2]).strip()) for r in rows} == {
        ("fk_deals_customer_id_customers", "customers", "r"),
        ("fk_deals_partner_id_partners", "partners", "r"),
    }


async def test_upgrade_after_downgrade_creates_contacts_again(blank_database: URL) -> None:
    """Scenario: 내렸다가 다시 올려도 contacts가 만들어지고 customers·partners는 다시 사라진다."""
    # Given
    await given_schema_at(blank_database, contacts_revision())
    await when_operator_downgrades(blank_database, target=CODES_REVISION)
    # When
    await when_operator_upgrades(blank_database, target=contacts_revision())
    # Then
    await then_schema_is_at(blank_database, contacts_revision())
    tables = await table_names(blank_database)
    assert "contacts" in tables
    assert not RETIRED & tables
    assert await run_sql(blank_database, COUNT_CODES) == SEEDED_CODES
