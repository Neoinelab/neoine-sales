"""head 스키마의 reports.

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
    """reports 테이블의 컬럼 타입·길이·NULL 여부가 명세와 같다.

    테스트 코드: RS-049
    """
    # when: 테이블의 컬럼 정보를 읽는다
    rows = (await session.execute(text(COLUMNS))).all()
    columns = {
        r.column_name: (r.data_type, r.character_maximum_length, r.is_nullable) for r in rows
    }
    # then: 컬럼 13개의 타입·길이·NULL 여부가 명세와 같다
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
    """설명 컬럼에는 DB 기본값이 없다.

    테스트 코드: RS-049
    """
    # when: 컬럼의 기본값을 읽는다
    defaults = {
        r.column_name: r.column_default for r in (await session.execute(text(COLUMNS))).all()
    }
    # then: description의 기본값이 없다
    assert defaults["description"] is None


async def test_foreign_keys_restrict_to_users(session: AsyncSession) -> None:
    """만든 사람·최종 수정자 FK는 users를 RESTRICT로 가리킨다.

    테스트 코드: RS-049
    """
    # when: reports의 외래 키를 읽는다
    rows = (await session.execute(text(FOREIGN_KEYS))).all()
    # then: 사용자 FK 두 개가 RESTRICT(r)다
    assert {(r.conname, r.confrelid, r.confdeltype.strip(), r.attname) for r in rows} == {
        ("fk_reports_owner_user_id_users", "users", "r", "owner_user_id"),
        ("fk_reports_updated_by_user_id_users", "users", "r", "updated_by_user_id"),
    }


async def test_a_user_with_a_report_cannot_be_physically_deleted(session: AsyncSession) -> None:
    """리포트를 만든 사용자 행은 물리 삭제할 수 없다.

    테스트 코드: RS-049
    """
    # given: 리포트를 만든 사용자
    owner = await insert_user(session, "report-owner")
    await insert_report(session, owner)
    # when·then: 사용자 행을 지우면 만든 사람 FK가 거절한다
    with pytest.raises(IntegrityError, match="fk_reports_owner_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": owner})


async def test_a_user_who_last_edited_a_report_cannot_be_physically_deleted(
    session: AsyncSession,
) -> None:
    """리포트를 마지막으로 수정한 사용자 행도 물리 삭제할 수 없다.

    테스트 코드: RS-049
    """
    # given: 다른 사람이 만든 리포트를 마지막으로 수정한 사용자
    owner = await insert_user(session, "report-owner")
    editor = await insert_user(session, "report-editor")
    await insert_report(session, owner, updated_by_user_id=editor)
    # when·then: 수정자 행을 지우면 최종 수정자 FK가 거절한다
    with pytest.raises(IntegrityError, match="fk_reports_updated_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": editor})


async def test_lower_name_index_is_unique_over_all_reports(session: AsyncSession) -> None:
    """이름 인덱스는 lower(name) 유니크이고 만든 사람 열을 포함하지 않는다.

    테스트 코드: RS-049
    """
    # when: reports의 인덱스 정의를 읽는다
    definitions = {r.indexname: r.indexdef for r in (await session.execute(text(INDEXES))).all()}
    # then: 이름 인덱스는 lower 유니크이고 만든 사람 열과 무관하며 사용자 열 인덱스는 일반이다
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
    """같은 사람이 대소문자만 다른 이름을 넣으면 이름 인덱스가 거절한다.

    테스트 코드: RS-049
    """
    # given: "Sales" 리포트
    owner = await insert_user(session, "report-owner")
    await insert_report(session, owner, name="Sales")
    # when·then: "sALES"를 넣으면 이름 인덱스가 거절한다
    with pytest.raises(IntegrityError, match="uq_reports_name_lower"):
        await insert_report(session, owner, name="sALES")


async def test_lower_name_unique_index_rejects_the_same_name_of_a_different_owner(
    session: AsyncSession,
) -> None:
    """다른 사람이 대소문자만 다른 이름을 넣어도 이름 인덱스가 거절한다.

    테스트 코드: RS-049
    """
    # given: 한 사용자의 비공개 "Sales" 리포트
    first = await insert_user(session, "report-a")
    second = await insert_user(session, "report-b")
    await insert_report(session, first, name="Sales", visibility="private")
    # when·then: 다른 사용자가 "SALES"를 넣으면 이름 인덱스가 거절한다
    with pytest.raises(IntegrityError, match="uq_reports_name_lower"):
        await insert_report(session, second, name="SALES")


@pytest.mark.parametrize("visibility", ["public", "private"])
async def test_visibility_accepts_public_and_private(
    session: AsyncSession, visibility: str
) -> None:
    """공개 범위 CHECK는 public과 private를 받는다.

    테스트 코드: RS-049
    """
    # given: 사용자
    owner = await insert_user(session, "report-owner")
    # when: public 또는 private으로 넣는다
    await insert_report(session, owner, visibility=visibility)
    # then: 오류 없이 저장된다


async def test_visibility_check_rejects_other_values(session: AsyncSession) -> None:
    """공개 범위 CHECK는 다른 값을 거절한다.

    테스트 코드: RS-049
    """
    # given: 사용자
    owner = await insert_user(session, "report-owner")
    # when·then: "shared"를 넣으면 CHECK가 거절한다
    with pytest.raises(IntegrityError, match="ck_reports_visibility_valid"):
        await insert_report(session, owner, visibility="shared")


async def test_revision_check_rejects_zero(session: AsyncSession) -> None:
    """revision CHECK(>= 1)는 0을 거절한다.

    테스트 코드: RS-049
    """
    # given: 사용자
    owner = await insert_user(session, "report-owner")
    # when·then: revision 0을 넣으면 CHECK가 거절한다
    with pytest.raises(IntegrityError, match="ck_reports_revision_positive"):
        await insert_report(session, owner, revision=0)


async def test_definition_check_rejects_a_json_array(session: AsyncSession) -> None:
    """정의 CHECK는 JSON 객체가 아닌 값을 거절한다.

    테스트 코드: RS-049
    """
    # given: 사용자
    owner = await insert_user(session, "report-owner")
    # when·then: 배열 정의를 넣으면 CHECK가 거절한다
    with pytest.raises(IntegrityError, match="ck_reports_definition_object"):
        await insert_report(session, owner, definition="[]")


async def test_name_longer_than_100_is_rejected_by_the_column(session: AsyncSession) -> None:
    """101자 이름은 컬럼이 거절한다.

    테스트 코드: RS-049
    """
    # given: 사용자
    owner = await insert_user(session, "report-owner")
    # when·then: 101자 이름을 넣으면 컬럼 길이가 거절한다
    with pytest.raises(Exception, match="too long"):
        await insert_report(session, owner, name="가" * 101)


async def test_the_schema_has_no_integrity_violations_with_reports(session: AsyncSession) -> None:
    """reports 테이블이 있는 head 스키마는 공통 무결성 점검을 통과한다."""
    # when: 스키마를 점검한다
    violations = await check_schema(session)
    # then: 위반이 없다
    assert violations == []
