"""head 스키마의 directory_settings(서비스 계정 개편)와 user_password_hashes.

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
    """directory_settings의 컬럼 이름·타입·길이·NULL 허용이 서비스 계정 설계와 같다."""
    # when: 컬럼 정보를 조회한다
    columns = await _columns(session, "directory_settings")

    # then: directory_settings 컬럼의 이름·타입·길이·NULL 허용이 설계 표와 정확히 같다
    assert columns == {
        "id": ("smallint", None, "NO"),
        "revision": ("integer", None, "NO"),
        "host": ("character varying", 253, "NO"),
        "port": ("integer", None, "NO"),
        "security": ("character varying", 16, "NO"),
        "bind_account": ("character varying", 256, "YES"),
        "bind_password_encrypted": ("text", None, "YES"),
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
    """예전 컬럼은 directory_settings에 없다."""
    # when: 컬럼 정보를 조회한다
    columns = await _columns(session, "directory_settings")

    # then: 예전 컬럼이 없다
    assert old not in columns


async def test_directory_settings_check_constraints_are_the_new_set(session: AsyncSession) -> None:
    """directory_settings의 체크 제약은 새 집합이고 예전 수신 타임아웃 제약은 없다."""
    # when: 체크 제약 이름을 조회한다
    names = {
        r.conname for r in (await session.execute(text(CHECKS), {"table": "directory_settings"}))
    }

    # then: 새 제약이 모두 있고 예전 제약은 없다
    assert {
        "ck_directory_settings_single_row",
        "ck_directory_settings_revision_positive",
        "ck_directory_settings_connect_timeout_range",
        "ck_directory_settings_port_range",
        "ck_directory_settings_security_values",
    } <= names
    assert "ck_directory_settings_receive_timeout_range" not in names


async def test_a_valid_settings_row_is_accepted(session: AsyncSession) -> None:
    """올바른 설정 행은 저장된다."""
    # when: 올바른 설정 행을 넣는다
    await insert_settings(session)

    # then: 행이 하나 있다
    count = (await session.execute(text("select count(*) from directory_settings"))).scalar_one()
    assert count == 1


@pytest.mark.parametrize("security", ["none", "ssl", "starttls"])
async def test_every_security_mode_is_accepted(session: AsyncSession, security: str) -> None:
    """보안 연결 값 none·ssl·starttls는 모두 허용한다."""
    # when·then: 해당 보안 연결 값으로 넣어도 오류가 없다
    await insert_settings(session, security=security)


@pytest.mark.parametrize("port", [1, 389, 65535])
async def test_port_boundaries_are_accepted(session: AsyncSession, port: int) -> None:
    """포트 경계값 1·389·65535는 허용한다."""
    # when·then: 해당 포트로 넣어도 오류가 없다
    await insert_settings(session, port=port)


@pytest.mark.parametrize("port", [0, -1, 65536])
async def test_port_outside_range_is_rejected(session: AsyncSession, port: int) -> None:
    """범위(1~65535) 밖 포트는 거부한다."""
    # when·then: 범위 밖 포트로 넣으면 포트 범위 제약 위반이다
    with pytest.raises(IntegrityError, match="ck_directory_settings_port_range"):
        await insert_settings(session, port=port)


@pytest.mark.parametrize("security", ["", "SSL", "tls", "ldaps"])
async def test_unknown_security_value_is_rejected(session: AsyncSession, security: str) -> None:
    """알 수 없는 보안 연결 값은 거부한다."""
    # when·then: 알 수 없는 값으로 넣으면 보안 값 제약 위반이다
    with pytest.raises(IntegrityError, match="ck_directory_settings_security_values"):
        await insert_settings(session, security=security)


@pytest.mark.parametrize("seconds", [0, 31, -1])
async def test_connect_timeout_outside_range_is_rejected(
    session: AsyncSession, seconds: int
) -> None:
    """범위(1~30) 밖 연결 제한 시간은 거부한다."""
    # when·then: 범위 밖 값으로 넣으면 제한 시간 제약 위반이다
    with pytest.raises(IntegrityError, match="ck_directory_settings_connect_timeout_range"):
        await insert_settings(session, connect_timeout_seconds=seconds)


@pytest.mark.parametrize("seconds", [1, 30])
async def test_connect_timeout_boundaries_are_accepted(session: AsyncSession, seconds: int) -> None:
    """연결 제한 시간 경계값 1·30초는 허용한다."""
    # when·then: 경계값으로 넣어도 오류가 없다
    await insert_settings(session, connect_timeout_seconds=seconds)


@pytest.mark.parametrize("overrides", [{"id": 2}, {"id": 0}, {"revision": 0}, {"revision": -1}])
async def test_single_row_and_revision_checks(
    session: AsyncSession, overrides: dict[str, int]
) -> None:
    """id가 1이 아니거나 revision이 1 미만인 행은 거부한다."""
    # when·then: 잘못된 id나 revision으로 넣으면 체크 제약 위반이다
    with pytest.raises(IntegrityError, match="ck_directory_settings"):
        await insert_settings(session, **overrides)


async def test_directory_settings_allows_only_one_row(session: AsyncSession) -> None:
    """directory_settings에는 행이 하나만 들어간다."""
    # given: 설정 행이 이미 있다
    await insert_settings(session)

    # when·then: 한 행을 더 넣으면 기본 키 위반이다
    with pytest.raises(IntegrityError, match="pk_directory_settings"):
        await insert_settings(session)


async def test_long_sealed_password_token_is_accepted(session: AsyncSession) -> None:
    """긴 암호화 비밀번호 토큰도 저장된다."""
    # when·then: 2000자가 넘는 토큰으로 넣어도 오류가 없다
    await insert_settings(session, bind_password_encrypted="gAAAAA" + "x" * 2000)


async def test_no_column_holds_a_plain_text_password_name(session: AsyncSession) -> None:
    """비밀번호 이름이 든 컬럼은 암호화 컬럼과 해시 컬럼뿐이다."""
    # when: 이름에 password가 든 컬럼을 조회한다
    rows = (
        await session.execute(
            text(
                "select table_name, column_name from information_schema.columns"
                " where table_schema = 'public' and column_name ilike '%password%'"
            )
        )
    ).all()

    # then: 암호화 컬럼과 해시 컬럼뿐이다
    assert {(r.table_name, r.column_name) for r in rows} == {
        ("directory_settings", "bind_password_encrypted"),
        ("user_password_hashes", "password_hash"),
    }


async def test_user_password_hashes_columns(session: AsyncSession) -> None:
    """user_password_hashes의 컬럼이 설계와 같다."""
    # when: 컬럼 정보를 조회한다
    columns = await _columns(session, "user_password_hashes")

    # then: user_password_hashes 컬럼의 이름·타입·길이·NULL 허용이 설계 표와 정확히 같다
    assert columns == {
        "user_id": ("bigint", None, "NO"),
        "password_hash": ("character varying", 512, "NO"),
        "updated_at": ("timestamp with time zone", None, "NO"),
    }


async def test_user_password_hashes_primary_key_is_the_user_id(session: AsyncSession) -> None:
    """user_password_hashes의 기본 키는 user_id다."""
    # when: 기본 키 제약을 조회한다
    rows = (
        await session.execute(
            text(
                "select a.attname, c.conname from pg_constraint c join pg_attribute a"
                " on a.attrelid = c.conrelid and a.attnum = any(c.conkey)"
                " where c.conrelid = 'user_password_hashes'::regclass and c.contype = 'p'"
            )
        )
    ).all()

    # then: user_id 하나가 기본 키다
    assert [(r.attname, r.conname) for r in rows] == [("user_id", "pk_user_password_hashes")]


async def test_user_password_hashes_foreign_key_cascades_from_users(session: AsyncSession) -> None:
    """user_password_hashes.user_id는 users를 CASCADE로 참조한다."""
    # when: 외래 키 제약을 조회한다
    rows = (await session.execute(text(FOREIGN_KEYS), {"table": "user_password_hashes"})).all()

    # then: users를 CASCADE로 참조하는 제약 하나다
    assert {(r.conname, r.confrelid, r.confdeltype.strip(), r.attname) for r in rows} == {
        ("fk_user_password_hashes_user_id_users", "users", "c", "user_id")
    }


async def test_a_hash_row_is_accepted_for_an_existing_user(session: AsyncSession) -> None:
    """있는 사용자의 해시 행은 저장된다."""
    # given: 사용자 한 명
    user_id = await insert_user(session, "kim")

    # when: 그 사용자의 해시를 넣는다
    await insert_password_hash(session, user_id)

    # then: 해시 행이 하나 있다
    count = (await session.execute(text("select count(*) from user_password_hashes"))).scalar_one()
    assert count == 1


async def test_a_hash_row_for_a_missing_user_is_rejected(session: AsyncSession) -> None:
    """없는 사용자의 해시 행은 거부한다."""
    # when·then: 없는 사용자 id로 넣으면 외래 키 위반이다
    with pytest.raises(IntegrityError, match="fk_user_password_hashes_user_id_users"):
        await insert_password_hash(session, 999_999_999_999)


async def test_a_second_hash_row_for_the_same_user_is_rejected(session: AsyncSession) -> None:
    """같은 사용자의 해시 행을 하나 더 넣을 수 없다."""
    # given: 해시가 이미 있는 사용자
    user_id = await insert_user(session, "kim")
    await insert_password_hash(session, user_id)

    # when·then: 같은 사용자로 또 넣으면 기본 키 위반이다
    with pytest.raises(IntegrityError, match="pk_user_password_hashes"):
        await insert_password_hash(session, user_id)


async def test_hash_longer_than_512_characters_is_rejected(session: AsyncSession) -> None:
    """512자를 넘는 해시는 거부한다."""
    # given: 사용자 한 명
    user_id = await insert_user(session, "kim")

    # when·then: 513자 해시를 넣으면 DB 오류가 난다
    with pytest.raises(DBAPIError):
        await insert_password_hash(session, user_id, password_hash="x" * 513)


async def test_deleting_the_user_deletes_the_hash(session: AsyncSession) -> None:
    """사용자를 지우면 해시 행도 함께 지워진다."""
    # given: 해시가 있는 사용자
    user_id = await insert_user(session, "kim")
    await insert_password_hash(session, user_id)

    # when: 사용자를 삭제한다
    await session.execute(text("delete from users where id = :id"), {"id": user_id})

    # then: 해시 행이 없다
    count = (await session.execute(text("select count(*) from user_password_hashes"))).scalar_one()
    assert count == 0


async def test_the_schema_has_no_integrity_violations(session: AsyncSession) -> None:
    """head 스키마는 점검 규칙 위반이 없다."""
    # given: 점검 대상 테이블이 있다
    exists = (
        await session.execute(text("select to_regclass('public.user_password_hashes')"))
    ).scalar()

    # when: 스키마를 점검한다
    violations = await check_schema(session)

    # then: 점검 대상 테이블이 있고(없으면 점검이 의미 없다) 위반이 없다
    assert exists is not None
    assert violations == []
