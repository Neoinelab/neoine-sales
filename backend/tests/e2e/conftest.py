from contextlib import AsyncExitStack
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.auth.issue_session import IssueSession
from app.config.profiles import LocalSettings
from app.container import Container
from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Principal, Role
from app.domain.user.entities import User
from app.domain.user.value_objects import UserId
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from app.infra.system_clock import SystemClock
from app.main import create_app
from tests.factories_auth import ADMIN_LOGIN, ADMIN_PASSWORD
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.fakes.use_cases import FakeUseCases
from tests.support.user_ids import ACTOR_ID, OWNER_ID, uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from fastapi import FastAPI
    from sqlalchemy.engine import URL

    from app.application.ports.unit_of_work import UnitOfWorkFactory

TRUNCATE_ALL = (
    "truncate auth_sessions, users, login_failures, directory_settings, "
    "deal_actions, deals, customers, partners cascade"
)
TEST_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
ALLOWED_ORIGIN = "http://localhost:5173"
SESSION_COOKIE = "neoine_session"
CSRF_HEADER = {"X-Requested-With": "neoine-web"}
DEFAULT_LOGIN = "sales-user"  # 기본 client·stack이 로그인한 사용자(sales)의 아이디
DEFAULT_NAME = f"사용자 {DEFAULT_LOGIN}"  # principal_for가 만드는 표시 이름


def make_settings(**overrides: object) -> LocalSettings:
    """실제 환경 파일을 읽지 않는 테스트용 설정."""
    values: dict[str, object] = {
        "database_url": TEST_DATABASE_URL,
        "jwt_secret": "x" * 40,
        "cors_allowed_origins": [ALLOWED_ORIGIN],
    }
    return LocalSettings(_env_file=None, **{**values, **overrides})  # type: ignore[arg-type]


def new_client(
    app: FastAPI, *, token: str | None = None, csrf: bool = True, base_url: str = "http://test"
) -> AsyncClient:
    headers = CSRF_HEADER if csrf else {}
    cookies = {SESSION_COOKIE: token} if token else None
    return AsyncClient(
        transport=ASGITransport(app=app), base_url=base_url, headers=headers, cookies=cookies
    )


@pytest.fixture
def use_cases() -> FakeUseCases:
    return FakeUseCases()


@pytest.fixture
def app(use_cases: FakeUseCases) -> FastAPI:
    return create_app(settings=make_settings(), use_cases=use_cases)


@pytest_asyncio.fixture
async def client(
    app: FastAPI, use_cases: FakeUseCases, deal_users: None
) -> AsyncIterator[AsyncClient]:
    """영업 사용자(sales)로 로그인한 클라이언트: 사용자 행을 등록하고 세션을 발급한다.

    Deal·활동 요청의 기본 담당자·활동자(deal_users)도 함께 둔다(사용자 목록 테스트는 admin_client).
    """
    token = await use_cases.login_as(principal_for(DEFAULT_LOGIN, Role.SALES))
    async with new_client(app, token=token) as http:
        yield http


@pytest_asyncio.fixture
async def admin_client(app: FastAPI, use_cases: FakeUseCases) -> AsyncIterator[AsyncClient]:
    """관리자(root)로 로그인한 클라이언트. AD 설정이 저장돼 있고 AD에 root/pw-root 계정이 있다."""
    await use_cases.seed_directory()
    use_cases.directory.add_account(ADMIN_LOGIN, ADMIN_PASSWORD)
    token = await use_cases.login_as(principal_for(ADMIN_LOGIN, Role.ADMIN))
    async with new_client(app, token=token) as http:
        yield http


@pytest_asyncio.fixture
async def viewer_client(app: FastAPI, use_cases: FakeUseCases) -> AsyncIterator[AsyncClient]:
    """조회 전용(user) 역할로 로그인한 클라이언트."""
    token = await use_cases.login_as(principal_for("viewer", Role.USER))
    async with new_client(app, token=token) as http:
        yield http


@pytest_asyncio.fixture
async def anonymous_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with new_client(app) as http:
        yield http


def principal_for(subject: str, role: Role = Role.SALES) -> Principal:
    """subject를 로그인 아이디로 한 주체. user_id는 로그인 도우미가 users 행의 id로 바꿔 넣는다."""
    return Principal(uid(subject), subject, f"{subject}@local.test", f"사용자 {subject}", role)


@pytest_asyncio.fixture
async def owners(use_cases: FakeUseCases) -> dict[str, str]:
    """검색·지정 검증용 재직 사용자들(login id -> user id 문자열): x, y, park, park2."""
    ids: dict[str, str] = {}
    for login in ("x", "y", "park", "park2"):
        await use_cases.seed_user(login, Role.SALES)
        ids[login] = str(await use_cases.user_id_of(login))
    return ids


@pytest_asyncio.fixture
async def deal_users(use_cases: FakeUseCases) -> None:
    """Deal 담당자·활동자 기본값(OWNER_ID/ACTOR_ID, payloads의 기본 요청값)을 재직 사용자로 둔다."""
    async with use_cases.uow as uow:
        await ensure_users(uow.users, OWNER_ID, ACTOR_ID)
        await uow.commit()


@pytest_asyncio.fixture
async def client_as(
    app: FastAPI, use_cases: FakeUseCases
) -> AsyncIterator[Callable[[str, Role], Awaitable[AsyncClient]]]:
    """(아이디, 역할)로 사용자 행을 등록하고 로그인한 클라이언트를 돌려주는 팩토리."""
    async with AsyncExitStack() as stack_:

        async def open_client(login_id: str, role: Role) -> AsyncClient:
            token = await use_cases.login_as(principal_for(login_id, role))
            return await stack_.enter_async_context(new_client(app, token=token))

        yield open_client


@pytest_asyncio.fixture
async def client_for(
    app: FastAPI, use_cases: FakeUseCases, deal_users: None
) -> AsyncIterator[Callable[[str], Awaitable[AsyncClient]]]:
    """subject를 주면 그 사용자로 로그인한 클라이언트 팩토리(Fake UoW, deal_users 포함)."""
    async with AsyncExitStack() as stack_:

        async def open_client(subject: str) -> AsyncClient:
            token = await use_cases.login_as(principal_for(subject))
            return await stack_.enter_async_context(new_client(app, token=token))

        yield open_client


async def _truncate(database_url: URL) -> None:
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(TRUNCATE_ALL))
    finally:
        await engine.dispose()


async def _register_and_issue(
    uow_factory: UnitOfWorkFactory, ttl_hours: int, principal: Principal
) -> str:
    """공개 클래스만으로 사용자 행을 등록하고 세션을 발급한다(Container 내부에 의존하지 않는다)."""
    async with uow_factory() as uow:
        user = await uow.users.get_active_by_login_id(LoginId(principal.subject))
        if user is None:
            user_id = UserId(uuid4())
            user = User.register(
                LoginId(principal.subject),
                principal.role,
                created_by_user_id=user_id,  # 스스로 등록한 행
                entity_id=user_id,
                now=SystemClock().now(),
            )
            await uow.users.add(user)
            await uow.commit()
    issue = IssueSession(uow_factory, SystemClock(), timedelta(hours=ttl_hours))
    return (await issue.execute(replace(principal, user_id=user.id))).token


async def _seed_deal_users(uow_factory: UnitOfWorkFactory) -> None:
    async with uow_factory() as uow:
        await ensure_users(uow.users, OWNER_ID, ACTOR_ID)
        await uow.commit()


@pytest_asyncio.fixture
async def stack_for(
    test_database_url: URL,
) -> AsyncIterator[Callable[[str], Awaitable[AsyncClient]]]:
    """실제 PostgreSQL을 쓰는 다중 사용자 팩토리(sales). 끝나면 테이블을 비운다."""
    settings = make_settings(database_url=test_database_url.render_as_string(hide_password=False))
    container = Container(settings, directory=FakeDirectoryAuthenticator())
    app = create_app(settings=settings, use_cases=container)
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    uow_factory = sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
    try:
        await _seed_deal_users(uow_factory)
        async with AsyncExitStack() as stack_:

            async def open_client(subject: str) -> AsyncClient:
                token = await _register_and_issue(
                    uow_factory, settings.session_ttl_hours, principal_for(subject)
                )
                return await stack_.enter_async_context(new_client(app, token=token))

            yield open_client
    finally:
        await container.dispose()
        await engine.dispose()
        await _truncate(test_database_url)


@pytest_asyncio.fixture
async def stack(test_database_url: URL) -> AsyncIterator[AsyncClient]:
    """실제 PostgreSQL을 쓰는 sales 클라이언트."""
    settings = make_settings(database_url=test_database_url.render_as_string(hide_password=False))
    container = Container(settings, directory=FakeDirectoryAuthenticator())
    app = create_app(settings=settings, use_cases=container)
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    uow_factory = sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
    try:
        await _seed_deal_users(uow_factory)
        token = await _register_and_issue(
            uow_factory, settings.session_ttl_hours, principal_for(DEFAULT_LOGIN)
        )
        async with new_client(app, token=token) as http:
            yield http
    finally:
        await container.dispose()
        await engine.dispose()
        await _truncate(test_database_url)


@dataclass(frozen=True, slots=True)
class AuthFullStack:
    """실제 PostgreSQL + FakeDirectoryAuthenticator로 조립한 인증 전체 구간."""

    database_url: URL
    settings: LocalSettings
    directory: FakeDirectoryAuthenticator

    def open_app(self, **setting_overrides: object) -> tuple[Container, FastAPI]:
        """같은 DB를 보는 앱 인스턴스(다른 워커·서버 시뮬레이션). 호출한 쪽이 dispose한다."""
        settings = self.settings.model_copy(update=setting_overrides)
        container = Container(settings, directory=self.directory)
        return container, create_app(settings=settings, use_cases=container)


@pytest_asyncio.fixture
async def auth_full_stack(test_database_url: URL) -> AsyncIterator[AuthFullStack]:
    settings = make_settings(database_url=test_database_url.render_as_string(hide_password=False))
    try:
        yield AuthFullStack(test_database_url, settings, FakeDirectoryAuthenticator())
    finally:
        await _truncate(test_database_url)


@pytest_asyncio.fixture
async def ready(use_cases: FakeUseCases) -> FakeUseCases:
    """AD 설정이 있고, AD에 kim/newbie/gone이 있으며 kim(sales)·gone(삭제)만 앱에 등록돼 있다."""
    await use_cases.seed_directory()
    await use_cases.seed_user("kim", Role.SALES)
    use_cases.directory.add_account("kim", "pw-kim", display_name="김영업", email="kim@corp.test")
    use_cases.directory.add_account("newbie", "pw-newbie")
    return use_cases
