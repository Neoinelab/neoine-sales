"""Feature: 운영자는 deleted_at 제거 리비전을 안전하게 올리고 내릴 수 있다(AC1~AC4).

When: 운영자 명령(alembic upgrade/downgrade). `e3a9c41b7d52` 스키마에 행을 넣어 두고 적용한다.
deleted_at 값이 있는 행이 하나라도 있으면 데이터를 지우지 않고 `<테이블>=<건수>`가 담긴
RuntimeError로 중단해야 하며 스키마는 그대로여야 한다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

from tests.functional.steps.schema import (
    given_schema_at,
    then_command_aborted,
    then_schema_is_at,
    when_operator_attempts_upgrade,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.drop_deleted_at import (
    CODE,
    PREVIOUS_HEAD,
    TABLES,
    deleted_at_tables,
    row_counts,
    run_sql,
    seed,
    user_index_names,
)
from tests.support.revisions import DROP_DELETED_AT_REVISION as DROP_REVISION

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

DUPLICATE_LOGIN_INSERT = (
    "insert into users (id, login_id, role, created_by, created_at, updated_at)"
    " values (gen_random_uuid(), 'KIM', 'user', 'a', now(), now())"
)


@pytest.mark.parametrize("table", TABLES)
async def test_upgrade_aborts_and_keeps_everything_when_a_row_is_soft_deleted(
    blank_database: URL, table: str
) -> None:
    """Scenario: 소프트 삭제된 행이 하나라도 있으면 올리기가 중단되고 스키마·데이터가 그대로다."""
    # Given
    await given_schema_at(blank_database, PREVIOUS_HEAD)
    await seed(blank_database, soft_deleted=[table])
    before = await row_counts(blank_database)
    # When
    outcome = await when_operator_attempts_upgrade(blank_database, target=DROP_REVISION)
    # Then
    then_command_aborted(outcome, f"{table}=1")
    assert await deleted_at_tables(blank_database) == set(TABLES)  # 컬럼 하나도 지워지지 않았다
    assert await row_counts(blank_database) == before  # 행도 그대로
    assert await user_index_names(blank_database) == {"uq_users_login_id_active"}
    await then_schema_is_at(blank_database, PREVIOUS_HEAD)


async def test_upgrade_reports_every_table_with_soft_deleted_rows(blank_database: URL) -> None:
    """Scenario: 소프트 삭제된 행이 있는 테이블을 모두 알리고, 없는 테이블은 알리지 않는다."""
    # Given
    await given_schema_at(blank_database, PREVIOUS_HEAD)
    await seed(blank_database, soft_deleted=["customers", "users"])
    # When
    outcome = await when_operator_attempts_upgrade(blank_database, target=DROP_REVISION)
    # Then
    then_command_aborted(outcome, "customers=1", "users=1")
    assert outcome.error is not None
    assert "partners=" not in str(outcome.error)
    assert await deleted_at_tables(blank_database) == set(TABLES)


async def test_upgrade_drops_columns_and_keeps_all_rows_when_none_is_soft_deleted(
    blank_database: URL,
) -> None:
    """Scenario: 소프트 삭제된 행이 없으면 deleted_at만 지우고 모든 행·로그인 유니크를 유지한다."""
    # Given
    await given_schema_at(blank_database, PREVIOUS_HEAD)
    await seed(blank_database)
    before = await row_counts(blank_database)
    # When
    await when_operator_upgrades(blank_database, target=DROP_REVISION)
    # Then
    assert await deleted_at_tables(blank_database) == set()
    assert await row_counts(blank_database) == before
    assert await run_sql(blank_database, "select code from deals") == [(CODE,)]
    assert await user_index_names(blank_database) == {"uq_users_login_id"}
    with pytest.raises(IntegrityError, match="uq_users_login_id"):
        await run_sql(blank_database, DUPLICATE_LOGIN_INSERT)


async def test_downgrade_restores_nullable_deleted_at_and_partial_unique_index_losslessly(
    blank_database: URL,
) -> None:
    """Scenario: 내리면 NULL 허용 deleted_at과 부분 유니크 인덱스가 복원되고 행은 손실이 없다."""
    # Given
    await given_schema_at(blank_database, PREVIOUS_HEAD)
    await seed(blank_database)
    await when_operator_upgrades(blank_database, target=DROP_REVISION)
    before = await row_counts(blank_database)
    # When
    await when_operator_downgrades(blank_database, target=PREVIOUS_HEAD)
    # Then
    assert await deleted_at_tables(blank_database) == set(TABLES)
    nullable = await run_sql(
        blank_database,
        "select count(*) from information_schema.columns where column_name = 'deleted_at'"
        " and is_nullable = 'YES' and table_name in"
        " ('customers','partners','deals','deal_actions','users')",
    )
    assert nullable == [(5,)]
    assert await row_counts(blank_database) == before
    assert await run_sql(
        blank_database, "select count(*) from users where deleted_at is not null"
    ) == [(0,)]
    assert await user_index_names(blank_database) == {"uq_users_login_id_active"}
    definition = await run_sql(
        blank_database,
        "select indexdef from pg_indexes where indexname = 'uq_users_login_id_active'",
    )
    assert "deleted_at IS NULL" in str(definition[0][0])


async def test_upgrade_after_downgrade_drops_the_columns_again(blank_database: URL) -> None:
    """Scenario: 내렸던 deleted_at 제거 리비전을 다시 올리면 컬럼이 다시 사라지고 행은 유지된다."""
    # Given
    await given_schema_at(blank_database, PREVIOUS_HEAD)
    await seed(blank_database)
    await when_operator_upgrades(blank_database, target=DROP_REVISION)
    before = await row_counts(blank_database)
    await when_operator_downgrades(blank_database, target=PREVIOUS_HEAD)
    # When
    await when_operator_upgrades(blank_database, target=DROP_REVISION)
    # Then
    assert await deleted_at_tables(blank_database) == set()
    assert await row_counts(blank_database) == before
