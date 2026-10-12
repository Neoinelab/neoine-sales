"""사용자·로그인 실패·AD 설정 마이그레이션(MIG-1~4, T-P12~P14·P24).

expand 마이그레이션이어야 하므로 기존 테이블·데이터가 그대로이고, 이전 릴리스 코드가 쓰는 SQL이
새 스키마에서도 동작하는지 확인한다.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

if TYPE_CHECKING:
    from sqlalchemy.engine import URL, Connection

pytestmark = pytest.mark.integration

PREVIOUS_REVISION = "39d531ff2643"
NEW_TABLES = {"users", "login_failures", "directory_settings"}
USER_COLUMNS = {
    "id",
    "created_at",
    "updated_at",
    "deleted_at",
    "login_id",
    "role",
    "display_name",
    "email",
    "created_by",
    "last_login_at",
}
SETTINGS_COLUMNS = {
    "id",
    "revision",
    "server_urls",
    "use_starttls",
    "ca_cert_pem",
    "bind_template",
    "base_dn",
    "user_filter",
    "display_name_attribute",
    "email_attribute",
    "connect_timeout_seconds",
    "receive_timeout_seconds",
    "updated_at",
    "updated_by",
}
FAILURE_COLUMNS = {"key", "failures", "window_started_at", "locked_until"}


async def _insert_user(session: AsyncSession, login_id: str = "kim", **overrides: object) -> None:
    values: dict[str, object] = {
        "id": uuid4(),
        "login_id": login_id,
        "role": "sales",
        "created_by": "admin",
        "deleted_at": None,
    }
    values.update(overrides)
    await session.execute(
        text(
            "insert into users (id, login_id, role, created_by, created_at, updated_at,"
            " deleted_at) values (:id, :login_id, :role, :created_by, now(), now(), :deleted_at)"
        ),
        values,
    )


async def _insert_settings(session: AsyncSession, **overrides: object) -> None:
    values: dict[str, object] = {
        "id": 1,
        "revision": 1,
        "connect_timeout_seconds": 5,
        "receive_timeout_seconds": 10,
    }
    values.update(overrides)
    await session.execute(
        text(
            "insert into directory_settings (id, revision, server_urls, use_starttls,"
            " bind_template, base_dn, user_filter, display_name_attribute, email_attribute,"
            " connect_timeout_seconds, receive_timeout_seconds, updated_at)"
            " values (:id, :revision, cast('[\"ldaps://dc1.corp.test\"]' as jsonb), false,"
            " 'cn={login_id}', 'dc=corp', '(cn={login_id})', 'displayName', 'mail',"
            " :connect_timeout_seconds, :receive_timeout_seconds, now())"
        ),
        values,
    )


async def test_head_creates_the_auth_tables_with_expected_columns(test_database_url: URL) -> None:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:

            def read(sync_connection: Connection) -> dict[str, set[str]]:
                inspector = inspect(sync_connection)
                assert inspector is not None
                return {
                    name: {c["name"] for c in inspector.get_columns(name)}
                    for name in sorted(NEW_TABLES)
                }

            columns = await connection.run_sync(read)
    finally:
        await engine.dispose()

    assert columns["users"] == USER_COLUMNS
    assert columns["directory_settings"] == SETTINGS_COLUMNS
    assert columns["login_failures"] == FAILURE_COLUMNS


async def test_users_nullability_matches_the_design(session: AsyncSession) -> None:
    rows = await session.execute(
        text(
            "select column_name, is_nullable from information_schema.columns"
            " where table_name = 'users'"
        )
    )
    nullable = {name: flag == "YES" for name, flag in rows}

    assert {k for k, v in nullable.items() if v} == {
        "deleted_at",
        "display_name",
        "email",
        "last_login_at",
    }


async def test_indexes_exist_with_the_planned_definitions(session: AsyncSession) -> None:
    rows = await session.execute(
        text(
            "select indexname, indexdef from pg_indexes where indexname in"
            " ('uq_users_login_id_active', 'ix_users_created_at_id', 'ix_auth_sessions_subject')"
        )
    )
    definitions: dict[str, str] = {str(n): str(d) for n, d in rows}

    assert set(definitions) == {
        "uq_users_login_id_active",
        "ix_users_created_at_id",
        "ix_auth_sessions_subject",
    }
    unique = definitions["uq_users_login_id_active"]
    assert "UNIQUE" in unique
    assert "lower(" in unique
    assert "deleted_at IS NULL" in unique
    assert "(created_at, id)" in definitions["ix_users_created_at_id"]
    assert "(subject)" in definitions["ix_auth_sessions_subject"]


async def test_active_login_id_is_unique_in_the_database(session: AsyncSession) -> None:
    await _insert_user(session, "kim")

    with pytest.raises(IntegrityError, match="uq_users_login_id_active"):
        await _insert_user(session, "kim")


async def test_active_login_id_uniqueness_ignores_case(session: AsyncSession) -> None:
    await _insert_user(session, "kim")

    with pytest.raises(IntegrityError, match="uq_users_login_id_active"):
        await _insert_user(session, "KIM")


async def test_deleted_login_id_can_be_registered_again(session: AsyncSession) -> None:
    await _insert_user(session, "kim", deleted_at=None)
    await session.execute(text("update users set deleted_at = now() where login_id = 'kim'"))

    await _insert_user(session, "kim")

    count = await session.scalar(text("select count(*) from users where login_id = 'kim'"))
    assert count == 2


async def test_multiple_deleted_users_may_share_a_login_id(session: AsyncSession) -> None:
    await _insert_user(session, "kim", deleted_at=datetime.now(UTC))
    await _insert_user(session, "kim", deleted_at=datetime.now(UTC))


async def test_user_role_is_restricted_by_check(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_users"):
        await _insert_user(session, "kim", role="owner")


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_allowed_user_roles_are_accepted(session: AsyncSession, role: str) -> None:
    await _insert_user(session, "kim", role=role)


async def test_login_failure_count_cannot_be_negative(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_login_failures"):
        await session.execute(
            text(
                "insert into login_failures (key, failures, window_started_at)"
                " values ('k', -1, now())"
            )
        )


async def test_valid_directory_settings_row_is_accepted(session: AsyncSession) -> None:
    await _insert_settings(session)


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": 2},
        {"id": 0},
        {"revision": 0},
        {"revision": -1},
        {"connect_timeout_seconds": 0},
        {"connect_timeout_seconds": 31},
        {"receive_timeout_seconds": 0},
        {"receive_timeout_seconds": 61},
    ],
    ids=lambda o: ",".join(f"{k}={v}" for k, v in o.items()),
)
async def test_directory_settings_checks(session: AsyncSession, overrides: dict[str, int]) -> None:
    with pytest.raises(IntegrityError, match="ck_directory_settings"):
        await _insert_settings(session, **overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"connect_timeout_seconds": 1, "receive_timeout_seconds": 1},
        {"connect_timeout_seconds": 30, "receive_timeout_seconds": 60},
    ],
)
async def test_directory_settings_timeout_boundaries_are_accepted(
    session: AsyncSession, overrides: dict[str, int]
) -> None:
    await _insert_settings(session, **overrides)


async def test_directory_settings_allows_only_one_row(session: AsyncSession) -> None:
    await _insert_settings(session)

    with pytest.raises(IntegrityError, match="pk_directory_settings"):
        await _insert_settings(session)
