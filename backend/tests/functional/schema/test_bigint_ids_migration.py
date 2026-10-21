"""Feature: 운영자는 BIGINT id 리비전으로 올려 업무 데이터를 모두 지우고 새 스키마·시드를 얻는다.

When: 운영자 명령(alembic upgrade/downgrade). 이 리비전은 `e8c2b4f6a1d9`(UUID 스키마) 바로
다음이고 head다. 올리면 모든 앱 테이블을 가드 없이(플래그·데이터 점검 없이) 지우고 BIGINT
IDENTITY 스키마로 다시 만든 뒤 기본 시드(코드 13, BANT Label 23, Action 유형 8)를 넣는다.
이전 저장 위치(path)는 WARNING 로그로 알리고 디스크는 건드리지 않는다. 내리는 것은 한국어
사유의 RuntimeError로 거부하고 버전·스키마·데이터를 그대로 둔다(복구는 배포 전 백업 복원뿐).
"""

import logging
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.bigint_ids import (
    BUSINESS_TABLES,
    given_business_data_before_the_bigint_revision,
    given_storage_path_before_the_bigint_revision,
    row_count,
    then_business_tables_are_empty,
    then_seed_rows_are_present,
    uuid_columns,
)
from tests.functional.steps.schema import (
    given_rows,
    given_schema_at,
    table_names,
    table_structure,
    then_command_aborted,
    then_command_succeeded,
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_attempts_upgrade,
    when_operator_upgrades,
)
from tests.support.head_rows import insert_user
from tests.support.revisions import bigint_ids_revision, deals_users_required_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

USERS_REQUIRED_REVISION = "e8c2b4f6a1d9"  # 이 아래는 UUID 스키마
NOT_REVERSIBLE = "되돌릴 수 없습니다"
RESTORE_FROM_BACKUP = "백업"
NEXT_ID_AFTER_SEED = (
    "insert into action_types (name, is_default, created_at, updated_at)"
    " values ('ZZ 새 유형', false, now(), now()) returning id"
)


async def test_operator_upgrade_from_empty_creates_bigint_keys_and_seeds(
    blank_database: URL,
) -> None:
    """Scenario: 빈 DB를 head로 올리면 uuid 컬럼이 없고 기본 시드가 있다(AC-1·6)."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, bigint_ids_revision())
    assert await uuid_columns(blank_database) == []
    await then_seed_rows_are_present(blank_database)
    await then_business_tables_are_empty(blank_database)


async def test_operator_upgrade_continues_numbering_after_the_seed_rows(
    blank_database: URL,
) -> None:
    """Scenario: 시드가 쓴 번호 다음부터 새 행이 번호를 받는다(시드도 같은 시퀀스를 쓴다)."""
    # Given
    await when_operator_upgrades(blank_database)
    seed_max = (await run_sql(blank_database, "select max(id) from action_types"))[0][0]
    # When
    created = await run_sql(blank_database, NEXT_ID_AFTER_SEED)
    # Then
    assert created[0][0] > seed_max


async def test_operator_upgrade_clears_all_business_data_without_any_flag(
    blank_database: URL,
) -> None:
    """Scenario: 업무 데이터가 있는 e8c2b4f6a1d9 DB도 플래그 없이 올라가고 시드만 남는다(AC-7)."""
    # Given
    await given_business_data_before_the_bigint_revision(blank_database)
    # When
    outcome = await when_operator_attempts_upgrade(blank_database)
    # Then
    then_command_succeeded(outcome)
    await then_schema_is_at(blank_database, bigint_ids_revision())
    await then_business_tables_are_empty(blank_database)
    await then_seed_rows_are_present(blank_database)
    assert await uuid_columns(blank_database) == []


async def test_operator_upgrade_of_a_seed_only_database_succeeds(blank_database: URL) -> None:
    """Scenario: 시드만 있는 e8c2b4f6a1d9 DB도 성공하고 새 시드가 있다(AC-7)."""
    # Given
    await given_schema_at(blank_database, deals_users_required_revision())
    # When
    outcome = await when_operator_attempts_upgrade(blank_database)
    # Then
    then_command_succeeded(outcome)
    await then_seed_rows_are_present(blank_database)
    await then_business_tables_are_empty(blank_database)


async def test_operator_sees_the_previous_storage_path_in_the_log(
    blank_database: URL, caplog: pytest.LogCaptureFixture
) -> None:
    """Scenario: 올리기 직전 저장 위치가 있으면 그 경로가 WARNING 로그에 남는다(AC-8)."""
    # Given
    await given_storage_path_before_the_bigint_revision(blank_database, "/x")
    # When
    with caplog.at_level(logging.WARNING):
        await when_operator_upgrades(blank_database)
    # Then
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("/x" in message for message in warnings), warnings
    assert any("수동" in message for message in warnings), warnings  # 남은 첨부 파일은 수동 정리


async def test_operator_upgrade_leaves_the_files_on_disk_alone(
    blank_database: URL, tmp_path: Path
) -> None:
    """Scenario: 마이그레이션은 경로만 알리고 디스크의 파일은 지우지 않는다(AC-8)."""
    # Given
    storage = tmp_path / "files"
    leftover = storage / "20261016-A001" / ("a" * 32)
    leftover.parent.mkdir(parents=True)
    leftover.write_bytes(b"attachment bytes")
    await given_storage_path_before_the_bigint_revision(blank_database, str(storage))
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert leftover.read_bytes() == b"attachment bytes"
    assert await row_count(blank_database, "storage_settings") == 0  # DB에서는 분리된다


async def test_operator_sees_no_storage_warning_when_no_path_was_saved(
    blank_database: URL, caplog: pytest.LogCaptureFixture
) -> None:
    """Scenario: 저장 위치가 없던 DB는 저장 위치 경고 없이 올라간다."""
    # Given
    await given_schema_at(blank_database, deals_users_required_revision())
    # When
    with caplog.at_level(logging.WARNING):
        await when_operator_upgrades(blank_database)
    # Then
    assert [r for r in caplog.records if "첨부" in r.getMessage()] == []


@pytest.mark.parametrize("target", ["-1", "base", USERS_REQUIRED_REVISION])
async def test_operator_downgrade_from_the_bigint_revision_is_refused_and_changes_nothing(
    blank_database: URL, target: str
) -> None:
    """Scenario: head에서 이 리비전 아래로 내리면 거부되고 버전·스키마·데이터가 그대로다(AC-9)."""
    # Given
    await when_operator_upgrades(blank_database)

    async def one_user(session: AsyncSession) -> None:
        await insert_user(session, "kim")

    await given_rows(blank_database, one_user)
    tables = await table_names(blank_database)
    users_structure = await table_structure(blank_database, "users")
    # When
    outcome = await when_operator_attempts_downgrade(blank_database, target=target)
    # Then
    then_command_aborted(outcome, NOT_REVERSIBLE, RESTORE_FROM_BACKUP)
    await then_schema_is_at(blank_database, bigint_ids_revision())
    assert await row_count(blank_database, "users") == 1
    assert await table_names(blank_database) == tables
    assert await table_structure(blank_database, "users") == users_structure
    for table in BUSINESS_TABLES:
        assert table in tables
