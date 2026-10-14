"""사용자 FK 마이그레이션(AC1·11, T6): 문자열 사용자 참조 7곳을 users.id(UUID) FK로 변환한다.

LEGACY_HEAD 스키마에 시드한 뒤 head를 적용한다. 중단 경로는 test_user_fk_migration_abort,
downgrade는 test_user_fk_migration_downgrade가 검증한다.
users.login_id에는 유니크 제약/인덱스를 두지 않고 lower(login_id) 일반 인덱스를 둔다.
"""

import re
from typing import TYPE_CHECKING

import pytest
from alembic.script import ScriptDirectory

from tests.support.database import _alembic_config, apply_migrations
from tests.support.revisions import LEGACY_HEAD
from tests.support.user_fk_migration import (
    KIM,
    PARK,
    ROOT,
    LegacyData,
    columns_of,
    run_sql,
    seed_legacy,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

DATA_TABLES = ("users", "deals", "deal_actions", "deal_stage_changes", "auth_sessions")


def test_the_user_fk_revision_follows_the_legacy_head_and_is_the_single_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    heads = script.get_heads()

    assert len(heads) == 1
    assert heads != [LEGACY_HEAD]
    head = script.get_revision(heads[0])
    assert head is not None
    assert head.down_revision == LEGACY_HEAD


async def test_migration_converts_login_ids_and_names_to_user_ids(legacy_db: URL) -> None:
    await seed_legacy(legacy_db)

    await apply_migrations(legacy_db)

    owners = dict(await run_sql(legacy_db, "select code, owner_user_id from deals"))
    registrants = dict(await run_sql(legacy_db, "select code, registered_by_user_id from deals"))
    assert owners == {"D-1": PARK, "D-2": KIM}  # 이름(display_name) 일치 / login id(trim·대소문자)
    assert registrants == {"D-1": KIM, "D-2": None}  # 등록자 없던 딜은 NULL 그대로
    assert await run_sql(legacy_db, "select actor_user_id from deal_actions") == [(PARK,)]
    assert await run_sql(legacy_db, "select changed_by_user_id from deal_stage_changes") == [
        (PARK,)
    ]
    sessions = dict(await run_sql(legacy_db, "select token_hash, user_id from auth_sessions"))
    assert sessions == {"tok-0": KIM, "tok-1": PARK}
    creators = dict(await run_sql(legacy_db, "select login_id, created_by_user_id from users"))
    assert creators == {"root": ROOT, "kim": ROOT, "park": KIM}
    assert await run_sql(legacy_db, "select updated_by_user_id from directory_settings") == [
        (ROOT,)
    ]


async def test_migration_keeps_every_row(legacy_db: URL) -> None:
    await seed_legacy(legacy_db)
    before = {}
    for table in DATA_TABLES:
        before[table] = await run_sql(legacy_db, f"select count(*) from {table}")  # noqa: S608

    await apply_migrations(legacy_db)

    for table in DATA_TABLES:
        assert await run_sql(legacy_db, f"select count(*) from {table}") == before[table]  # noqa: S608
    assert [r[0] for r in await run_sql(legacy_db, "select code from deals order by code")] == [
        "D-1",
        "D-2",
    ]


async def test_login_id_matching_wins_over_display_name_matching(legacy_db: URL) -> None:
    data = LegacyData(
        users=[
            (ROOT, "root", "루트", "admin", "root"),
            (KIM, "kim", "김", "sales", "root"),
            (
                PARK,
                "park",
                "kim",
                "sales",
                "root",
            ),  # park의 표시 이름이 다른 사람의 login id와 같다
        ],
        deals=[("D-1", "kim", None)],
        actions=[],
        changes=[],
        sessions=[],
    )
    await seed_legacy(legacy_db, data)

    await apply_migrations(legacy_db)

    assert await run_sql(legacy_db, "select owner_user_id from deals") == [(KIM,)]


async def test_migration_adds_resignation_columns_with_checks_and_keeps_everyone_active(
    legacy_db: URL,
) -> None:
    await seed_legacy(legacy_db)

    await apply_migrations(legacy_db)

    assert {"deleted_at", "delete_reason"} <= await columns_of(legacy_db, "users")
    assert await run_sql(legacy_db, "select count(*) from users where deleted_at is not null") == [
        (0,)
    ]
    checks = {
        r[0]
        for r in await run_sql(
            legacy_db, "select conname from pg_constraint where conrelid = 'users'::regclass"
        )
    }
    assert {"ck_users_delete_reason_valid", "ck_users_deleted_pair"} <= checks


async def test_migration_drops_the_old_string_columns_and_adds_the_uuid_ones(
    legacy_db: URL,
) -> None:
    await apply_migrations(legacy_db)

    assert "owner" not in await columns_of(legacy_db, "deals")
    assert {"owner_user_id", "registered_by_user_id"} <= await columns_of(legacy_db, "deals")
    assert "actor" not in await columns_of(legacy_db, "deal_actions")
    assert "actor_user_id" in await columns_of(legacy_db, "deal_actions")
    assert "subject" not in await columns_of(legacy_db, "auth_sessions")
    assert "user_id" in await columns_of(legacy_db, "auth_sessions")
    changed = await columns_of(legacy_db, "deal_stage_changes")
    assert not ({"changed_by_subject", "changed_by_name"} & changed)
    assert "changed_by_user_id" in changed
    assert "created_by" not in await columns_of(legacy_db, "users")
    assert "updated_by" not in await columns_of(legacy_db, "directory_settings")


async def test_login_id_unique_index_is_replaced_by_a_plain_lower_index(legacy_db: URL) -> None:
    await apply_migrations(legacy_db)

    gone = await run_sql(
        legacy_db, "select 1 from pg_indexes where indexname = 'uq_users_login_id'"
    )
    assert gone == []
    (row,) = await run_sql(
        legacy_db, "select indexdef from pg_indexes where indexname = 'ix_users_login_id_lower'"
    )
    definition = str(row[0])
    assert "UNIQUE" not in definition
    assert "WHERE" not in definition
    assert re.search(r"lower\(\(?login_id", definition)


async def test_after_migration_the_same_login_id_can_exist_in_several_rows(legacy_db: URL) -> None:
    await apply_migrations(legacy_db)
    resigned = (
        "insert into users (id, login_id, role, created_by_user_id, created_at, updated_at,"
        " deleted_at, delete_reason) select g, :login, 'sales', g, now(), now(), now(),"
        " 'resigned' from (select gen_random_uuid() g) s"
    )
    active = (
        "insert into users (id, login_id, role, created_by_user_id, created_at, updated_at)"
        " select g, :login, 'sales', g, now(), now() from (select gen_random_uuid() g) s"
    )
    await run_sql(legacy_db, resigned, {"login": "kim"})
    await run_sql(legacy_db, resigned, {"login": "kim"})
    await run_sql(legacy_db, active, {"login": "KIM"})

    count = await run_sql(legacy_db, "select count(*) from users where lower(login_id) = 'kim'")

    assert count == [(3,)]
