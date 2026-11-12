"""head 스키마의 storage_settings: 단일 행 체크, 경로 길이, 저장자 FK, 인덱스.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다. 실패하는 INSERT는 테스트마다 하나뿐이다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.support.attachment_rows import insert_storage_settings
from tests.support.head_rows import insert_user
from tests.support.ids import new_id
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
    """storage_settings 테이블은 정해진 열과 자료형을 가진다."""
    # when: 열 정보를 조회한다 (전제: head 스키마의 DB 세션)
    columns = {r.column_name: r for r in (await session.execute(text(COLUMN_INFO))).all()}

    # then: 열 이름과 자료형·길이가 맞다
    assert set(columns) == {"id", "path", "updated_at", "updated_by_user_id"}
    assert columns["id"].data_type == "smallint"
    assert (columns["path"].data_type, columns["path"].character_maximum_length) == (
        "character varying",
        1024,
    )
    assert columns["updated_at"].data_type == "timestamp with time zone"
    assert columns["updated_by_user_id"].data_type == "bigint"


async def test_a_path_and_a_time_are_required_but_a_saver_is_not(session: AsyncSession) -> None:
    """경로와 시각은 필수이고 저장자는 비워 둘 수 있다."""
    # when: 열의 NULL 허용 여부를 조회한다 (전제: head 스키마의 DB 세션)
    columns = {r.column_name: r.is_nullable for r in (await session.execute(text(COLUMN_INFO)))}

    # then: 저장자 열만 NULL을 허용한다
    assert columns == {
        "id": "NO",
        "path": "NO",
        "updated_at": "NO",
        "updated_by_user_id": "YES",
    }


async def test_the_single_row_with_id_one_is_accepted(session: AsyncSession) -> None:
    """id가 1인 단일 행은 허용한다."""
    # when: id 1로 설정을 넣는다 (전제: head 스키마의 DB 세션)
    await insert_storage_settings(session)

    # then: 행이 한 개 있다
    assert (await session.execute(text(COUNT))).scalar() == 1


async def test_any_id_other_than_one_is_rejected(session: AsyncSession) -> None:
    """id가 1이 아니면 단일 행 CHECK가 거부한다."""
    # when·then: id 2로 넣으면 단일 행 CHECK 위반이 난다 (전제: head 스키마의 DB 세션)
    with pytest.raises(IntegrityError, match="ck_storage_settings_single_row"):
        await insert_storage_settings(session, id=2)


async def test_a_second_row_is_rejected(session: AsyncSession) -> None:
    """두 번째 행은 기본 키 제약이 거부한다."""
    # given: 설정 한 행
    await insert_storage_settings(session)

    # when·then: 한 행을 더 넣으면 기본 키 위반이 난다
    with pytest.raises(IntegrityError, match="pk_storage_settings"):
        await insert_storage_settings(session)


async def test_a_path_of_1024_characters_is_accepted(session: AsyncSession) -> None:
    """1024자 경로는 허용한다."""
    # when: 1024자 경로로 넣는다 (전제: head 스키마의 DB 세션)
    await insert_storage_settings(session, path="/" + "a" * 1023)

    # then: 저장된 경로 길이가 1024다
    assert (await session.execute(text("select length(path) from storage_settings"))).scalar() == (
        1024
    )


async def test_a_path_over_1024_characters_is_rejected(session: AsyncSession) -> None:
    """1024자를 넘는 경로는 거부한다."""
    # when·then: 1025자 경로로 넣으면 DB 오류가 난다 (전제: head 스키마의 DB 세션)
    with pytest.raises(DBAPIError):
        await insert_storage_settings(session, path="/" + "a" * 1024)


async def test_a_saver_that_is_not_a_user_is_rejected(session: AsyncSession) -> None:
    """사용자가 아닌 저장자는 FK 제약이 거부한다."""
    # when·then: 없는 사용자 id로 넣으면 FK 위반이 난다 (전제: head 스키마의 DB 세션)
    with pytest.raises(IntegrityError, match="fk_storage_settings_updated_by_user_id_users"):
        await insert_storage_settings(session, updated_by=new_id())


async def test_a_user_who_saved_the_settings_cannot_be_deleted(session: AsyncSession) -> None:
    """설정을 저장한 사용자는 삭제할 수 없다."""
    # given: 설정을 저장한 사용자
    admin = await insert_user(session, "root")
    await insert_storage_settings(session, updated_by=admin)

    # when·then: 그 사용자를 삭제하면 FK 위반이 난다
    with pytest.raises(IntegrityError, match="fk_storage_settings_updated_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": admin})


async def test_the_saver_foreign_key_restricts_and_leads_an_index(session: AsyncSession) -> None:
    """저장자 FK는 RESTRICT이고 인덱스가 걸려 있다."""
    # when: 외래 키와 인덱스를 조회한다 (전제: head 스키마의 DB 세션)
    fks = {(r[0], r[1], r[2].strip()) for r in (await session.execute(text(FOREIGN_KEYS))).all()}
    indexes = {str(r[0]) for r in (await session.execute(text(INDEX_NAMES))).all()}

    # then: FK는 users에 restrict이고 저장자 인덱스가 있다
    assert fks == {("fk_storage_settings_updated_by_user_id_users", "users", "r")}
    assert "ix_storage_settings_updated_by_user_id" in indexes


async def test_the_table_passes_the_schema_integrity_rules(session: AsyncSession) -> None:
    """테이블이 스키마 무결성 규칙을 통과한다."""
    # when: 스키마 무결성을 점검한다 (전제: head 스키마의 DB 세션)
    result = await check_schema(session, only_tables={"storage_settings"})
    # then: 위반 목록이 비어 있다
    assert result == []
