"""로그인·세션 feature가 쓰는 실제 DB 조회·조작 step.

API로 만들 수 없는 상태(중복 재직 행, 만료된 세션, DB에서 직접 일어난 변경)를 준비하고,
필요할 때만 DB 상태를 확인한다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infra.db.user_repository import SqlUserRepository
from tests.factories_auth import make_resigned_user, make_user

if TYPE_CHECKING:
    from app.domain.auth.principal import Role
    from tests.functional.conftest import Api


async def sql_rows(api: Api, statement: str, **params: object) -> list[tuple[object, ...]]:
    """문장을 실행하고(커밋) 조회 결과 행을 돌려준다."""
    engine = create_async_engine(api.database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(statement), params)
            return [tuple(row) for row in result] if result.returns_rows else []
    finally:
        await engine.dispose()


async def given_extra_user_row(
    api: Api, *, login_id: str, role: Role, resigned: bool = False
) -> None:
    """같은 로그인 아이디의 사용자 행이 DB에 하나 더 있다(재직 중복은 API로 만들 수 없다)."""
    engine = create_async_engine(api.database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, class_=AsyncSession)() as session:
            user = make_resigned_user(login_id, role) if resigned else make_user(login_id, role)
            await SqlUserRepository(session).add(user)
            await session.commit()
    finally:
        await engine.dispose()


async def given_session_expired(api: Api) -> None:
    """저장된 모든 세션의 유효 시간이 지났다."""
    await sql_rows(
        api,
        "update auth_sessions"
        " set created_at = now() - interval '9 hours', expires_at = now() - interval '1 hour'",
    )


async def given_role_changed_in_database(api: Api, *, login_id: str, role: str) -> None:
    """DB에서 직접 그 사원의 역할을 바꿨다."""
    await sql_rows(
        api,
        "update users set role = :role where login_id = :login_id",
        role=role,
        login_id=login_id,
    )


async def given_employee_removed_from_database(api: Api, *, login_id: str) -> None:
    """DB에서 그 사원의 세션과 사용자 행을 직접 지웠다(세션 FK 때문에 세션을 먼저 지운다)."""
    await sql_rows(
        api,
        "delete from auth_sessions"
        " where user_id = (select id from users where login_id = :login_id)",
        login_id=login_id,
    )
    await sql_rows(api, "delete from users where login_id = :login_id", login_id=login_id)


async def given_directory_settings_changed_in_database(api: Api, *, base_dn: str) -> None:
    """DB의 AD 설정이 다른 곳에서 바뀌었다(base_dn, revision 2)."""
    await sql_rows(
        api, "update directory_settings set base_dn = :base_dn, revision = 2", base_dn=base_dn
    )


async def then_no_failure_is_counted(api: Api) -> None:
    """시도 제한 카운터(계정·IP)에 남은 실패 횟수가 없다(예약했던 시도가 반환됐다)."""
    rows = await sql_rows(api, "select count(*) from login_failures where failures > 0")
    assert rows == [(0,)]


async def then_no_secret_is_stored(api: Api, *, secrets: list[str]) -> None:
    """인증 관련 4개 테이블 어디에도 주어진 비밀 값이 없다. 검사가 의미 있도록 행이 있어야 한다."""
    tables = (
        "users",
        "login_failures",
        "directory_settings",
        "auth_sessions",
        "user_password_hashes",
    )
    for table in tables:
        rows = await sql_rows(api, f"select t::text from {table} t")  # noqa: S608
        content = "\n".join(str(row[0]) for row in rows)
        for secret in secrets:
            assert secret not in content, table
        if table in ("users", "login_failures"):
            assert content, f"{table}에 행이 없어 검사가 의미 없다"
        if table == "login_failures":
            assert "kim" not in content
            assert "127.0.0.1" not in content
