"""사용자 관리 영역에서 공개 API가 없어 DB에 직접 두거나 DB로 확인하는 step.

- 사용자를 FK로 참조하는 행(삭제하면 퇴사 처리되는 대상 만들기)
- users 표의 역할 변경(역할 수정 API가 없다)
- 세션 행·재직 admin 수 확인
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.auth.credentials import LoginId
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.functional.steps.auth import USERS, RoleName, given_user_registered
from tests.support.user_links import link_user

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Role
    from tests.functional.conftest import Api


@asynccontextmanager
async def _uow_factory(api: Api) -> AsyncIterator[UnitOfWorkFactory]:
    engine = create_async_engine(api.database_url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


async def _query_scalar(api: Api, sql: str, **params: object) -> object:
    engine = create_async_engine(api.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return (await connection.execute(text(sql), params)).scalar_one()
    finally:
        await engine.dispose()


async def given_user_linked(api: Api, *, login_id: str, kind: str) -> None:
    """사용자를 FK로 참조하는 행(`kind` 종류)이 있어 삭제하면 퇴사 처리된다."""
    async with _uow_factory(api) as uow_factory:
        async with uow_factory() as uow:
            user = await uow.users.get_active_by_login_id(LoginId(login_id))
        assert user is not None, login_id
        await link_user(uow_factory, user, kind)


async def given_user_resigned(api: Api, *, login_id: str, role: RoleName = "sales") -> str:
    """연결된 행이 있는 사용자를 등록해 퇴사 처리했다. 사용자 id를 돌려준다."""
    user_id = await given_user_registered(api, login_id=login_id, role=role)
    await given_user_linked(api, login_id=login_id, kind="deal_owner")
    api.clock.advance(60)  # 퇴사 시각(deleted_at)이 등록 시각(created_at)과 구분되도록
    response = await api.delete(f"{USERS}/{user_id}")
    assert response.json() == {"outcome": "resigned"}, response.text
    return user_id


async def given_role_changed(api: Api, *, login_id: str, role: Role) -> None:
    """users 표의 역할을 바꿨다(역할 수정 API가 없어 DB에 직접 반영한다)."""
    async with _uow_factory(api) as uow_factory, uow_factory() as uow:
        user = await uow.users.get_active_by_login_id(LoginId(login_id))
        assert user is not None, login_id
        user.role = role
        await uow.users.update(user)
        await uow.commit()


async def then_no_session_rows(api: Api, user_id: str) -> None:
    """DB에 그 사용자의 세션 행이 하나도 없다."""
    count = await _query_scalar(
        api, "select count(*) from auth_sessions where user_id = cast(:id as uuid)", id=user_id
    )
    assert count == 0
