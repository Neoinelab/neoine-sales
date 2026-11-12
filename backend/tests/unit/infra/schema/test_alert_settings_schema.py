"""head 스키마의 alert_settings: 단일 행 체크, 기준 범위 체크, 저장자 FK, 인덱스.

제약은 원시 INSERT로 직접 어겨 보고 제약 이름으로 거절되는지 확인한다(도메인 검증을 거치지 않는다).
임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다. 실패하는 INSERT는 테스트마다 하나뿐이다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.support.alert_rows import insert_alert_settings
from tests.support.head_rows import insert_user
from tests.support.ids import new_id
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
    """alert_settings 테이블은 계획한 컬럼과 타입을 가진다."""
    # when: 컬럼 정보를 조회한다 (전제: head 스키마의 임시 DB)
    columns = {r.column_name: r for r in (await session.execute(text(COLUMN_INFO))).all()}

    # then: 컬럼 이름과 타입이 계획과 같다
    assert set(columns) == {"id", "stale_days", "updated_at", "updated_by_user_id"}
    assert columns["id"].data_type == "smallint"
    assert columns["stale_days"].data_type == "smallint"
    assert columns["updated_at"].data_type == "timestamp with time zone"
    assert columns["updated_by_user_id"].data_type == "bigint"


async def test_every_column_is_required_including_the_saver(session: AsyncSession) -> None:
    """저장자를 포함한 모든 컬럼은 NOT NULL이다."""
    # when: 컬럼의 NULL 허용 여부를 조회한다
    columns = {r.column_name: r.is_nullable for r in (await session.execute(text(COLUMN_INFO)))}

    # then: 모든 컬럼이 NO다
    assert columns == {
        "id": "NO",
        "stale_days": "NO",
        "updated_at": "NO",
        "updated_by_user_id": "NO",
    }


async def test_the_migration_seeds_no_row(session: AsyncSession) -> None:
    """마이그레이션은 기본 행을 넣지 않는다."""
    # when: 행 수를 조회한다
    result = (await session.execute(text(COUNT))).scalar()
    # then: 0이다
    assert result == 0


async def test_the_single_row_with_id_one_is_accepted(session: AsyncSession) -> None:
    """id가 1인 단일 행은 저장된다."""
    # given: 저장자가 될 사용자 (id 1 행)
    admin = await insert_user(session, "root")

    # when: 설정 행을 넣는다
    await insert_alert_settings(session, admin)

    # then: 행이 하나다
    assert (await session.execute(text(COUNT))).scalar() == 1


async def test_any_id_other_than_one_is_rejected(session: AsyncSession) -> None:
    """id가 1이 아니면 거부한다."""
    # given: 저장자가 될 사용자 (id 1이 아닌 행)
    admin = await insert_user(session, "root")

    # when·then: id 2로 넣으면 단일 행 체크 제약 위반이다
    with pytest.raises(IntegrityError, match="ck_alert_settings_single_row"):
        await insert_alert_settings(session, admin, id=2)


async def test_a_second_row_is_rejected(session: AsyncSession) -> None:
    """두 번째 행은 거부한다."""
    # given: 저장자가 될 사용자 (두 번째 행)
    admin = await insert_user(session, "root")
    # given: 이미 설정 행이 있다
    await insert_alert_settings(session, admin)

    # when·then: 한 행 더 넣으면 PK 위반이다
    with pytest.raises(IntegrityError, match="pk_alert_settings"):
        await insert_alert_settings(session, admin)


@pytest.mark.parametrize("days", [1, 365])
async def test_stale_days_at_the_bounds_are_accepted(session: AsyncSession, days: int) -> None:
    """경고 기준 일수의 경계값 1과 365는 허용한다."""
    # given: 저장자가 될 사용자 (일수 경계값)
    admin = await insert_user(session, "root")

    # when: 경계 일수로 넣는다
    await insert_alert_settings(session, admin, stale_days=days)

    # then: 그 값이 저장된다
    assert (await session.execute(text("select stale_days from alert_settings"))).scalar() == days


@pytest.mark.parametrize("days", [0, 366, -1])
async def test_stale_days_outside_the_range_are_rejected(session: AsyncSession, days: int) -> None:
    """경고 기준 일수가 1~365 밖이면 거부한다."""
    # given: 저장자가 될 사용자 (일수 범위 밖)
    admin = await insert_user(session, "root")

    # when·then: 범위 밖 일수로 넣으면 범위 체크 제약 위반이다
    with pytest.raises(IntegrityError, match="ck_alert_settings_stale_days_range"):
        await insert_alert_settings(session, admin, stale_days=days)


async def test_a_saver_that_is_not_a_user_is_rejected(session: AsyncSession) -> None:
    """저장자가 사용자가 아니면 거부한다."""
    # when·then: 없는 사용자 id로 넣으면 FK 위반이다
    with pytest.raises(IntegrityError, match="fk_alert_settings_updated_by_user_id_users"):
        await insert_alert_settings(session, new_id())


async def test_a_user_who_saved_the_settings_cannot_be_deleted(session: AsyncSession) -> None:
    """설정을 저장한 사용자는 삭제할 수 없다."""
    # given: 저장자가 될 사용자 (삭제 시도 대상)
    admin = await insert_user(session, "root")
    # given: 그 사용자가 저장한 설정
    await insert_alert_settings(session, admin)

    # when·then: 사용자를 삭제하면 FK 위반이다
    with pytest.raises(IntegrityError, match="fk_alert_settings_updated_by_user_id_users"):
        await session.execute(text("delete from users where id = :id"), {"id": admin})


async def test_the_saver_foreign_key_restricts_and_leads_an_index(session: AsyncSession) -> None:
    """저장자 FK는 RESTRICT이며 선행 인덱스가 있다."""
    # when: FK와 인덱스 목록을 조회한다
    fks = {(r[0], r[1], r[2].strip()) for r in (await session.execute(text(FOREIGN_KEYS))).all()}
    indexes = {str(r[0]) for r in (await session.execute(text(INDEX_NAMES))).all()}

    # then: RESTRICT FK 하나와 저장자 인덱스가 있다
    assert fks == {("fk_alert_settings_updated_by_user_id_users", "users", "r")}
    assert "ix_alert_settings_updated_by_user_id" in indexes


async def test_the_table_passes_the_schema_integrity_rules(session: AsyncSession) -> None:
    """테이블은 스키마 무결성 규칙을 통과한다."""
    # when: 스키마 무결성을 점검한다
    result = await check_schema(session, only_tables={"alert_settings"})
    # then: 위반 목록이 비어 있다
    assert result == []
