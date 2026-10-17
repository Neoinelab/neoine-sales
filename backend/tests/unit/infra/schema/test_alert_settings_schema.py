"""head 스키마의 alert_settings(P3 AC-12, M-P3): 단일 행 체크, 기준 범위 체크, 저장자 FK, 인덱스.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다. 실패하는 INSERT는 테스트마다 하나뿐이다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.alert_rows import insert_alert_settings
from tests.support.head_rows import insert_user
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, data_type, is_nullable"
    " from information_schema.columns where table_name = 'alert_settings'"
)
FOREIGN_KEYS = (
    "select conname, confrelid::regclass::text, confdeltype::text from pg_constraint"
    " where conrelid = 'alert_settings'::regclass and contype = 'f'"
)
INDEX_NAMES = "select indexname from pg_indexes where tablename = 'alert_settings'"
COUNT = "select count(*) from alert_settings"


async def test_the_table_has_the_planned_columns_and_types(session: AsyncSession) -> None:
    columns = {r.column_name: r for r in (await session.execute(text(COLUMN_INFO))).all()}

    assert set(columns) == {"id", "stale_days", "updated_at", "updated_by_user_id"}
    assert columns["id"].data_type == "smallint"
    assert columns["stale_days"].data_type == "smallint"
    assert columns["updated_at"].data_type == "timestamp with time zone"
    assert columns["updated_by_user_id"].data_type == "uuid"


async def test_every_column_is_required_including_the_saver(session: AsyncSession) -> None:
    columns = {r.column_name: r.is_nullable for r in (await session.execute(text(COLUMN_INFO)))}

    assert columns == {
        "id": "NO",
        "stale_days": "NO",
        "updated_at": "NO",
        "updated_by_user_id": "NO",
    }


async def test_the_migration_seeds_no_row(session: AsyncSession) -> None:
    assert (await session.execute(text(COUNT))).scalar() == 0


async def test_the_single_row_with_id_one_is_accepted(session: AsyncSession) -> None:
    admin = await insert_user(session, "root")

    await insert_alert_settings(session, admin)

    assert (await session.execute(text(COUNT))).scalar() == 1


async def test_any_id_other_than_one_is_rejected(session: AsyncSession) -> None:
    admin = await insert_user(session, "root")

    with pytest.raises(IntegrityError, match="ck_alert_settings_single_row"):
        await insert_alert_settings(session, admin, id=2)


async def test_a_second_row_is_rejected(session: AsyncSession) -> None:
    admin = await insert_user(session, "root")
    await insert_alert_settings(session, admin)

    with pytest.raises(IntegrityError, match="pk_alert_settings"):
        await insert_alert_settings(session, admin)


@pytest.mark.parametrize("days", [1, 365])
async def test_stale_days_at_the_bounds_are_accepted(session: AsyncSession, days: int) -> None:
    admin = await insert_user(session, "root")

    await insert_alert_settings(session, admin, stale_days=days)

    assert (await session.execute(text("select stale_days from alert_settings"))).scalar() == days


@pytest.mark.parametrize("days", [0, 366, -1])
async def test_stale_days_outside_the_range_are_rejected(session: AsyncSession, days: int) -> None:
    admin = await insert_user(session, "root")

    with pytest.raises(IntegrityError, match="ck_alert_settings_stale_days_range"):
        await insert_alert_settings(session, admin, stale_days=days)


async def test_a_saver_that_is_not_a_user_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="fk_alert_settings_updated_by_user_id_users"):
        await insert_alert_settings(session, uuid4())


async def test_a_user_who_saved_the_settings_cannot_be_deleted(session: AsyncSession) -> None:
    admin = await insert_user(session, "root")
    await insert_alert_settings(session, admin)

    with pytest.raises(IntegrityError, match="fk_alert_settings_updated_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": admin})


async def test_the_saver_foreign_key_restricts_and_leads_an_index(session: AsyncSession) -> None:
    fks = {(r[0], r[1], r[2].strip()) for r in (await session.execute(text(FOREIGN_KEYS))).all()}
    indexes = {str(r[0]) for r in (await session.execute(text(INDEX_NAMES))).all()}

    assert fks == {("fk_alert_settings_updated_by_user_id_users", "users", "r")}
    assert "ix_alert_settings_updated_by_user_id" in indexes


async def test_the_table_passes_the_schema_integrity_rules(session: AsyncSession) -> None:
    assert await check_schema(session, only_tables={"alert_settings"}) == []
