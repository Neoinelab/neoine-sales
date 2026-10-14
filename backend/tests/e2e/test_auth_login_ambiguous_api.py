"""POST /api/v1/auth/login (R7): 재직 행 중복은 500이 아니라 401, 퇴사 1 + 재직 1은 정상 로그인."""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.principal import Role
from app.infra.db.user_repository import SqlUserRepository
from tests.e2e.conftest import AuthFullStack, new_client
from tests.e2e.payloads_auth import LOGIN, SETUP_DIRECTORY, credentials, directory_payload
from tests.factories_auth import make_resigned_user, make_user
from tests.support.auth_seed import DUMMY_PASSWORD, seed_user

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases


@pytest.mark.usefixtures("ready")
async def test_login_with_duplicate_active_rows_returns_401_not_500(
    anonymous_client: AsyncClient, ready: FakeUseCases
) -> None:
    await ready.seed_user("kim", Role.USER)  # ready가 이미 kim(sales)을 등록했다 -> 재직 2행

    response = await anonymous_client.post(LOGIN, json=credentials())

    assert response.status_code == 401
    assert response.json()["detail"] == LOGIN_FAILED
    assert not [h for h in response.headers.get_list("set-cookie") if "session" in h.lower()]


async def test_login_with_one_resigned_and_one_active_row_succeeds(
    anonymous_client: AsyncClient, ready: FakeUseCases
) -> None:
    await seed_user(lambda: ready.uow, "kim", Role.USER, resigned=True)

    response = await anonymous_client.post(LOGIN, json=credentials())

    assert response.status_code == 200
    assert response.json()["role"] == "sales"


@pytest.mark.integration
async def test_login_with_duplicate_active_rows_in_postgres_returns_401(
    auth_full_stack: AuthFullStack,
) -> None:
    auth_full_stack.directory.add_account("kim", DUMMY_PASSWORD)
    container, app = auth_full_stack.open_app()
    engine = create_async_engine(auth_full_stack.database_url, poolclass=NullPool)
    try:
        async with new_client(app) as http:
            assert (await http.put(SETUP_DIRECTORY, json=directory_payload())).status_code == 200
            async with async_sessionmaker(engine, class_=AsyncSession)() as session:
                repository = SqlUserRepository(session)
                await repository.add(make_resigned_user("kim"))
                await repository.add(make_user("kim", Role.SALES))
                await repository.add(make_user("kim", Role.USER))  # DB 유일 제약이 없다
                await session.commit()

            response = await http.post(LOGIN, json=credentials("kim", DUMMY_PASSWORD))
    finally:
        await engine.dispose()
        await container.dispose()

    assert response.status_code == 401
    assert response.json()["detail"] == LOGIN_FAILED
