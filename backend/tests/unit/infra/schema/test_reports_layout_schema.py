"""head 스키마의 reports.layout(결과 배치).

layout은 NULL 가능한 JSONB이고 NULL이 아니면 JSON 객체여야 한다(CHECK ck_reports_layout_object).
기존 행은 NULL(= 기본 배치로 응답)이다. 실패하는 INSERT는 테스트마다 하나뿐이다.
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

COLUMN = (
    "select data_type, is_nullable, column_default from information_schema.columns"
    " where table_schema = 'public' and table_name = 'reports' and column_name = 'layout'"
)
SET_LAYOUT = "update reports set layout = cast(:value as jsonb) where id = :id"


async def test_reports_layout_column_nullable_jsonb_with_object_check(
    session: AsyncSession,
) -> None:
    """layout 컬럼은 기본값 없는 NULL 가능 JSONB다.

    테스트 코드: RS-049
    """
    # when: 컬럼 정보를 읽는다
    row = (await session.execute(text(COLUMN))).one()
    # then: jsonb, NULL 가능, 기본값 없음이다
    assert (row.data_type, row.is_nullable, row.column_default) == ("jsonb", "YES", None)


async def test_a_report_inserted_without_layout_has_a_null_layout(session: AsyncSession) -> None:
    """배치 없이 넣은 행의 layout은 NULL이다(기본 배치로 읽힌다).

    테스트 코드: RS-049
    """
    # given: layout 없이 넣은 리포트
    owner = await insert_user(session, "layout-owner")
    report_id = await insert_report(session, owner)
    # when: layout 값을 읽는다
    value = (
        await session.execute(text("select layout from reports where id = :id"), {"id": report_id})
    ).scalar_one()
    # then: NULL이다
    assert value is None


async def test_layout_accepts_a_json_object(session: AsyncSession) -> None:
    """layout은 JSON 객체를 받아 그대로 저장한다.

    테스트 코드: RS-049
    """
    # given: 리포트와 배치 JSON 객체
    owner = await insert_user(session, "layout-owner")
    report_id = await insert_report(session, owner)
    value = '{"view": "both", "order": ["table", "chart"], "arrange": "stacked"}'
    # when: layout을 쓰고 읽는다
    await session.execute(text(SET_LAYOUT), {"value": value, "id": report_id})
    stored = (
        await session.execute(text("select layout from reports where id = :id"), {"id": report_id})
    ).scalar_one()
    # then: 같은 객체다
    assert stored == {"view": "both", "order": ["table", "chart"], "arrange": "stacked"}


@pytest.mark.parametrize("value", ["[]", '"both"', "1", "true"])
async def test_layout_check_rejects_a_non_object_json(session: AsyncSession, value: str) -> None:
    """layout CHECK는 JSON 객체가 아닌 값(배열·문자열·숫자·불리언)을 거절한다.

    테스트 코드: RS-049
    """
    # given: 리포트
    owner = await insert_user(session, "layout-owner")
    report_id = await insert_report(session, owner)
    # when·then: 객체가 아닌 값을 쓰면 CHECK가 거절한다
    with pytest.raises(IntegrityError, match="ck_reports_layout_object"):
        await session.execute(text(SET_LAYOUT), {"value": value, "id": report_id})


async def test_the_schema_has_no_integrity_violations_with_the_layout_column(
    session: AsyncSession,
) -> None:
    """layout 컬럼이 있는 head 스키마는 공통 무결성 점검을 통과한다."""
    # when: 스키마를 점검한다
    violations = await check_schema(session)
    # then: 위반이 없다
    assert violations == []
