"""BIGINT id 리비전 마이그레이션 step: 이전 리비전에 업무 데이터를 심고, 시드와 초기화를 확인한다.

이전 리비전(`e8c2b4f6a1d9`)은 UUID 스키마라 Given 행은 `tests.support.uuid_era` 도우미로 넣는다.
시드의 기대값은 `tests/fakes/catalog_seed.py`·`tests/factories_action_type.py`(= 마이그레이션 시드와
같아야 하는 정본 표)에서 가져온다.
"""

from typing import TYPE_CHECKING, Final

from sqlalchemy import text

from tests.factories_action_type import DEFAULT_ACTION_TYPE_NAMES
from tests.fakes.catalog_seed import (
    DEFAULT_FORECASTS,
    DEFAULT_LABELS,
    DEFAULT_STATUSES,
)
from tests.functional.steps.schema import given_rows, given_schema_at
from tests.support.revisions import deals_users_required_revision
from tests.support.user_fk_migration import run_sql
from tests.support.uuid_era.alert_rows import insert_alert_settings
from tests.support.uuid_era.attachment_rows import insert_attachment, insert_storage_settings
from tests.support.uuid_era.head_rows import (
    insert_action,
    insert_bant,
    insert_contact,
    insert_deal,
    insert_history,
    insert_partner_link,
    insert_user,
)
from tests.support.uuid_era.vendor_rows import insert_solution, insert_vendor

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

# 마이그레이션이 비우는 업무 테이블(시드 테이블 codes·bant_labels·action_types는 시드로 다시 채운다)
BUSINESS_TABLES: Final = (
    "users",
    "auth_sessions",
    "login_failures",
    "directory_settings",
    "storage_settings",
    "alert_settings",
    "contacts",
    "vendors",
    "solutions",
    "deals",
    "deal_partners",
    "deal_bant_labels",
    "deal_history",
    "deal_actions",
    "deal_attachments",
)
SEED_COUNTS: Final = {"codes": 13, "bant_labels": 23, "action_types": 8}
UUID_COLUMNS: Final = (
    "select table_name, column_name from information_schema.columns"
    " where table_schema = 'public' and (data_type = 'uuid' or udt_name = 'uuid')"
    " order by table_name, column_name"
)
INSERT_SESSION: Final = (
    "insert into auth_sessions (id, token_hash, user_id, email, name, role, created_at,"
    " expires_at) values (gen_random_uuid(), :token, :user_id, null, 'n', 'sales', now(),"
    " now() + interval '1 hour')"
)
INSERT_FAILURE: Final = (
    "insert into login_failures (key, failures, window_started_at) values (:key, 1, now())"
)
INSERT_DIRECTORY: Final = (
    "insert into directory_settings (id, revision, server_urls, use_starttls, bind_template,"
    " base_dn, user_filter, display_name_attribute, email_attribute, connect_timeout_seconds,"
    " receive_timeout_seconds, updated_at, updated_by_user_id) values (1, 1,"
    " cast('[\"ldaps://dc1.corp.test\"]' as jsonb), false, 'cn={login_id}', 'dc=corp',"
    " '(cn={login_id})', 'displayName', 'mail', 5, 10, now(), :user_id)"
)
CODES_SEED: Final = (
    "select kind, key, name, sort_order, outcome, probability_hint from codes"
    " order by kind, sort_order"
)
LABELS_SEED: Final = (
    "select category, name, default_order, is_default, created_by_user_id from bant_labels"
    " order by category, default_order"
)
TYPES_SEED: Final = (
    "select name, default_order, is_default, created_by_user_id from action_types"
    " order by default_order"
)


async def _business_rows(session: AsyncSession) -> None:
    """운영 중 쌓인 데이터: 모든 업무 테이블에 최소 한 행(UUID 스키마)."""
    admin = await insert_user(session, "root")
    owner = await insert_user(session, "kim")
    customer = await insert_contact(session)
    partner = await insert_contact(session, kind="partner", company="한빛파트너스")
    code = await insert_deal(session, customer, owner)
    label = (
        await session.execute(text("select id from bant_labels where category = 'need' limit 1"))
    ).scalar_one()
    await insert_partner_link(session, code, partner)
    await insert_bant(session, code, "need", label)
    await insert_history(session, code, owner)
    await insert_action(session, code, owner)
    await insert_attachment(session, code, owner)
    await insert_storage_settings(session, path="/data/neoine-sales/files", updated_by=admin)
    await insert_alert_settings(session, admin)
    vendor = await insert_vendor(session, "SAP")
    await insert_solution(session, vendor, "S/4HANA")
    await session.execute(text(INSERT_SESSION), {"token": "t" * 64, "user_id": owner})
    await session.execute(text(INSERT_FAILURE), {"key": "k" * 64})
    await session.execute(text(INSERT_DIRECTORY), {"user_id": admin})


async def given_business_data_before_the_bigint_revision(url: URL) -> None:
    """`e8c2b4f6a1d9`까지 올린 DB에 사용자·연락처·Deal·Action·첨부·설정 등 업무 데이터가 있다."""
    await given_schema_at(url, deals_users_required_revision())
    await given_rows(url, _business_rows)
    for table in BUSINESS_TABLES:
        assert await row_count(url, table) > 0, f"Given 실패: {table}에 행이 없다"


async def given_storage_path_before_the_bigint_revision(url: URL, path: str) -> None:
    """`e8c2b4f6a1d9`까지 올린 DB의 storage_settings에 저장 위치 path가 있다(다른 데이터는 없다)."""
    await given_schema_at(url, deals_users_required_revision())

    async def seed(session: AsyncSession) -> None:
        await insert_storage_settings(session, path=path)

    await given_rows(url, seed)


async def row_count(url: URL, table: str) -> int:
    rows = await run_sql(url, f"select count(*) from {table}")  # noqa: S608 - 상수 테이블 이름
    return int(rows[0][0])


async def uuid_columns(url: URL) -> list[tuple[str, str]]:
    return [(str(r[0]), str(r[1])) for r in await run_sql(url, UUID_COLUMNS)]


async def then_business_tables_are_empty(url: URL) -> None:
    counts = {table: await row_count(url, table) for table in BUSINESS_TABLES}
    assert counts == dict.fromkeys(BUSINESS_TABLES, 0)


async def then_seed_rows_are_present(url: URL) -> None:
    """기본 코드 13·BANT Label 23·Action 유형 8이 정본 표와 같은 값으로 있고 id는 1 이상이다."""
    counts = {table: await row_count(url, table) for table in SEED_COUNTS}
    assert counts == SEED_COUNTS
    for table in SEED_COUNTS:
        smallest = (await run_sql(url, f"select min(id) from {table}"))[0][0]  # noqa: S608
        assert isinstance(smallest, int)
        assert smallest >= 1, table
    await _then_codes_match(url)
    await _then_labels_match(url)
    await _then_types_match(url)


async def _then_codes_match(url: URL) -> None:
    expected = sorted(
        [
            ("status", key, name, order, "open", None)
            for order, (key, name) in enumerate(DEFAULT_STATUSES, 1)
        ]
        + [
            ("forecast", key, name, order, outcome, hint)
            for order, (key, name, outcome, hint) in enumerate(DEFAULT_FORECASTS, 1)
        ],
        key=lambda row: (row[0], row[3]),
    )
    assert [tuple(r) for r in await run_sql(url, CODES_SEED)] == expected


async def _then_labels_match(url: URL) -> None:
    expected = [
        (category, name, order, True, None)
        for category, names in sorted(DEFAULT_LABELS.items())
        for order, name in enumerate(names, 1)
    ]
    assert [tuple(r) for r in await run_sql(url, LABELS_SEED)] == expected


async def _then_types_match(url: URL) -> None:
    expected = [
        (name, order, True, None) for order, name in enumerate(DEFAULT_ACTION_TYPE_NAMES, 1)
    ]
    assert [tuple(r) for r in await run_sql(url, TYPES_SEED)] == expected
