"""functional test(feature end-to-end, BDD) 공통 fixture.

`api`는 실제 PostgreSQL 임시 DB(세션당 하나, 마이그레이션 head 적용) 위에 실제 Container로 앱을
띄우고 httpx ASGI 클라이언트로 감싼 것이다. 로그인 상태(세션 쿠키)는 클라이언트 쿠키로 유지되며
`tests/functional/steps/auth.py`의 Given step으로 바꾼다.

격리: 기존 e2e와 같다. 테스트가 끝나면 모든 업무 테이블을 TRUNCATE한다(한 세션 DB를 공유).

시드 카탈로그: 위 TRUNCATE(`users … cascade`)가 기본 BANT Label 23개까지 지우고 시나리오가 코드를
바꾸기도 하므로, 시작과 정리 단계에서 기본 코드(Status 7·Forecast 6)·기본 Label·기본
Action 유형 8개를 마이그레이션 시드와 같은 값(`tests/fakes/catalog_seed.py`)으로 복원한다.
그래서 어느 feature든 시작 상태에서
기본 카탈로그를 읽을 수 있다. 복원은 Repository Port 구현(SqlCodeRepository,
SqlBantLabelRepository, SqlActionTypeRepository)으로 넣는다. 복원된 기본 유형의 id는 이름에서
정해진 고정 정수(`tests/factories_action_type.type_id`, 20억대)이고, 마이그레이션 직후 DB
(`fresh_api`)의 시드 id는 시퀀스가 매긴 1부터의 값이므로 step은 id를 이름으로 API에서 찾는다.

외부 대체: 회사 AD(LDAP)는 테스트 환경에서 띄울 수 없고 Container는 디렉터리 Port만 주입받으므로
`FakeDirectoryAuthenticator`(Port 구현)로 대체한다. AD 계정은 `api.directory.add_account`로 둔다.

시계: Container에 `clock`을 주입한다(`api.clock`). 시작 시점의 실제 시각에 고정되고 step이 전진시킬
때만 움직여서(`tests/support/functional_clock.py`), 응답의 시각을 정확한 값으로 단언할 수 있다.
"""

from typing import TYPE_CHECKING, Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.profiles import LocalSettings
from app.container import Container
from app.infra.db.bant_label_repository import SqlBantLabelRepository
from app.infra.db.code_repository import SqlCodeRepository
from app.main import create_app
from tests.factories_action_type import default_action_types
from tests.fakes.catalog_seed import default_codes, default_labels
from tests.fakes.directory import FakeDirectoryAuthenticator
from tests.support.crypto_keys import TEST_FERNET_KEY
from tests.support.database import apply_migrations, resolve_admin_url, temporary_database
from tests.support.functional_clock import activate, new_clock
from tests.support.skips import skip_or_fail
from tests.support.truncate import truncate_business_tables

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from fastapi import FastAPI
    from httpx import Response
    from sqlalchemy.engine import URL

    from tests.fakes.unit_of_work import FixedClock


ALLOWED_ORIGIN = "http://localhost:5173"
CSRF_HEADER = {"X-Requested-With": "neoine-web"}
BASE_URL = "http://test"
Params = dict[str, str | int | list[str]]


def make_settings(database_url: str, **overrides: object) -> LocalSettings:
    """실제 환경 파일을 읽지 않는 테스트용 local 설정(비밀은 더미 값)."""
    values: dict[str, object] = {
        "database_url": database_url,
        "jwt_secret": "x" * 40,
        "settings_encryption_key": TEST_FERNET_KEY,
        "cors_allowed_origins": [ALLOWED_ORIGIN],
    }
    return LocalSettings(_env_file=None, **{**values, **overrides})  # type: ignore[arg-type]


class Api:
    """시나리오가 쓰는 HTTP 클라이언트 래퍼. 쿠키(로그인 상태)를 요청 사이에 유지한다."""

    def __init__(
        self,
        database_url: URL,
        directory: FakeDirectoryAuthenticator,
        clock: FixedClock | None = None,
        storage_root: Path | None = None,
    ) -> None:
        self.database_url = database_url
        self.directory = directory
        # 파일 저장 위치로 쓰는 실제 디렉터리(tmp_path 아래). 시나리오가 최초 설정·외부연동으로
        # 이 경로를 등록한다(없는 디렉터리여도 쓰기 확인이 만든다). 파일은 이 경로를 직접 본다.
        self.storage_root = storage_root
        self.clock = clock or new_clock()
        activate(self.clock)
        self._container, self._client = self._open()

    def _open(self, **setting_overrides: object) -> tuple[Container, AsyncClient]:
        overrides = dict(setting_overrides)
        real_url = self.database_url.render_as_string(hide_password=False)
        settings = make_settings(str(overrides.pop("database_url", real_url)), **overrides)
        container = Container(settings, directory=self.directory, clock=self.clock)
        app: FastAPI = create_app(settings=settings, use_cases=container)
        client = AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
        client.headers.update(CSRF_HEADER)
        return container, client

    async def reopen(self, **setting_overrides: object) -> None:
        """설정을 바꿔 앱을 다시 띄운다(예: 접속할 수 없는 DB). 쿠키는 버린다."""
        await self.aclose()
        self._container, self._client = self._open(**setting_overrides)

    def forget_session(self) -> None:
        """서버에 알리지 않고 브라우저 쿠키만 지운다(익명 사용자로 전환)."""
        self._client.cookies.clear()

    async def request(  # noqa: PLR0913 - HTTP 요청의 독립적인 선택지
        self,
        method: str,
        url: str,
        *,
        json: object = None,
        params: Params | None = None,
        headers: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Response:
        """files를 주면 multipart/form-data 본문이다(파일 파트는 (이름, 바이트, 형식) 튜플,
        문자 파트는 (None, 값))."""
        return await self._client.request(
            method, url, json=json, params=params, headers=headers, files=files
        )

    async def get(
        self, url: str, *, params: Params | None = None, headers: dict[str, str] | None = None
    ) -> Response:
        return await self.request("GET", url, params=params, headers=headers)

    async def post(self, url: str, *, json: object = None) -> Response:
        return await self.request("POST", url, json=json)

    async def put(self, url: str, *, json: object = None) -> Response:
        return await self.request("PUT", url, json=json)

    async def patch(self, url: str, *, json: object = None) -> Response:
        return await self.request("PATCH", url, json=json)

    async def delete(self, url: str) -> Response:
        return await self.request("DELETE", url)

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._container.dispose()


async def restore_default_catalog(database_url: URL) -> None:
    """기본 코드·Label 23개·Action 유형 8개로 되돌린다(시나리오가 바꾼 것은 버린다)."""
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("truncate codes, bant_labels, action_types cascade"))
        # Action 유형 구현은 사용 시점에 가져온다(구현 전에도 functional 수집이 막히지 않게)
        from app.infra.db.action_type_repository import SqlActionTypeRepository  # noqa: PLC0415

        async with AsyncSession(engine, expire_on_commit=False) as session:
            codes, labels = SqlCodeRepository(session), SqlBantLabelRepository(session)
            types = SqlActionTypeRepository(session)
            for code in default_codes():
                await codes.add(code)
            for label in default_labels():
                await labels.add(label)
            for action_type in default_action_types():
                await types.add(action_type)
            await session.commit()
    finally:
        await engine.dispose()


async def _truncate(database_url: URL) -> None:
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await truncate_business_tables(connection)
    finally:
        await engine.dispose()
    await restore_default_catalog(database_url)


@pytest_asyncio.fixture
async def fresh_api(tmp_path: Path) -> AsyncIterator[Api]:
    """마이그레이션만 적용한 새 임시 DB 위의 앱. 시드가 그대로 남아 있고 업무 데이터는 없다.

    복원·TRUNCATE를 하지 않으므로 시드 id가 마이그레이션이 매긴 값(1부터)이다. 마이그레이션 직후의
    초기화된 시스템(최초 설정 3단계가 다시 열린 상태)을 보는 시나리오가 쓴다.
    """
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 새 DB 시나리오를 건너뜁니다")
    async with temporary_database(admin_url) as url:
        await apply_migrations(url)
        client = Api(url, FakeDirectoryAuthenticator(), storage_root=tmp_path / "neoine-files")
        try:
            yield client
        finally:
            await client.aclose()


@pytest_asyncio.fixture
async def api(test_database_url: URL, tmp_path: Path) -> AsyncIterator[Api]:
    # 앞서 돈 다른 층(users cascade TRUNCATE)이 카탈로그를 지웠을 수 있어 시작에도 복원
    await restore_default_catalog(test_database_url)
    client = Api(
        test_database_url, FakeDirectoryAuthenticator(), storage_root=tmp_path / "neoine-files"
    )
    try:
        yield client
    finally:
        await client.aclose()
        await _truncate(test_database_url)
