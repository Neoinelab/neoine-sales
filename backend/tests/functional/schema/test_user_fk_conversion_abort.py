"""Feature: 변환 불가 업무 데이터가 있으면 운영자의 upgrade는 아무것도 바꾸지 않고 중단된다(AC11).

When: 운영자 명령(alembic upgrade head [-x ...]).
중단 사유는 `<테이블.컬럼>=<건수> (예: ...)`가 담긴 RuntimeError다. alembic -x 인자:
`name_map=<json 경로>`(사람이 검토한 이름 -> login id), `drop_orphan_sessions=1`(변환 불가 세션만
삭제). 데이터 삭제·NULL화·임의 사용자 생성은 하지 않는다.
"""

import json
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    then_command_aborted,
    then_schema_is_at,
    when_operator_attempts_upgrade,
    when_operator_upgrades,
)
from tests.support.revisions import LEGACY_HEAD, USER_FK_REVISION
from tests.support.user_fk_migration import (
    KIM,
    PARK,
    ROOT,
    LegacyData,
    columns_of,
    run_sql,
    seed_legacy,
    snapshot,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration


async def test_upgrade_aborts_with_counts_for_unmappable_business_data(legacy_db: URL) -> None:
    """Scenario: 변환 불가 업무 데이터가 있으면 컬럼별 건수와 값 예시를 알리고 중단한다."""
    # Given
    data = LegacyData(
        users=[
            (ROOT, "root", "루트", "admin", "root"),
            (KIM, "kim", "동명", "sales", "dev:admin"),  # created_by가 users에 없다
            (PARK, "park", "동명", "sales", "root"),  # 표시 이름이 같은 사람이 둘
        ],
        deals=[("D-1", "없는사람", None), ("D-2", "동명", "ghost")],
        actions=[("D-1", "동명")],
        changes=[("D-1", "dev:admin", "개발")],
        sessions=[],
        settings_updated_by="ghost",
    )
    await seed_legacy(legacy_db, data)
    before = await snapshot(legacy_db)
    # When
    outcome = await when_operator_attempts_upgrade(legacy_db, target=USER_FK_REVISION)
    # Then
    then_command_aborted(
        outcome,
        "deals.owner=2",  # '없는사람', 동명이인
        "deals.owner_user_id=1",  # 등록자 ghost
        "deal_actions.actor=1",
        "deal_stage_changes.changed_by_subject=1",
        "users.created_by=1",
        "directory_settings.updated_by=1",
        "없는사람",  # 값 예시를 담는다
        "dev:admin",
    )
    assert await snapshot(legacy_db) == before  # 데이터는 그대로
    await then_schema_is_at(legacy_db, LEGACY_HEAD)
    assert "owner" in await columns_of(legacy_db, "deals")  # 스키마도 그대로


async def test_upgrade_abort_never_deletes_nulls_or_invents_users(legacy_db: URL) -> None:
    """Scenario: 중단할 때 데이터를 지우거나 NULL로 만들거나 임의 사용자를 만들지 않는다."""
    # Given
    data = LegacyData(deals=[("D-1", "없는사람", None)], actions=[], changes=[])
    await seed_legacy(legacy_db, data)
    users_before = await run_sql(legacy_db, "select count(*) from users")
    # When
    outcome = await when_operator_attempts_upgrade(legacy_db, target=USER_FK_REVISION)
    # Then
    then_command_aborted(outcome)
    assert await run_sql(legacy_db, "select count(*) from users") == users_before
    assert await run_sql(legacy_db, "select count(*) from deals") == [(1,)]


async def test_upgrade_aborts_on_unmappable_sessions_by_default_and_keeps_them(
    legacy_db: URL,
) -> None:
    """Scenario: 변환 불가 세션이 있으면 기본적으로 중단하고 세션을 지우지 않는다."""
    # Given
    await seed_legacy(legacy_db, LegacyData(sessions=["kim", "dev:admin", "ghost"]))
    before = await snapshot(legacy_db)
    # When
    outcome = await when_operator_attempts_upgrade(legacy_db, target=USER_FK_REVISION)
    # Then
    then_command_aborted(outcome, "auth_sessions.subject=2")
    assert await snapshot(legacy_db) == before


async def test_drop_orphan_sessions_flag_deletes_only_the_unmappable_sessions(
    legacy_db: URL,
) -> None:
    """Scenario: drop_orphan_sessions=1이면 변환 불가 세션만 지우고 나머지는 변환한다."""
    # Given
    await seed_legacy(legacy_db, LegacyData(sessions=["kim", "dev:admin", "ghost", "PARK"]))
    # When
    await when_operator_upgrades(
        legacy_db, target=USER_FK_REVISION, x_args=["drop_orphan_sessions=1"]
    )
    # Then
    sessions = dict(await run_sql(legacy_db, "select token_hash, user_id from auth_sessions"))
    assert sessions == {"tok-0": KIM, "tok-3": PARK}  # 변환 가능한 세션은 그대로 변환된다


async def test_drop_orphan_sessions_flag_does_not_excuse_other_unmappable_data(
    legacy_db: URL,
) -> None:
    """Scenario: drop_orphan_sessions=1이어도 다른 변환 불가 데이터가 있으면 중단한다."""
    # Given
    data = LegacyData(deals=[("D-1", "없는사람", None)], actions=[], changes=[], sessions=["x"])
    await seed_legacy(legacy_db, data)
    before = await snapshot(legacy_db)
    # When
    outcome = await when_operator_attempts_upgrade(
        legacy_db, target=USER_FK_REVISION, x_args=["drop_orphan_sessions=1"]
    )
    # Then
    then_command_aborted(outcome, "deals.owner=1")
    assert await snapshot(legacy_db) == before  # 세션도 삭제되지 않았다


async def test_name_map_option_resolves_names_that_do_not_match_automatically(
    legacy_db: URL, tmp_path: Path
) -> None:
    """Scenario: name_map으로 사람이 검토한 이름을 로그인 아이디에 연결하면 변환된다."""
    # Given
    data = LegacyData(deals=[("D-1", "박사장", None)], actions=[("D-1", "박사장")], changes=[])
    await seed_legacy(legacy_db, data)
    mapping = tmp_path / "name_map.json"
    mapping.write_text(json.dumps({"박사장": "park"}, ensure_ascii=False), encoding="utf-8")
    # When
    await when_operator_upgrades(legacy_db, target=USER_FK_REVISION, x_args=[f"name_map={mapping}"])
    # Then
    assert await run_sql(legacy_db, "select owner_user_id from deals") == [(PARK,)]
    assert await run_sql(legacy_db, "select actor_user_id from deal_actions") == [(PARK,)]


async def test_name_map_pointing_at_an_unknown_login_id_aborts_without_changes(
    legacy_db: URL, tmp_path: Path
) -> None:
    """Scenario: name_map이 없는 로그인 아이디를 가리키면 아무것도 바꾸지 않고 중단한다."""
    # Given
    data = LegacyData(deals=[("D-1", "박사장", None)], actions=[], changes=[])
    await seed_legacy(legacy_db, data)
    mapping = tmp_path / "name_map.json"
    mapping.write_text(json.dumps({"박사장": "nobody"}, ensure_ascii=False), encoding="utf-8")
    before = await snapshot(legacy_db)
    # When
    outcome = await when_operator_attempts_upgrade(
        legacy_db, target=USER_FK_REVISION, x_args=[f"name_map={mapping}"]
    )
    # Then
    then_command_aborted(outcome)
    assert await snapshot(legacy_db) == before
