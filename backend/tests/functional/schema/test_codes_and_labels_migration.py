"""Feature: 운영자는 코드·BANT Label 리비전을 올리고 내려 기본값 시드와 구조를 확인할 수 있다.

When: 운영자 명령(alembic upgrade/downgrade). 리비전 `c5d8e2f4a916`은 codes(Status 7, Forecast 6)와
bant_labels(기본 Label 23)를 만들고 시드한다. 내리면 두 테이블이 사라지고 기존 데이터는 그대로다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    given_schema_at,
    index_names,
    table_names,
    then_schema_is_at,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.revisions import CODES_REVISION, USER_FK_REVISION
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

COUNT_CODES = "select kind, count(*) from codes group by kind order by kind"
COUNT_LABELS = "select category, count(*) from bant_labels group by category order by category"
SEEDED_CODES = [("forecast", 6), ("status", 7)]
SEEDED_LABELS = [("authority", 6), ("budget", 7), ("need", 5), ("timeline", 5)]  # 합계 23
NEW_TABLES = {"codes", "bant_labels"}


async def test_upgrade_creates_the_tables_and_seeds_the_documented_defaults(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 두 테이블이 생기고 Status 7, Forecast 6, 기본 Label 23개가 시드된다."""
    # Given
    await given_schema_at(blank_database, USER_FK_REVISION)
    assert not NEW_TABLES & await table_names(blank_database)
    # When
    await when_operator_upgrades(blank_database, target=CODES_REVISION)
    # Then
    await then_schema_is_at(blank_database, CODES_REVISION)
    assert await table_names(blank_database) >= NEW_TABLES
    assert await run_sql(blank_database, COUNT_CODES) == SEEDED_CODES
    assert await run_sql(blank_database, COUNT_LABELS) == SEEDED_LABELS
    assert sum(count for _, count in SEEDED_LABELS) == 23
    assert await run_sql(
        blank_database,
        "select count(*) from bant_labels where is_default and created_by_user_id is null",
    ) == [(23,)]


async def test_upgrade_creates_the_unique_and_lookup_indexes(blank_database: URL) -> None:
    """Scenario: 올리면 코드·Label의 이름 유니크 인덱스와 생성자 조회 인덱스가 생긴다."""
    # Given
    await given_schema_at(blank_database, USER_FK_REVISION)
    # When
    await when_operator_upgrades(blank_database, target=CODES_REVISION)
    # Then
    assert {"uq_codes_kind_key", "uq_codes_kind_name_lower"} <= await index_names(
        blank_database, "codes"
    )
    assert {
        "uq_bant_labels_category_name_lower",
        "ix_bant_labels_created_by_user_id",
    } <= await index_names(blank_database, "bant_labels")


async def test_downgrade_drops_both_tables_and_keeps_existing_users(blank_database: URL) -> None:
    """Scenario: 내리면 두 테이블이 사라지고 기존 사용자 데이터는 그대로다."""
    # Given
    await given_schema_at(blank_database, USER_FK_REVISION)
    await run_sql(
        blank_database,
        "insert into users (id, login_id, role, created_by_user_id, created_at, updated_at)"
        " values ('00000000-0000-0000-0000-000000000001', 'KIM', 'user',"
        " '00000000-0000-0000-0000-000000000001', now(), now())",
    )
    await when_operator_upgrades(blank_database, target=CODES_REVISION)
    # When
    await when_operator_downgrades(blank_database, target=USER_FK_REVISION)
    # Then
    await then_schema_is_at(blank_database, USER_FK_REVISION)
    assert not NEW_TABLES & await table_names(blank_database)
    assert await run_sql(blank_database, "select login_id from users") == [("KIM",)]


async def test_upgrade_after_downgrade_seeds_the_same_defaults_again(blank_database: URL) -> None:
    """Scenario: 내렸다가 다시 올려도 시드가 중복 없이 같은 개수로 복원된다."""
    # Given
    await given_schema_at(blank_database, CODES_REVISION)
    await when_operator_downgrades(blank_database, target=USER_FK_REVISION)
    # When
    await when_operator_upgrades(blank_database, target=CODES_REVISION)
    # Then
    assert await run_sql(blank_database, COUNT_CODES) == SEEDED_CODES
    assert await run_sql(blank_database, COUNT_LABELS) == SEEDED_LABELS
