"""head 스키마의 reports(Reports 3단계 5장, 마이그레이션 순수 expand).

제약은 원시 INSERT로 직접 어겨 보고 제약·인덱스 이름으로 거절되는지 확인한다(도메인 검증을
거치지 않는다). 임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다. 실패하는 INSERT는 테스트마다
하나뿐이다. 대리 키 규칙(BIGINT IDENTITY)은 `test_bigint_ids_schema.py`가 이 테이블도 점검한다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.head_rows import insert_user
from tests.support.report_rows import insert_report
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMNS = (
    "select column_name, data_type, character_maximum_length, is_nullable, column_default"
    " from information_schema.columns where table_schema = 'public' and table_name = 'reports'"
)
FOREIGN_KEYS = (
    "select conname, confrelid::regclass::text, confdeltype::text, a.attname"
    " from pg_constraint c"
    " join pg_attribute a on a.attrelid = c.conrelid and a.attnum = any(c.conkey)"
    " where c.conrelid = 'reports'::regclass and c.contype = 'f'"
)
INDEXES = (
    "select indexname, indexdef from pg_indexes"
    " where schemaname = 'public' and tablename = 'reports'"
)


async def test_reports_columns_types_and_nullability(session: AsyncSession) -> None:
    rows = (await session.execute(text(COLUMNS))).all()
    columns = {
        r.column_name: (r.data_type, r.character_maximum_length, r.is_nullable) for r in rows
    }

    assert columns == {
        "id": ("bigint", None, "NO"),
        "name": ("character varying", 100, "NO"),
        "description": ("character varying", 1000, "NO"),
        "visibility": ("character varying", 10, "NO"),
        "owner_user_id": ("bigint", None, "NO"),
        "updated_by_user_id": ("bigint", None, "NO"),
        "definition": ("jsonb", None, "NO"),
        "generated_sql": ("text", None, "NO"),
        "chart": ("jsonb", None, "YES"),
        "layout": ("jsonb", None, "YES"),
        "revision": ("integer", None, "NO"),
        "created_at": ("timestamp with time zone", None, "NO"),
        "updated_at": ("timestamp with time zone", None, "NO"),
    }


async def test_description_has_no_database_default(session: AsyncSession) -> None:
    defaults = {
        r.column_name: r.column_default for r in (await session.execute(text(COLUMNS))).all()
    }

    assert defaults["description"] is None


async def test_foreign_keys_restrict_to_users(session: AsyncSession) -> None:
    rows = (await session.execute(text(FOREIGN_KEYS))).all()

    assert {(r.conname, r.confrelid, r.confdeltype.strip(), r.attname) for r in rows} == {
        ("fk_reports_owner_user_id_users", "users", "r", "owner_user_id"),
        ("fk_reports_updated_by_user_id_users", "users", "r", "updated_by_user_id"),
    }


async def test_a_user_with_a_report_cannot_be_physically_deleted(session: AsyncSession) -> None:
    owner = await insert_user(session, "report-owner")
    await insert_report(session, owner)

    with pytest.raises(IntegrityError, match="fk_reports_owner_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": owner})


async def test_a_user_who_last_edited_a_report_cannot_be_physically_deleted(
    session: AsyncSession,
) -> None:
    owner = await insert_user(session, "report-owner")
    editor = await insert_user(session, "report-editor")
    await insert_report(session, owner, updated_by_user_id=editor)

    with pytest.raises(IntegrityError, match="fk_reports_updated_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": editor})


async def test_lower_name_index_is_unique_over_all_reports(session: AsyncSession) -> None:
    definitions = {r.indexname: r.indexdef for r in (await session.execute(text(INDEXES))).all()}

    assert "UNIQUE" in definitions["uq_reports_name_lower"]
    assert "lower" in definitions["uq_reports_name_lower"]
    assert "owner_user_id" not in definitions["uq_reports_name_lower"]
    assert "uq_reports_owner_name_lower" not in definitions
    assert "ix_reports_owner_user_id" in definitions
    assert "UNIQUE" not in definitions["ix_reports_owner_user_id"]
    assert "ix_reports_updated_by_user_id" in definitions


async def test_lower_name_unique_index_rejects_case_variant_of_the_same_owner(
    session: AsyncSession,
) -> None:
    owner = await insert_user(session, "report-owner")
    await insert_report(session, owner, name="Sales")

    with pytest.raises(IntegrityError, match="uq_reports_name_lower"):
        await insert_report(session, owner, name="sALES")


async def test_lower_name_unique_index_rejects_the_same_name_of_a_different_owner(
    session: AsyncSession,
) -> None:
    first = await insert_user(session, "report-a")
    second = await insert_user(session, "report-b")
    await insert_report(session, first, name="Sales", visibility="private")

    with pytest.raises(IntegrityError, match="uq_reports_name_lower"):
        await insert_report(session, second, name="SALES")


@pytest.mark.parametrize("visibility", ["public", "private"])
async def test_visibility_accepts_public_and_private(
    session: AsyncSession, visibility: str
) -> None:
    owner = await insert_user(session, "report-owner")

    await insert_report(session, owner, visibility=visibility)


async def test_visibility_check_rejects_other_values(session: AsyncSession) -> None:
    owner = await insert_user(session, "report-owner")

    with pytest.raises(IntegrityError, match="ck_reports_visibility_valid"):
        await insert_report(session, owner, visibility="shared")


async def test_revision_check_rejects_zero(session: AsyncSession) -> None:
    owner = await insert_user(session, "report-owner")

    with pytest.raises(IntegrityError, match="ck_reports_revision_positive"):
        await insert_report(session, owner, revision=0)


async def test_definition_check_rejects_a_json_array(session: AsyncSession) -> None:
    owner = await insert_user(session, "report-owner")

    with pytest.raises(IntegrityError, match="ck_reports_definition_object"):
        await insert_report(session, owner, definition="[]")


async def test_name_longer_than_100_is_rejected_by_the_column(session: AsyncSession) -> None:
    owner = await insert_user(session, "report-owner")

    with pytest.raises(Exception, match="too long"):
        await insert_report(session, owner, name="가" * 101)


async def test_the_schema_has_no_integrity_violations_with_reports(session: AsyncSession) -> None:
    assert await check_schema(session) == []
