"""head 스키마의 storage_settings(P2b AC-17, M-P2b): 단일 행 체크, 경로 길이, 저장자 FK, 인덱스.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다. 실패하는 INSERT는 테스트마다 하나뿐이다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.support.attachment_rows import insert_storage_settings
from tests.support.head_rows import insert_user
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMN_INFO = (
    "select column_name, data_type, character_maximum_length, is_nullable"
    " from information_schema.columns where table_name = 'storage_settings'"
)
FOREIGN_KEYS = (
    "select conname, confrelid::regclass::text, confdeltype::text from pg_constraint"
    " where conrelid = 'storage_settings'::regclass and contype = 'f'"
)
INDEX_NAMES = "select indexname from pg_indexes where tablename = 'storage_settings'"
COUNT = "select count(*) from storage_settings"


async def test_the_table_has_the_planned_columns_and_types(session: AsyncSession) -> None:
    columns = {r.column_name: r for r in (await session.execute(text(COLUMN_INFO))).all()}

    assert set(columns) == {"id", "path", "updated_at", "updated_by_user_id"}
    assert columns["id"].data_type == "smallint"
    assert (columns["path"].data_type, columns["path"].character_maximum_length) == (
        "character varying",
        1024,
    )
    assert columns["updated_at"].data_type == "timestamp with time zone"
    assert columns["updated_by_user_id"].data_type == "uuid"


async def test_a_path_and_a_time_are_required_but_a_saver_is_not(session: AsyncSession) -> None:
    columns = {r.column_name: r.is_nullable for r in (await session.execute(text(COLUMN_INFO)))}

    assert columns == {
        "id": "NO",
        "path": "NO",
        "updated_at": "NO",
        "updated_by_user_id": "YES",
    }


async def test_the_single_row_with_id_one_is_accepted(session: AsyncSession) -> None:
    await insert_storage_settings(session)

    assert (await session.execute(text(COUNT))).scalar() == 1


async def test_any_id_other_than_one_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_storage_settings_single_row"):
        await insert_storage_settings(session, id=2)


async def test_a_second_row_is_rejected(session: AsyncSession) -> None:
    await insert_storage_settings(session)

    with pytest.raises(IntegrityError, match="pk_storage_settings"):
        await insert_storage_settings(session)


async def test_a_path_of_1024_characters_is_accepted(session: AsyncSession) -> None:
    await insert_storage_settings(session, path="/" + "a" * 1023)

    assert (await session.execute(text("select length(path) from storage_settings"))).scalar() == (
        1024
    )


async def test_a_path_over_1024_characters_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(DBAPIError):
        await insert_storage_settings(session, path="/" + "a" * 1024)


async def test_a_saver_that_is_not_a_user_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="fk_storage_settings_updated_by_user_id_users"):
        await insert_storage_settings(session, updated_by=uuid4())


async def test_a_user_who_saved_the_settings_cannot_be_deleted(session: AsyncSession) -> None:
    admin = await insert_user(session, "root")
    await insert_storage_settings(session, updated_by=admin)

    with pytest.raises(IntegrityError, match="fk_storage_settings_updated_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": admin})


async def test_the_saver_foreign_key_restricts_and_leads_an_index(session: AsyncSession) -> None:
    fks = {(r[0], r[1], r[2].strip()) for r in (await session.execute(text(FOREIGN_KEYS))).all()}
    indexes = {str(r[0]) for r in (await session.execute(text(INDEX_NAMES))).all()}

    assert fks == {("fk_storage_settings_updated_by_user_id_users", "users", "r")}
    assert "ix_storage_settings_updated_by_user_id" in indexes


async def test_the_table_passes_the_schema_integrity_rules(session: AsyncSession) -> None:
    assert await check_schema(session, only_tables={"storage_settings"}) == []
