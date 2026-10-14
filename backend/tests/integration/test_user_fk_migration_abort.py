"""사용자 FK 마이그레이션의 중단 경로(AC11, T7·T8·T9).

변환 불가 업무 데이터가 있으면 아무것도 바꾸지 않고 `<테이블.컬럼>=<건수> (예: ...)`가 담긴
RuntimeError로 중단한다. alembic -x 인자: `name_map=<json 경로>`(사람이 검토한 이름 -> login id),
`drop_orphan_sessions=1`(변환 불가 세션만 삭제). 데이터 삭제·NULL화·임의 사용자 생성은 하지 않는다.
"""

import json
from typing import TYPE_CHECKING

import pytest

from tests.support.database import apply_migrations
from tests.support.revisions import LEGACY_HEAD
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


async def test_migration_aborts_with_counts_for_unmappable_business_data(legacy_db: URL) -> None:
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

    with pytest.raises(RuntimeError) as aborted:
        await apply_migrations(legacy_db)

    message = str(aborted.value)
    assert "deals.owner=2" in message  # '없는사람', 동명이인
    assert "deals.owner_user_id=1" in message  # 등록자 ghost
    assert "deal_actions.actor=1" in message
    assert "deal_stage_changes.changed_by_subject=1" in message
    assert "users.created_by=1" in message
    assert "directory_settings.updated_by=1" in message
    assert "없는사람" in message  # 값 예시를 담는다
    assert "dev:admin" in message
    assert await snapshot(legacy_db) == before  # 데이터는 그대로
    assert await run_sql(legacy_db, "select version_num from alembic_version") == [(LEGACY_HEAD,)]
    assert "owner" in await columns_of(legacy_db, "deals")  # 스키마도 그대로


async def test_migration_never_deletes_nulls_or_invents_users_to_make_the_data_fit(
    legacy_db: URL,
) -> None:
    data = LegacyData(deals=[("D-1", "없는사람", None)], actions=[], changes=[])
    await seed_legacy(legacy_db, data)
    users_before = await run_sql(legacy_db, "select count(*) from users")

    with pytest.raises(RuntimeError):
        await apply_migrations(legacy_db)

    assert await run_sql(legacy_db, "select count(*) from users") == users_before
    assert await run_sql(legacy_db, "select count(*) from deals") == [(1,)]


async def test_unmappable_sessions_abort_by_default_and_are_not_deleted(legacy_db: URL) -> None:
    await seed_legacy(legacy_db, LegacyData(sessions=["kim", "dev:admin", "ghost"]))
    before = await snapshot(legacy_db)

    with pytest.raises(RuntimeError) as aborted:
        await apply_migrations(legacy_db)

    assert "auth_sessions.subject=2" in str(aborted.value)
    assert await snapshot(legacy_db) == before


async def test_drop_orphan_sessions_flag_deletes_only_the_unmappable_sessions(
    legacy_db: URL,
) -> None:
    await seed_legacy(legacy_db, LegacyData(sessions=["kim", "dev:admin", "ghost", "PARK"]))

    await apply_migrations(legacy_db, x_args=["drop_orphan_sessions=1"])

    sessions = dict(await run_sql(legacy_db, "select token_hash, user_id from auth_sessions"))
    assert sessions == {"tok-0": KIM, "tok-3": PARK}  # 변환 가능한 세션은 그대로 변환된다


async def test_drop_orphan_sessions_flag_does_not_excuse_other_unmappable_data(
    legacy_db: URL,
) -> None:
    data = LegacyData(deals=[("D-1", "없는사람", None)], actions=[], changes=[], sessions=["x"])
    await seed_legacy(legacy_db, data)
    before = await snapshot(legacy_db)

    with pytest.raises(RuntimeError) as aborted:
        await apply_migrations(legacy_db, x_args=["drop_orphan_sessions=1"])

    assert "deals.owner=1" in str(aborted.value)
    assert await snapshot(legacy_db) == before  # 세션도 삭제되지 않았다


async def test_name_map_option_resolves_names_that_do_not_match_automatically(
    legacy_db: URL, tmp_path: Path
) -> None:
    data = LegacyData(deals=[("D-1", "박사장", None)], actions=[("D-1", "박사장")], changes=[])
    await seed_legacy(legacy_db, data)
    mapping = tmp_path / "name_map.json"
    mapping.write_text(json.dumps({"박사장": "park"}, ensure_ascii=False), encoding="utf-8")

    await apply_migrations(legacy_db, x_args=[f"name_map={mapping}"])

    assert await run_sql(legacy_db, "select owner_user_id from deals") == [(PARK,)]
    assert await run_sql(legacy_db, "select actor_user_id from deal_actions") == [(PARK,)]


async def test_name_map_pointing_at_an_unknown_login_id_aborts_without_changes(
    legacy_db: URL, tmp_path: Path
) -> None:
    data = LegacyData(deals=[("D-1", "박사장", None)], actions=[], changes=[])
    await seed_legacy(legacy_db, data)
    mapping = tmp_path / "name_map.json"
    mapping.write_text(json.dumps({"박사장": "nobody"}, ensure_ascii=False), encoding="utf-8")
    before = await snapshot(legacy_db)

    with pytest.raises(RuntimeError):
        await apply_migrations(legacy_db, x_args=[f"name_map={mapping}"])

    assert await snapshot(legacy_db) == before
