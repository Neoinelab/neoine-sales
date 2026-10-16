"""deleted_at 제거 리비전(DROP_DELETED_AT_REVISION) 직후 스키마의 카탈로그 단언(AC1~AC4).

이후 사용자 FK 리비전이 users에만 deleted_at을 되살리므로 '어떤 테이블에도 deleted_at이 없다'는
단언은 그 리비전에 고정한다(현재 head의 규칙은 test_head_schema_integrity가 검증한다).
올리기·중단·왕복 흐름은 tests/functional/schema/test_drop_deleted_at.py.
"""

from typing import TYPE_CHECKING

import pytest

from tests.support.drop_deleted_at import TABLES, deleted_at_tables, run_sql, user_index_names
from tests.support.revisions import DROP_DELETED_AT_REVISION as DROP_REVISION

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration


@pytest.fixture
def test_database_url(database_at: Callable[[str], URL]) -> URL:
    return database_at(DROP_REVISION)


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
