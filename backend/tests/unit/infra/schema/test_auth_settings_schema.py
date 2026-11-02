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
    columns = await _columns(session, "auth_settings")

    assert columns == {
        "id": ("smallint", None, "NO"),
        "mode": ("character varying", 16, "NO"),
        "updated_at": ("timestamp with time zone", None, "NO"),
    }


async def test_auth_settings_starts_empty_in_a_fresh_schema(session: AsyncSession) -> None:
    count = (await session.execute(text("select count(*) from auth_settings"))).scalar_one()

    assert count == 0


@pytest.mark.parametrize("mode", ["ad", "local"])
async def test_auth_settings_accepts_the_two_modes_in_row_one(
    session: AsyncSession, mode: str
) -> None:
    await session.execute(text(INSERT), {"id": 1, "mode": mode})

    stored = (await session.execute(text("select mode from auth_settings"))).scalar_one()
    assert stored == mode


@pytest.mark.parametrize("mode", ["", "AD", "ldap", "oidc"])
async def test_auth_settings_rejects_an_unknown_mode(session: AsyncSession, mode: str) -> None:
    with pytest.raises(IntegrityError):
        await session.execute(text(INSERT), {"id": 1, "mode": mode})


@pytest.mark.parametrize("row_id", [0, 2, -1])
async def test_auth_settings_allows_only_row_one(session: AsyncSession, row_id: int) -> None:
    with pytest.raises(IntegrityError):
        await session.execute(text(INSERT), {"id": row_id, "mode": "local"})


async def test_auth_settings_rejects_a_second_row_one(session: AsyncSession) -> None:
    await session.execute(text(INSERT), {"id": 1, "mode": "ad"})

    with pytest.raises(IntegrityError):
        await session.execute(text(INSERT), {"id": 1, "mode": "local"})


async def test_auth_settings_does_not_reference_users(session: AsyncSession) -> None:
    assert [fk for fk in await user_foreign_keys(session) if fk[0] == "auth_settings"] == []


async def test_users_phone_is_a_nullable_varchar_40(session: AsyncSession) -> None:
    columns = await _columns(session, "users")

    assert columns["phone"] == ("character varying", 40, "YES")


async def test_a_user_inserted_without_phone_has_a_null_phone(session: AsyncSession) -> None:
    user_id = await insert_user(session, "phone-user")

    phone = (
        await session.execute(text("select phone from users where id = :id"), {"id": user_id})
    ).scalar_one()

    assert phone is None


async def test_users_phone_rejects_a_value_over_forty_chars(session: AsyncSession) -> None:
    user_id = await insert_user(session, "phone-user")

    with pytest.raises(DBAPIError, match="too long"):
        await session.execute(
            text("update users set phone = :phone where id = :id"),
            {"phone": "1" * 41, "id": user_id},
        )


async def test_the_schema_has_no_integrity_violations_with_the_new_table_and_column(
    session: AsyncSession,
) -> None:
    assert await check_schema(session) == []
