"""모든 테이블의 deleted_at 제거 마이그레이션(AC1~AC4): 단일 리비전, 사전 점검, 인덱스 교체, 왕복.

`e3a9c41b7d52` 스키마에 행을 넣어 두고 head를 적용한다. deleted_at 값이 있는 행이 하나라도 있으면
데이터를 지우지 않고 `<테이블>=<건수>`가 담긴 RuntimeError로 중단해야 하며 스키마는 그대로여야 한다.
"""

from typing import TYPE_CHECKING

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.support.database import (
    _alembic_config,
    apply_migrations,
    resolve_admin_url,
    temporary_database,
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
from tests.support.skips import skip_or_fail

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration


def _require_admin_url() -> URL:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 마이그레이션 테스트를 건너뜁니다")
    return admin_url


@pytest.fixture
def test_database_url(database_at: Callable[[str], URL]) -> URL:
    """이 파일의 head 스키마 단언은 deleted_at 제거 리비전 직후 스키마에서 검증한다.

    이후 사용자 FK 리비전이 users에만 deleted_at을 되살리므로 '어떤 테이블에도 deleted_at이 없다'는
    단언은 그 리비전에 고정해야 한다(현재 head의 규칙은 test_schema_integrity가 검증한다).
    """
    return database_at(DROP_REVISION)


def test_the_drop_revision_follows_the_previous_head_and_stays_in_the_single_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    heads = script.get_heads()

    assert len(heads) == 1
    drop = script.get_revision(DROP_REVISION)
    assert drop is not None
    assert drop.down_revision == PREVIOUS_HEAD
    history = {r.revision for r in script.iterate_revisions(heads[0], "base")}
    assert DROP_REVISION in history


async def test_head_schema_has_no_deleted_at_column_on_any_table(test_database_url: URL) -> None:
    assert await deleted_at_tables(test_database_url) == set()
    for table in TABLES:
        rows = await run_sql(
            test_database_url,
            f"select column_name from information_schema.columns where table_name = '{table}'",  # noqa: S608
        )
        assert {"id", "created_at", "updated_at"} <= {str(r[0]) for r in rows}, table


async def test_fks_and_unique_deal_code_survive_the_column_drop(test_database_url: URL) -> None:
    rows = await run_sql(
        test_database_url,
        "select conname, contype::text, confdeltype::text from pg_constraint where conname in"
        " ('uq_deals_code', 'fk_deals_customer_id_customers', 'fk_deals_partner_id_partners',"
        " 'fk_deal_actions_deal_id_deals', 'fk_deal_stage_changes_deal_id_deals')",
    )

    found = {str(r[0]): (str(r[1]), str(r[2]).strip()) for r in rows}

    assert found == {
        "uq_deals_code": ("u", ""),  # 일반 UNIQUE 제약
        "fk_deals_customer_id_customers": ("f", "r"),  # RESTRICT
        "fk_deals_partner_id_partners": ("f", "r"),
        "fk_deal_actions_deal_id_deals": ("f", "r"),
        "fk_deal_stage_changes_deal_id_deals": ("f", "r"),
    }


async def test_users_login_id_unique_index_is_plain_and_case_insensitive(
    test_database_url: URL,
) -> None:
    rows = await run_sql(
        test_database_url, "select indexdef from pg_indexes where indexname = 'uq_users_login_id'"
    )

    assert len(rows) == 1
    definition = str(rows[0][0])
    assert "UNIQUE" in definition
    assert "lower(" in definition
    assert "WHERE" not in definition
    assert await user_index_names(test_database_url) == {"uq_users_login_id"}


@pytest.mark.parametrize("table", TABLES)
async def test_upgrade_aborts_and_keeps_everything_when_a_row_is_soft_deleted(table: str) -> None:
    admin_url = _require_admin_url()
    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=PREVIOUS_HEAD)
        await seed(url, soft_deleted=[table])
        before = await row_counts(url)

        with pytest.raises(RuntimeError) as aborted:
            await apply_migrations(url, target=DROP_REVISION)

        assert f"{table}=1" in str(aborted.value)
        assert await deleted_at_tables(url) == set(TABLES)  # 컬럼 하나도 지워지지 않았다
        assert await row_counts(url) == before  # 행도 그대로
        assert await user_index_names(url) == {"uq_users_login_id_active"}
        version = await run_sql(url, "select version_num from alembic_version")
        assert version == [(PREVIOUS_HEAD,)]


async def test_upgrade_reports_every_table_with_soft_deleted_rows() -> None:
    admin_url = _require_admin_url()
    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=PREVIOUS_HEAD)
        await seed(url, soft_deleted=["customers", "users"])

        with pytest.raises(RuntimeError) as aborted:
            await apply_migrations(url, target=DROP_REVISION)

        message = str(aborted.value)
        assert "customers=1" in message
        assert "users=1" in message
        assert "partners=" not in message
        assert await deleted_at_tables(url) == set(TABLES)


async def test_upgrade_drops_columns_and_keeps_all_rows_when_none_is_soft_deleted() -> None:
    admin_url = _require_admin_url()
    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=PREVIOUS_HEAD)
        await seed(url)
        before = await row_counts(url)

        await apply_migrations(url, target=DROP_REVISION)

        assert await deleted_at_tables(url) == set()
        assert await row_counts(url) == before
        assert await run_sql(url, "select code from deals") == [(CODE,)]
        assert await user_index_names(url) == {"uq_users_login_id"}
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                with pytest.raises(IntegrityError, match="uq_users_login_id"):
                    await AsyncSession(bind=connection).execute(
                        text(
                            "insert into users (id, login_id, role, created_by, created_at,"
                            " updated_at) values (gen_random_uuid(), 'KIM', 'user', 'a',"
                            " now(), now())"
                        )
                    )
        finally:
            await engine.dispose()


async def test_downgrade_restores_nullable_deleted_at_and_partial_unique_index_losslessly() -> None:
    admin_url = _require_admin_url()
    async with temporary_database(admin_url) as url:
        await apply_migrations(url, target=PREVIOUS_HEAD)
        await seed(url)
        await apply_migrations(url, target=DROP_REVISION)
        before = await row_counts(url)

        await apply_migrations(url, direction="down", target=PREVIOUS_HEAD)

        assert await deleted_at_tables(url) == set(TABLES)
        nullable = await run_sql(
            url,
            "select count(*) from information_schema.columns where column_name = 'deleted_at'"
            " and is_nullable = 'YES' and table_name in"
            " ('customers','partners','deals','deal_actions','users')",
        )
        assert nullable == [(5,)]
        assert await row_counts(url) == before
        assert await run_sql(url, "select count(*) from users where deleted_at is not null") == [
            (0,)
        ]
        assert await user_index_names(url) == {"uq_users_login_id_active"}
        definition = await run_sql(
            url, "select indexdef from pg_indexes where indexname = 'uq_users_login_id_active'"
        )
        assert "deleted_at IS NULL" in str(definition[0][0])

        await apply_migrations(url, target=DROP_REVISION)  # 다시 올려도 정상이다

        assert await deleted_at_tables(url) == set()
        assert await row_counts(url) == before
