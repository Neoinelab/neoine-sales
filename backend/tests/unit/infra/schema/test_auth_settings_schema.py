"""head 스키마의 auth_settings(인증 방식)와 users.phone (순수 expand 마이그레이션).

auth_settings는 id=1 단일 행(CHECK), mode는 'ad'|'local'(CHECK)이고 users를 참조하지 않는다
(updated_by 없음). users.phone은 varchar(40) NULL이며 기존 행은 NULL이다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.support.head_rows import insert_user
from tests.support.schema_integrity import check_schema, user_foreign_keys

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMNS = (
    "select column_name, data_type, character_maximum_length, is_nullable"
    " from information_schema.columns"
    " where table_schema = 'public' and table_name = :table order by ordinal_position"
)
INSERT = "insert into auth_settings (id, mode, updated_at) values (:id, :mode, now())"


async def _columns(session: AsyncSession, table: str) -> dict[str, tuple[str, int | None, str]]:
    rows = (await session.execute(text(COLUMNS), {"table": table})).all()
    return {r.column_name: (r.data_type, r.character_maximum_length, r.is_nullable) for r in rows}


async def test_auth_settings_has_exactly_id_mode_and_updated_at(session: AsyncSession) -> None:
    """auth_settings는 id, mode, updated_at 컬럼만 가진다."""
    # when: 컬럼 정보를 조회한다 (전제: head 스키마의 임시 DB)
    columns = await _columns(session, "auth_settings")

    # then: 세 컬럼과 타입이 정해진 대로다
    assert columns == {
        "id": ("smallint", None, "NO"),
        "mode": ("character varying", 16, "NO"),
        "setup_pending": ("boolean", None, "NO"),
        "admin_setup_pending": ("boolean", None, "NO"),
        "updated_at": ("timestamp with time zone", None, "NO"),
    }


async def test_auth_settings_starts_empty_in_a_fresh_schema(session: AsyncSession) -> None:
    """새 스키마의 auth_settings는 비어 있다."""
    # when: 행 수를 조회한다
    count = (await session.execute(text("select count(*) from auth_settings"))).scalar_one()

    # then: 0이다
    assert count == 0


@pytest.mark.parametrize("mode", ["ad", "local"])
async def test_auth_settings_accepts_the_two_modes_in_row_one(
    session: AsyncSession, mode: str
) -> None:
    """1번 행에는 ad와 local 두 방식을 저장할 수 있다."""
    # when: 1번 행에 방식을 넣는다
    await session.execute(text(INSERT), {"id": 1, "mode": mode})

    # when: 저장된 방식을 읽는다
    stored = (await session.execute(text("select mode from auth_settings"))).scalar_one()
    # then: 넣은 방식과 같다
    assert stored == mode


@pytest.mark.parametrize("mode", ["", "AD", "ldap", "oidc"])
async def test_auth_settings_rejects_an_unknown_mode(session: AsyncSession, mode: str) -> None:
    """알 수 없는 방식은 거부한다."""
    # when·then: 허용되지 않은 방식을 넣으면 무결성 오류다
    with pytest.raises(IntegrityError):
        await session.execute(text(INSERT), {"id": 1, "mode": mode})


@pytest.mark.parametrize("row_id", [0, 2, -1])
async def test_auth_settings_allows_only_row_one(session: AsyncSession, row_id: int) -> None:
    """1번 행만 허용한다."""
    # when·then: 1이 아닌 id로 넣으면 무결성 오류다
    with pytest.raises(IntegrityError):
        await session.execute(text(INSERT), {"id": row_id, "mode": "local"})


async def test_auth_settings_rejects_a_second_row_one(session: AsyncSession) -> None:
    """1번 행을 두 번 넣을 수 없다."""
    # given: 1번 행이 이미 있다
    await session.execute(text(INSERT), {"id": 1, "mode": "ad"})

    # when·then: 1번 행을 다시 넣으면 무결성 오류다
    with pytest.raises(IntegrityError):
        await session.execute(text(INSERT), {"id": 1, "mode": "local"})


async def test_auth_settings_does_not_reference_users(session: AsyncSession) -> None:
    """auth_settings는 users를 참조하지 않는다."""
    # when: auth_settings가 가진 사용자 FK 목록을 구한다
    result = [fk for fk in await user_foreign_keys(session) if fk[0] == "auth_settings"]
    # then: 목록이 비어 있다
    assert result == []


async def test_users_phone_is_a_nullable_varchar_40(session: AsyncSession) -> None:
    """users.phone은 NULL 허용 varchar(40)이다."""
    # when: users 컬럼 정보를 조회한다
    columns = await _columns(session, "users")

    # then: phone은 varchar(40) NULL 허용이다
    assert columns["phone"] == ("character varying", 40, "YES")


async def test_a_user_inserted_without_phone_has_a_null_phone(session: AsyncSession) -> None:
    """전화번호 없이 넣은 사용자의 phone은 NULL이다."""
    # given: 전화번호 없이 넣은 사용자
    user_id = await insert_user(session, "phone-user")

    # when: phone을 읽는다
    phone = (
        await session.execute(text("select phone from users where id = :id"), {"id": user_id})
    ).scalar_one()

    # then: NULL이다
    assert phone is None


async def test_users_phone_rejects_a_value_over_forty_chars(session: AsyncSession) -> None:
    """phone은 40자를 넘으면 거부한다."""
    # given: 사용자
    user_id = await insert_user(session, "phone-user")

    # when·then: 41자로 수정하면 길이 초과 오류다
    with pytest.raises(DBAPIError, match="too long"):
        await session.execute(
            text("update users set phone = :phone where id = :id"),
            {"phone": "1" * 41, "id": user_id},
        )


async def test_the_schema_has_no_integrity_violations_with_the_new_table_and_column(
    session: AsyncSession,
) -> None:
    """새 테이블과 컬럼을 포함해도 스키마 무결성 위반이 없다."""
    # when: 스키마 무결성을 점검한다
    result = await check_schema(session)
    # then: 위반 목록이 비어 있다
    assert result == []
