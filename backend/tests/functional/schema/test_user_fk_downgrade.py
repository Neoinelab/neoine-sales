"""Feature: 운영자는 사용자 FK 리비전을 내려 문자열 컬럼을 복원하고, 퇴사자가 있으면 거부된다(AC11).

When: 운영자 명령(alembic downgrade). downgrade는 users 조인으로 문자열 컬럼을 채우고
(owner/actor = 표시 이름 또는 login id, 나머지 = login id), 퇴사 처리된 사용자가 있으면
구 스키마에서 되살아나거나 login_id가 중복되지 않도록 아무것도 바꾸지 않고 중단한다.
"""

import re
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    then_command_aborted,
    when_operator_attempts_downgrade,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.revisions import LEGACY_HEAD, USER_FK_REVISION
from tests.support.user_fk_migration import columns_of, run_sql, seed_legacy

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration


async def test_operator_downgrade_restores_string_columns_from_the_users(legacy_db: URL) -> None:
    """Scenario: 내리면 users 정보로 문자열 사용자 컬럼이 복원되고 퇴사 컬럼이 사라진다."""
    # Given
    await seed_legacy(legacy_db)
    await when_operator_upgrades(legacy_db, target=USER_FK_REVISION)
    # When
    await when_operator_downgrades(legacy_db, target=LEGACY_HEAD)
    # Then
    assert {"owner", "owner_user_id"} <= await columns_of(legacy_db, "deals")
    assert "registered_by_user_id" not in await columns_of(legacy_db, "deals")
    deals = await run_sql(legacy_db, "select code, owner, owner_user_id from deals order by code")
    assert deals == [("D-1", "박영업", "kim"), ("D-2", "김영업", None)]  # 이름 / 등록자 login id
    assert await run_sql(legacy_db, "select actor from deal_actions") == [("박영업",)]
    changed = await run_sql(
        legacy_db, "select changed_by_subject, changed_by_name from deal_stage_changes"
    )
    assert changed == [("park", "박영업")]
    sessions = dict(await run_sql(legacy_db, "select token_hash, subject from auth_sessions"))
    assert sessions == {"tok-0": "kim", "tok-1": "park"}
    creators = dict(await run_sql(legacy_db, "select login_id, created_by from users"))
    assert creators == {"root": "root", "kim": "root", "park": "kim"}
    assert {"deleted_at", "delete_reason"}.isdisjoint(await columns_of(legacy_db, "users"))
    unique = await run_sql(
        legacy_db, "select indexdef from pg_indexes where indexname = 'uq_users_login_id'"
    )
    assert "UNIQUE" in str(unique[0][0])  # 퇴사자가 없으면 전체 유니크로 되돌린다


async def test_operator_upgrade_after_downgrade_links_the_same_user_rows_again(
    legacy_db: URL,
) -> None:
    """Scenario: 내렸다가 다시 올리면 같은 사용자 행으로 다시 연결된다."""
    # Given
    await seed_legacy(legacy_db)
    await when_operator_upgrades(legacy_db, target=USER_FK_REVISION)
    owners_before = await run_sql(legacy_db, "select code, owner_user_id from deals order by code")
    await when_operator_downgrades(legacy_db, target=LEGACY_HEAD)
    # When
    await when_operator_upgrades(legacy_db, target=USER_FK_REVISION)
    # Then
    again = await run_sql(legacy_db, "select code, owner_user_id from deals order by code")
    assert again == owners_before


async def test_operator_downgrade_is_refused_when_resigned_users_exist_and_changes_nothing(
    legacy_db: URL,
) -> None:
    """Scenario: 퇴사 처리된 사용자가 있으면 내리기를 거부하고 아무것도 바꾸지 않는다."""
    # Given
    await seed_legacy(legacy_db)
    await when_operator_upgrades(legacy_db, target=USER_FK_REVISION)
    await run_sql(
        legacy_db,
        "update users set deleted_at = now(), delete_reason = 'resigned' where login_id = 'park'",
    )
    state = "select id, deleted_at is null from users order by login_id"
    before = await run_sql(legacy_db, state)
    # When
    outcome = await when_operator_attempts_downgrade(legacy_db, target=LEGACY_HEAD)
    # Then
    then_command_aborted(outcome)
    assert outcome.error is not None
    assert re.search("퇴사|resigned", str(outcome.error))
    assert await run_sql(legacy_db, state) == before
    assert "deleted_at" in await columns_of(legacy_db, "users")
    assert "actor_user_id" in await columns_of(legacy_db, "deal_actions")
