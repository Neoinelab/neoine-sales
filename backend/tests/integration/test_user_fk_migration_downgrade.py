"""사용자 FK 마이그레이션의 downgrade와 왕복(AC11, T10).

downgrade는 users 조인으로 문자열 컬럼을 채우고(owner/actor = 표시 이름 또는 login id, 나머지 =
login id), 퇴사 처리된 사용자가 있으면 구 스키마에서 되살아나거나 login_id가 중복되지 않도록
아무것도 바꾸지 않고 중단한다.
"""

import re
from typing import TYPE_CHECKING

import pytest

from tests.support.database import apply_migrations
from tests.support.revisions import LEGACY_HEAD
from tests.support.user_fk_migration import columns_of, run_sql, seed_legacy

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration


async def test_downgrade_restores_string_columns_from_the_users_and_upgrade_again_works(
    legacy_db: URL,
) -> None:
    await seed_legacy(legacy_db)
    await apply_migrations(legacy_db)
    owners_before = await run_sql(legacy_db, "select code, owner_user_id from deals order by code")

    await apply_migrations(legacy_db, direction="down", target=LEGACY_HEAD)

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

    await apply_migrations(legacy_db)

    again = await run_sql(legacy_db, "select code, owner_user_id from deals order by code")
    assert again == owners_before  # 같은 사용자 행으로 다시 연결된다


async def test_downgrade_refuses_when_resigned_users_exist_and_changes_nothing(
    legacy_db: URL,
) -> None:
    await seed_legacy(legacy_db)
    await apply_migrations(legacy_db)
    await run_sql(
        legacy_db,
        "update users set deleted_at = now(), delete_reason = 'resigned' where login_id = 'park'",
    )
    state = "select id, deleted_at is null from users order by login_id"
    before = await run_sql(legacy_db, state)

    with pytest.raises(RuntimeError) as refused:
        await apply_migrations(legacy_db, direction="down", target=LEGACY_HEAD)

    assert re.search("퇴사|resigned", str(refused.value))
    assert await run_sql(legacy_db, state) == before
    assert "deleted_at" in await columns_of(legacy_db, "users")
    assert "actor_user_id" in await columns_of(legacy_db, "deal_actions")
