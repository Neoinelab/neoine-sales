"""head 스키마의 directory_settings(서비스 계정 개편)와 user_password_hashes (AC3·AC11·AC13).

설정 테이블은 구 컬럼(server_urls 등)이 없고 새 컬럼·체크 제약을 가진다. 해시 테이블은 사용자 id가
PK이자 FK이며 사용자 삭제 때 CASCADE로 지워진다. 임시 DB의 head에서 돌며 세션은 테스트마다 롤백된다.
실패하는 INSERT는 테스트마다 하나뿐이다.
"""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.support.directory_rows import insert_password_hash, insert_settings
from tests.support.head_rows import insert_user
from tests.support.schema_integrity import check_schema

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

COLUMNS = (
    "select column_name, data_type, character_maximum_length, is_nullable"
    " from information_schema.columns where table_schema = 'public' and table_name = :table"
)
CHECKS = (
    "select conname from pg_constraint where conrelid = cast(:table as regclass) and contype = 'c'"
)
FOREIGN_KEYS = (
    "select conname, confrelid::regclass::text, confdeltype::text, a.attname"
    " from pg_constraint c"
    " join pg_attribute a on a.attrelid = c.conrelid and a.attnum = any(c.conkey)"
    " where c.conrelid = cast(:table as regclass) and c.contype = 'f'"
)


async def _columns(session: AsyncSession, table: str) -> dict[str, tuple[str, int | None, str]]:
    rows = (await session.execute(text(COLUMNS), {"table": table})).all()
    return {r.column_name: (r.data_type, r.character_maximum_length, r.is_nullable) for r in rows}


async def test_directory_settings_columns_types_and_nullability(session: AsyncSession) -> None:
    columns = await _columns(session, "directory_settings")

    assert columns == {
        "id": ("smallint", None, "NO"),
        "revision": ("integer", None, "NO"),
        "host": ("character varying", 253, "NO"),
        "port": ("integer", None, "NO"),
        "security": ("character varying", 16, "NO"),
        "bind_account": ("character varying", 256, "NO"),
        "bind_password_encrypted": ("text", None, "NO"),
        "base_dn": ("character varying", 512, "NO"),
        "user_filter": ("character varying", 512, "NO"),
        "connect_timeout_seconds": ("smallint", None, "NO"),
        "updated_at": ("timestamp with time zone", None, "NO"),
        "updated_by_user_id": ("bigint", None, "YES"),
    }


@pytest.mark.parametrize(
    "old",
    [
        "server_urls",
        "use_starttls",
        "ca_cert_pem",
        "bind_template",
        "display_name_attribute",
        "email_attribute",
        "receive_timeout_seconds",
    ],
)
async def test_old_columns_are_gone(session: AsyncSession, old: str) -> None:
    assert old not in await _columns(session, "directory_settings")


async def test_directory_settings_check_constraints_are_the_new_set(session: AsyncSession) -> None:
    names = {
        r.conname for r in (await session.execute(text(CHECKS), {"table": "directory_settings"}))
    }

    assert {
        "ck_directory_settings_single_row",
        "ck_directory_settings_revision_positive",
        "ck_directory_settings_connect_timeout_range",
        "ck_directory_settings_port_range",
        "ck_directory_settings_security_values",
    } <= names
    assert "ck_directory_settings_receive_timeout_range" not in names


async def test_a_valid_settings_row_is_accepted(session: AsyncSession) -> None:
    await insert_settings(session)

    count = (await session.execute(text("select count(*) from directory_settings"))).scalar_one()
    assert count == 1


@pytest.mark.parametrize("security", ["none", "ssl", "starttls"])
async def test_every_security_mode_is_accepted(session: AsyncSession, security: str) -> None:
    await insert_settings(session, security=security)


@pytest.mark.parametrize("port", [1, 389, 65535])
async def test_port_boundaries_are_accepted(session: AsyncSession, port: int) -> None:
    await insert_settings(session, port=port)


@pytest.mark.parametrize("port", [0, -1, 65536])
async def test_port_outside_range_is_rejected(session: AsyncSession, port: int) -> None:
    with pytest.raises(IntegrityError, match="ck_directory_settings_port_range"):
        await insert_settings(session, port=port)


@pytest.mark.parametrize("security", ["", "SSL", "tls", "ldaps"])
async def test_unknown_security_value_is_rejected(session: AsyncSession, security: str) -> None:
    with pytest.raises(IntegrityError, match="ck_directory_settings_security_values"):
        await insert_settings(session, security=security)


@pytest.mark.parametrize("seconds", [0, 31, -1])
async def test_connect_timeout_outside_range_is_rejected(
    session: AsyncSession, seconds: int
) -> None:
    with pytest.raises(IntegrityError, match="ck_directory_settings_connect_timeout_range"):
        await insert_settings(session, connect_timeout_seconds=seconds)


@pytest.mark.parametrize("seconds", [1, 30])
async def test_connect_timeout_boundaries_are_accepted(session: AsyncSession, seconds: int) -> None:
    await insert_settings(session, connect_timeout_seconds=seconds)


@pytest.mark.parametrize("overrides", [{"id": 2}, {"id": 0}, {"revision": 0}, {"revision": -1}])
async def test_single_row_and_revision_checks(
    session: AsyncSession, overrides: dict[str, int]
) -> None:
    with pytest.raises(IntegrityError, match="ck_directory_settings"):
        await insert_settings(session, **overrides)


async def test_directory_settings_allows_only_one_row(session: AsyncSession) -> None:
    await insert_settings(session)

    with pytest.raises(IntegrityError, match="pk_directory_settings"):
        await insert_settings(session)


async def test_long_sealed_password_token_is_accepted(session: AsyncSession) -> None:
    await insert_settings(session, bind_password_encrypted="gAAAAA" + "x" * 2000)


async def test_no_column_holds_a_plain_text_password_name(session: AsyncSession) -> None:
    rows = (
        await session.execute(
            text(
                "select table_name, column_name from information_schema.columns"
                " where table_schema = 'public' and column_name ilike '%password%'"
            )
        )
    ).all()

    assert {(r.table_name, r.column_name) for r in rows} == {
        ("directory_settings", "bind_password_encrypted"),
        ("user_password_hashes", "password_hash"),
    }


async def test_user_password_hashes_columns(session: AsyncSession) -> None:
    columns = await _columns(session, "user_password_hashes")

    assert columns == {
        "user_id": ("bigint", None, "NO"),
        "password_hash": ("character varying", 512, "NO"),
        "updated_at": ("timestamp with time zone", None, "NO"),
    }


async def test_user_password_hashes_primary_key_is_the_user_id(session: AsyncSession) -> None:
    rows = (
        await session.execute(
            text(
                "select a.attname, c.conname from pg_constraint c join pg_attribute a"
                " on a.attrelid = c.conrelid and a.attnum = any(c.conkey)"
                " where c.conrelid = 'user_password_hashes'::regclass and c.contype = 'p'"
            )
        )
    ).all()

    assert [(r.attname, r.conname) for r in rows] == [("user_id", "pk_user_password_hashes")]


async def test_user_password_hashes_foreign_key_cascades_from_users(session: AsyncSession) -> None:
    rows = (await session.execute(text(FOREIGN_KEYS), {"table": "user_password_hashes"})).all()

    assert {(r.conname, r.confrelid, r.confdeltype.strip(), r.attname) for r in rows} == {
        ("fk_user_password_hashes_user_id_users", "users", "c", "user_id")
    }


async def test_a_hash_row_is_accepted_for_an_existing_user(session: AsyncSession) -> None:
    user_id = await insert_user(session, "kim")

    await insert_password_hash(session, user_id)

    count = (await session.execute(text("select count(*) from user_password_hashes"))).scalar_one()
    assert count == 1


async def test_a_hash_row_for_a_missing_user_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="fk_user_password_hashes_user_id_users"):
        await insert_password_hash(session, 999_999_999_999)


async def test_a_second_hash_row_for_the_same_user_is_rejected(session: AsyncSession) -> None:
    user_id = await insert_user(session, "kim")
    await insert_password_hash(session, user_id)

    with pytest.raises(IntegrityError, match="pk_user_password_hashes"):
        await insert_password_hash(session, user_id)


async def test_hash_longer_than_512_characters_is_rejected(session: AsyncSession) -> None:
    user_id = await insert_user(session, "kim")

    with pytest.raises(DBAPIError):
        await insert_password_hash(session, user_id, password_hash="x" * 513)


async def test_deleting_the_user_deletes_the_hash(session: AsyncSession) -> None:
    user_id = await insert_user(session, "kim")
    await insert_password_hash(session, user_id)

    await session.execute(text("delete from users where id = :id"), {"id": user_id})

    count = (await session.execute(text("select count(*) from user_password_hashes"))).scalar_one()
    assert count == 0


async def test_the_schema_has_no_integrity_violations(session: AsyncSession) -> None:
    exists = (
        await session.execute(text("select to_regclass('public.user_password_hashes')"))
    ).scalar()

    assert exists is not None  # 점검 대상 테이블이 있어야 의미가 있다
    assert await check_schema(session) == []
